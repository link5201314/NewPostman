from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from typing import Any

import httpx
from PySide6.QtCore import Qt, QTimer
import pytest
from pytestqt.qtbot import QtBot

from newpostman.core.collection_runner import CollectionRunner, RunSummary
from newpostman.core.project_store import ProjectStore
from newpostman.models.collection import CollectionModel
from newpostman.models.environment import EnvironmentModel
from newpostman.models.request import RequestModel
from newpostman.ui.main_window import MainWindow
from newpostman.ui.runner_panel import RunnerPanel


@pytest.fixture
def client_factory() -> Iterator[Callable[[httpx.BaseTransport], httpx.Client]]:
    """提供使用者負責關閉的 HTTPX Client 工廠。"""
    with ExitStack() as stack:

        def create_client(transport: httpx.BaseTransport) -> httpx.Client:
            """建立並註冊注入指定 Transport 的 HTTPX Client。"""
            return stack.enter_context(httpx.Client(transport=transport))

        yield create_client


def make_request(name: str, url: str) -> RequestModel:
    """建立 Runner 測試使用的 Request。"""
    return RequestModel(name=name, method="GET", url=url)


def test_collection_runner_executes_in_order_and_continues_after_errors(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    received_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_urls.append(str(request.url))
        if request.url.path == "/offline":
            raise httpx.ConnectError("connection refused", request=request)
        if request.url.path == "/unavailable":
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, json={"ok": True})

    collection = CollectionModel(
        name="API checks",
        requests=[
            make_request("First", "https://api.example.test/first"),
            make_request("Missing variable", "https://{{missing_host}}/skip"),
            make_request("Transport error", "https://api.example.test/offline"),
            make_request("Server error", "https://api.example.test/unavailable"),
            make_request("Last", "https://api.example.test/last"),
        ],
    )
    runner = CollectionRunner(client=client_factory(httpx.MockTransport(handler)))
    progress: list[tuple[int, int]] = []
    item_results: list[Any] = []
    log_entries: list[str] = []
    runner.progress.connect(lambda completed, total: progress.append((completed, total)))
    runner.request_completed.connect(item_results.append)
    runner.log.connect(log_entries.append)

    summary = runner.run(collection)

    assert received_urls == [
        "https://api.example.test/first",
        "https://api.example.test/offline",
        "https://api.example.test/unavailable",
        "https://api.example.test/last",
    ]
    assert [item.request_name for item in item_results] == [
        "First",
        "Missing variable",
        "Transport error",
        "Server error",
        "Last",
    ]
    assert item_results[1].result.error is not None
    assert "HTTP 傳輸失敗" in item_results[2].result.error
    assert item_results[3].result.response.status_code == 503
    assert progress == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
    assert any("HTTP 503" in entry for entry in log_entries)
    assert any("Missing variable" in entry and "失敗" in entry for entry in log_entries)
    assert summary == RunSummary(total=5, succeeded=3, failed=2, cancelled=False)


def test_collection_runner_cancellation_stops_before_next_request(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
    qtbot: QtBot,
) -> None:
    request_started = Event()
    release_request = Event()
    received_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_urls.append(str(request.url))
        request_started.set()
        release_request.wait(timeout=5)
        return httpx.Response(200)

    collection = CollectionModel(
        name="Cancelable",
        requests=[
            make_request("First", "https://api.example.test/first"),
            make_request("Second", "https://api.example.test/second"),
        ],
    )
    runner = CollectionRunner(client=client_factory(httpx.MockTransport(handler)))

    assert runner.start(collection)
    qtbot.waitUntil(request_started.is_set, timeout=3000)
    with qtbot.waitSignal(runner.run_finished, timeout=3000) as signal:
        runner.cancel()
        release_request.set()

    assert len(received_urls) == 1
    assert signal.args[0] == RunSummary(
        total=2,
        succeeded=1,
        failed=0,
        cancelled=True,
    )


def test_runner_tab_uses_active_environment_and_keeps_ui_responsive(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    request_started = Event()
    release_request = Event()
    ui_event_processed = Event()
    received_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_urls.append(str(request.url))
        request_started.set()
        release_request.wait(timeout=5)
        return httpx.Response(200)

    client = client_factory(httpx.MockTransport(handler))
    store = ProjectStore(tmp_path / "project.json")
    environment = store.add_environment(
        EnvironmentModel(name="Development", variables={"host": "dev.example.test"})
    )
    collection = store.add_collection(
        CollectionModel(
            name="Smoke",
            requests=[
                make_request("Health", "https://{{host}}/health"),
                make_request("Second", "https://{{host}}/second"),
            ],
        )
    )
    window = MainWindow(store=store, client=client)
    qtbot.addWidget(window)
    qtbot.mouseClick(window.run_button, Qt.MouseButton.LeftButton)
    panel = window.workspace_tabs.currentWidget()
    assert isinstance(panel, RunnerPanel)
    assert not window.save_as_button.isEnabled()
    assert panel.collection_selector.currentData() == str(collection.id)
    assert panel.environment_label.text() == environment.name
    resource_names = []
    for index in range(window.resource_tree.topLevelItemCount()):
        resource_item = window.resource_tree.topLevelItem(index)
        assert resource_item is not None
        resource_names.append(resource_item.text(0))
    assert resource_names == ["Collections", "Environments"]

    qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(request_started.is_set, timeout=3000)
    QTimer.singleShot(0, ui_event_processed.set)
    qtbot.waitUntil(ui_event_processed.is_set, timeout=3000)

    with qtbot.waitSignal(panel.runner.run_finished, timeout=3000) as signal:
        qtbot.mouseClick(panel.cancel_button, Qt.MouseButton.LeftButton)
        release_request.set()

    assert received_urls == ["https://dev.example.test/health"]
    assert signal.args[0].succeeded == 1
    assert signal.args[0].total == 2
    assert signal.args[0].cancelled is True
    assert "1/2" in panel.progress_label.text()


def test_runner_tab_can_select_collection_and_start_empty_collection(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    store.add_collection(CollectionModel(name="Other collection"))
    empty_collection = store.add_collection(CollectionModel(name="Empty collection"))
    window = MainWindow(store=store)
    qtbot.addWidget(window)

    qtbot.mouseClick(window.run_button, Qt.MouseButton.LeftButton)
    panel = window.workspace_tabs.currentWidget()
    assert isinstance(panel, RunnerPanel)
    assert panel.collection_selector.count() == 2
    panel.collection_selector.setCurrentIndex(
        panel.collection_selector.findData(str(empty_collection.id))
    )
    qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: "完成" in panel.summary_label.text(), timeout=3000)
    assert "0" in panel.summary_label.text()
