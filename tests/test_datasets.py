from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

import httpx
import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from newpostman.core.collection_runner import CollectionRunner, RunSummary
from newpostman.core.dataset_loader import DatasetLoadError, DatasetLoader
from newpostman.core.project_store import ProjectStore
from newpostman.models.collection import CollectionModel
from newpostman.models.dataset import DatasetModel
from newpostman.models.environment import EnvironmentModel
from newpostman.models.request import (
    ExtractorModel,
    ExtractorType,
    RequestModel,
)
from newpostman.ui.main_window import MainWindow
from newpostman.ui.runner_panel import RunnerPanel


@pytest.fixture
def client_factory() -> Iterator[
    Callable[[httpx.BaseTransport], httpx.Client]
]:
    """提供由 fixture 關閉的 HTTPX Client 工廠。"""
    with ExitStack() as stack:

        def create_client(transport: httpx.BaseTransport) -> httpx.Client:
            """建立並註冊注入 MockTransport 的 Client。"""
            return stack.enter_context(httpx.Client(transport=transport))

        yield create_client


def test_dataset_loader_reads_csv_rows_and_json_values_as_strings(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "users.csv"
    csv_path.write_text("user_id,name\n1,Ada\n2,Grace\n", encoding="utf-8")
    json_path = tmp_path / "users.json"
    json_path.write_text(
        json.dumps(
            [
                {"user_id": 3, "active": True},
                {"user_id": 4, "active": False},
            ]
        ),
        encoding="utf-8",
    )

    assert DatasetLoader.load(csv_path) == [
        {"user_id": "1", "name": "Ada"},
        {"user_id": "2", "name": "Grace"},
    ]
    assert DatasetLoader.load(json_path) == [
        {"user_id": "3", "active": "true"},
        {"user_id": "4", "active": "false"},
    ]


def test_dataset_loader_reports_invalid_csv_and_json_before_run(
    tmp_path: Path,
) -> None:
    invalid_csv = tmp_path / "invalid.csv"
    invalid_csv.write_text("id,id\n1,2\n", encoding="utf-8")
    malformed_csv = tmp_path / "malformed.csv"
    malformed_csv.write_text('id,name\n1,"unterminated\n', encoding="utf-8")
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text('[{"id": 1}, null]', encoding="utf-8")
    nonstandard_json = tmp_path / "nonstandard.json"
    nonstandard_json.write_text('[{"id": NaN}]', encoding="utf-8")

    with pytest.raises(DatasetLoadError, match="欄名"):
        DatasetLoader.load(invalid_csv)
    with pytest.raises(DatasetLoadError, match="CSV Dataset 格式錯誤"):
        DatasetLoader.load(malformed_csv)
    with pytest.raises(DatasetLoadError, match="第 2 筆"):
        DatasetLoader.load(invalid_json)
    with pytest.raises(DatasetLoadError, match="非標準常數 NaN"):
        DatasetLoader.load(nonstandard_json)


def test_project_store_persists_dataset_reference_without_copying_source(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = project_root / "data" / "users.csv"
    source.parent.mkdir()
    source.write_text("id\n1\n", encoding="utf-8")
    source_contents = source.read_bytes()
    store = ProjectStore(project_root / "project.json")

    dataset = store.add_dataset(source)
    reopened = ProjectStore(project_root / "project.json")

    assert reopened.get_dataset(dataset.id).path == source.resolve()
    assert reopened.list_datasets() == [dataset]
    assert source.read_bytes() == source_contents
    project_index = json.loads(
        (project_root / "project.json").read_text(encoding="utf-8")
    )
    assert project_index["datasets"][str(dataset.id)] == "data/users.csv"


def test_collection_runner_isolates_runtime_variables_per_dataset_row(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
    tmp_path: Path,
) -> None:
    requests_seen: list[tuple[str, str | None, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        data_row_id = request.headers.get("x-row")
        requests_seen.append(
            (
                request.url.path,
                data_row_id,
                request.headers.get("authorization"),
            )
        )
        if request.url.path == "/start":
            if data_row_id == "A":
                return httpx.Response(200, json={"token": "token-A"})
            return httpx.Response(200, json={"other": "no token for row B"})
        return httpx.Response(200)

    dataset_path = tmp_path / "rows.json"
    dataset_path.write_text('[{"id":"A"},{"id":"B"}]', encoding="utf-8")
    dataset = DatasetModel(id=uuid4(), name="Rows", path=dataset_path)
    collection = CollectionModel(
        name="Per-row",
        requests=[
            RequestModel(
                name="Start",
                url="https://api.example.test/start",
                headers={"X-Row": "{{id}}"},
                extractors=[
                    ExtractorModel(
                        variable_name="token",
                        kind=ExtractorType.JSONPATH,
                        expression="$.token",
                    )
                ],
            ),
            RequestModel(
                name="Use token",
                url="https://api.example.test/use",
                headers={
                    "Authorization": "Bearer {{token}}",
                    "X-Row": "{{id}}",
                },
            ),
        ],
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )
    progress: list[tuple[int, int]] = []
    completed_items: list[Any] = []
    iteration_progress: list[tuple[int, int, int, int]] = []
    runner.progress.connect(lambda done, total: progress.append((done, total)))
    runner.request_completed.connect(completed_items.append)
    runner.iteration_progress.connect(
        lambda iteration, iterations, done, total: iteration_progress.append(
            (iteration, iterations, done, total)
        )
    )

    summary = runner.run(
        collection,
        EnvironmentModel(name="Development", variables={"id": "env"}),
        dataset_rows=DatasetLoader.load(dataset.path),
    )

    assert requests_seen == [
        ("/start", "A", None),
        ("/use", "A", "Bearer token-A"),
        ("/start", "B", None),
    ]
    assert [item.iteration_index for item in completed_items] == [1, 1, 2, 2]
    assert iteration_progress[-1] == (2, 2, 2, 2)
    assert progress[-1] == (4, 4)
    assert summary == RunSummary(
        total=4,
        succeeded=3,
        failed=1,
        cancelled=False,
        iterations=2,
        completed_iterations=2,
    )


def test_dataset_row_wins_extraction_and_keeps_its_value_for_next_request(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_headers.append(request.headers.get("x-id", "<missing>"))
        return httpx.Response(200, json={"id": "extracted"})

    collection = CollectionModel(
        name="Single iteration",
        requests=[
            RequestModel(
                name="Extract",
                url="https://api.example.test/",
                extractors=[
                    ExtractorModel(
                        variable_name="id",
                        kind=ExtractorType.JSONPATH,
                        expression="$.id",
                    )
                ],
            ),
            RequestModel(
                name="Use row value",
                url="https://api.example.test/next",
                headers={"X-Id": "{{id}}"},
            ),
        ],
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )

    summary = runner.run(
        collection,
        EnvironmentModel(name="Dev", variables={"id": "env"}),
        dataset_rows=[{"id": "row"}],
    )

    assert sent_headers == ["<missing>", "row"]
    assert summary.iterations == 1
    assert summary.completed_iterations == 1


def test_runner_panel_handles_invalid_selected_dataset_before_running(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    collection = store.add_collection(CollectionModel(name="Users"))
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("[]", encoding="utf-8")
    window = MainWindow(store=store)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "newpostman.ui.main_window.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (
            str(invalid_path),
            "Dataset (*.csv *.json)",
        ),
    )
    qtbot.mouseClick(window.load_dataset_button, Qt.MouseButton.LeftButton)
    dataset = store.list_datasets()[0]
    invalid_path.write_text("not-json", encoding="utf-8")
    panel = window.open_runner_tab()
    assert isinstance(panel, RunnerPanel)
    assert panel.dataset_selector.count() == 2
    assert panel.collection_selector.currentData() == str(collection.id)
    assert window.resource_tree.topLevelItemCount() == 3
    datasets_root = window.resource_tree.topLevelItem(2)
    assert datasets_root is not None
    assert datasets_root.text(0) == "Datasets"

    warnings: list[str] = []
    monkeypatch.setattr(
        "newpostman.ui.runner_panel.QMessageBox.warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    panel.dataset_selector.setCurrentIndex(
        panel.dataset_selector.findData(str(dataset.id))
    )
    qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)

    assert not panel.runner.is_running
    assert warnings
    assert "JSON" in warnings[0]


def test_runner_panel_runs_selected_dataset_rows(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    received_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_ids.append(request.headers["x-id"])
        return httpx.Response(200)

    dataset_path = tmp_path / "ids.csv"
    dataset_path.write_text("id\nfirst\nsecond\n", encoding="utf-8")
    store = ProjectStore(tmp_path / "project.json")
    store.add_collection(
        CollectionModel(
            name="Dataset requests",
            requests=[
                RequestModel(
                    name="Echo row",
                    url="https://api.example.test/",
                    headers={"X-Id": "{{id}}"},
                )
            ],
        )
    )
    dataset = store.add_dataset(dataset_path)
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(handler)),
    )
    qtbot.addWidget(window)
    window.show()
    panel = window.open_runner_tab()
    assert isinstance(panel, RunnerPanel)
    assert panel.dataset_selector.isVisible()
    panel.dataset_selector.setCurrentIndex(
        panel.dataset_selector.findData(str(dataset.id))
    )

    qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "完成" in panel.summary_label.text(), timeout=3000)

    assert received_ids == ["first", "second"]
    assert "2/2" in panel.summary_label.text()
    assert "Iteration 2/2" in panel.progress_label.text()


def test_dataset_cancellation_finishes_current_request_and_starts_no_next_row(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
    qtbot: QtBot,
) -> None:
    request_started = Event()
    release_request = Event()
    seen_rows: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_rows.append(request.headers["x-row"])
        request_started.set()
        release_request.wait(timeout=5)
        return httpx.Response(200)

    collection = CollectionModel(
        name="Cancelable dataset",
        requests=[
            RequestModel(
                name="Read",
                url="https://api.example.test/",
                headers={"X-Row": "{{id}}"},
            )
        ],
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )
    assert runner.start(collection, dataset_rows=[{"id": "1"}, {"id": "2"}])
    qtbot.waitUntil(request_started.is_set, timeout=3000)

    with qtbot.waitSignal(runner.run_finished, timeout=3000) as signal:
        runner.cancel()
        release_request.set()

    assert seen_rows == ["1"]
    assert signal.args[0].cancelled is True
    assert signal.args[0].completed_iterations == 1
