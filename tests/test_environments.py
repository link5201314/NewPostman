from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from newpostman.core.project_store import ProjectStore, ProjectStoreError
from newpostman.models.environment import EnvironmentModel
from newpostman.ui.environment_manager import EnvironmentManagerDialog
from newpostman.ui.main_window import MainWindow


@pytest.fixture
def client_factory() -> Iterator[Callable[[httpx.BaseTransport], httpx.Client]]:
    """提供由 fixture 管理生命週期的 HTTPX Client 工廠。"""
    with ExitStack() as stack:

        def create_client(transport: httpx.BaseTransport) -> httpx.Client:
            """建立一個由 ExitStack 關閉的 HTTPX Client。"""
            return stack.enter_context(httpx.Client(transport=transport))

        yield create_client


def test_project_store_persists_environment_and_active_selection(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    development = store.add_environment(
        EnvironmentModel(
            name="Development", variables={"base_url": "https://dev.example.test"}
        )
    )
    staging = store.add_environment(
        EnvironmentModel(
            name="Staging", variables={"base_url": "https://staging.example.test"}
        )
    )
    store.set_active_environment(staging.id)

    reopened = ProjectStore(tmp_path / "project.json")

    assert [item.name for item in reopened.list_environments()] == [
        "Development",
        "Staging",
    ]
    assert reopened.active_environment() == staging
    assert reopened.active_environment() != development
    assert (tmp_path / "environments" / f"{staging.id}.json").is_file()


def test_project_store_rejects_environment_path_outside_environment_directory(
    tmp_path: Path,
) -> None:
    project_directory = tmp_path / "project"
    project_directory.mkdir()
    protected_file = tmp_path / "outside.json"
    protected_file.write_text('{"preserve": true}', encoding="utf-8")
    environment_id = uuid4()
    project_path = project_directory / "project.json"
    project_path.write_text(
        json.dumps(
            {
                "environments": {str(environment_id): "../outside.json"},
                "active_environment_id": str(environment_id),
            }
        ),
        encoding="utf-8",
    )
    store = ProjectStore(project_path)

    with pytest.raises(ProjectStoreError, match="environments 目錄"):
        store.remove_environment(environment_id)

    assert protected_file.read_text(encoding="utf-8") == '{"preserve": true}'


def test_environment_manager_saves_edited_key_value_variables(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    environment = store.add_environment(EnvironmentModel(name="Development"))
    dialog = EnvironmentManagerDialog(store)
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.environment_list.setCurrentRow(0)
    qtbot.mouseClick(dialog.add_variable_button, Qt.MouseButton.LeftButton)
    dialog.variables_table.setItem(0, 0, dialog.make_table_item("base_url"))
    dialog.variables_table.setItem(
        0, 1, dialog.make_table_item("https://dev.example.test")
    )
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    saved = store.get_environment(environment.id)
    assert saved.variables == {"base_url": "https://dev.example.test"}


def test_main_window_uses_selected_environment_for_request(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["content"] = request.content
        return httpx.Response(200, json={"ok": True})

    store = ProjectStore(tmp_path / "project.json")
    store.add_environment(
        EnvironmentModel(
            name="Development",
            variables={
                "base_url": "https://dev.example.test",
                "environment_tag": "development",
                "item_id": "42",
            },
        )
    )
    store.add_environment(
        EnvironmentModel(
            name="Staging",
            variables={
                "base_url": "https://staging.example.test",
                "environment_tag": "staging",
                "item_id": "84",
            },
        )
    )
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(handler)),
    )
    qtbot.addWidget(window)
    window.show()
    window.environment_selector.setCurrentIndex(2)

    editor = window.request_editor
    editor.method_input.setCurrentText("POST")
    editor.url_input.setText("{{base_url}}/items")
    editor.headers_input.setPlainText("X-Environment: {{environment_tag}}")
    editor.params_input.setPlainText("id={{item_id}}")
    editor.body_mode_input.setCurrentText("json")
    editor.body_input.setPlainText('{"item":"{{item_id}}"}')

    with qtbot.waitSignal(editor.request_succeeded, timeout=3000):
        qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)

    assert captured["url"] == "https://staging.example.test/items?id=84"
    assert captured["headers"]["x-environment"] == "staging"
    assert captured["content"] == b'{"item":"84"}'
    assert editor.url_input.text() == "{{base_url}}/items"
    active_environment = store.active_environment()
    assert active_environment is not None
    assert active_environment.name == "Staging"


def test_missing_environment_variable_prevents_http_request(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200)

    store = ProjectStore(tmp_path / "project.json")
    store.add_environment(EnvironmentModel(name="Empty"))
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(handler)),
    )
    qtbot.addWidget(window)
    window.request_editor.url_input.setText("https://{{missing_host}}/items")

    with qtbot.waitSignal(window.request_editor.request_failed, timeout=3000) as signal:
        qtbot.mouseClick(window.request_editor.send_button, Qt.MouseButton.LeftButton)

    assert request_count == 0
    assert signal.args is not None
    assert "missing_host" in signal.args[0]
    assert window.request_editor.error_label.text()


def test_environment_substitution_that_breaks_json_prevents_http_request(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200)

    store = ProjectStore(tmp_path / "project.json")
    store.add_environment(
        EnvironmentModel(name="Development", variables={"item_name": '"broken'})
    )
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(handler)),
    )
    qtbot.addWidget(window)
    editor = window.request_editor
    editor.method_input.setCurrentText("POST")
    editor.url_input.setText("https://api.example.test/items")
    editor.body_mode_input.setCurrentText("json")
    editor.body_input.setPlainText('{"item":"{{item_name}}"}')

    with qtbot.waitSignal(editor.request_failed, timeout=3000) as signal:
        qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)

    assert request_count == 0
    assert "JSON" in signal.args[0]
    assert editor.body_input.toPlainText() == '{"item":"{{item_name}}"}'
