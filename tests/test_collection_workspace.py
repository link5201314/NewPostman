from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QSplitter, QTabWidget, QTreeWidget
from pytestqt.qtbot import QtBot

from newpostman.core.project_store import ProjectStore
from newpostman.models.collection import CollectionModel
from newpostman.models.request import BodyMode, RequestModel
from newpostman.ui.main_window import MainWindow
from newpostman.ui.request_editor import RequestEditor
from newpostman.ui.response_view import ResponseView


@pytest.fixture
def client_factory() -> Iterator[Callable[[httpx.BaseTransport], httpx.Client]]:
    """提供由 fixture 管理生命週期的 HTTPX Client 工廠。"""
    with ExitStack() as stack:

        def create_client(transport: httpx.BaseTransport) -> httpx.Client:
            """建立一個由 ExitStack 關閉的 HTTPX Client。"""
            return stack.enter_context(httpx.Client(transport=transport))

        yield create_client


def test_project_store_round_trips_collection_and_ordered_requests(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    collection = store.add_collection(
        CollectionModel(
            name="Orders",
            requests=[
                RequestModel(
                    name="Create order",
                    method="POST",
                    url="https://api.example.test/orders",
                ),
                RequestModel(
                    name="Read order", url="https://api.example.test/orders/1"
                ),
            ],
        )
    )

    reopened = ProjectStore(tmp_path / "project.json")

    assert reopened.list_collections() == [collection]
    assert [
        request.name for request in reopened.get_collection(collection.id).requests
    ] == [
        "Create order",
        "Read order",
    ]
    assert (tmp_path / "collections" / f"{collection.id}.json").is_file()


def test_main_window_opens_collection_request_once_and_focuses_existing_tab(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    collection = store.add_collection(
        CollectionModel(
            name="Orders",
            requests=[
                RequestModel(name="Read order", url="https://api.example.test/orders/1")
            ],
        )
    )
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    window.show()

    assert isinstance(window.resource_tree, QTreeWidget)
    assert isinstance(window.workspace_tabs, QTabWidget)
    collection_item = window.resource_tree.topLevelItem(0)
    assert collection_item is not None
    assert collection_item.text(0) == "Collections"
    order_group = collection_item.child(0)
    assert order_group is not None
    assert order_group.text(0) == "Orders"
    request_item = order_group.child(0)
    assert request_item is not None
    assert request_item.text(0) == "Read order"

    qtbot.mouseClick(
        window.resource_tree.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.resource_tree.visualItemRect(request_item).center(),
    )
    first_editor = window.workspace_tabs.currentWidget()
    first_index = window.workspace_tabs.currentIndex()
    window.open_collection_request(collection.id, collection.requests[0].id)

    assert (
        window.workspace_tabs.count() == 2
    )  # initial unsaved tab + one collection request
    assert window.workspace_tabs.currentIndex() == first_index
    assert window.workspace_tabs.currentWidget() is first_editor
    assert isinstance(first_editor, RequestEditor)


def test_collection_sidebar_moves_request_and_persists_order(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    collection = store.add_collection(
        CollectionModel(
            name="Orders",
            requests=[
                RequestModel(name="First", url="https://api.example.test/1"),
                RequestModel(name="Second", url="https://api.example.test/2"),
            ],
        )
    )
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    window.show()
    collection_item = window.resource_tree.topLevelItem(0)
    assert collection_item is not None
    requests_item = collection_item.child(0)
    assert requests_item is not None
    first_item = requests_item.child(0)
    assert first_item is not None
    window.resource_tree.setCurrentItem(first_item)

    qtbot.mouseClick(window.move_request_down_button, Qt.MouseButton.LeftButton)

    saved = store.get_collection(collection.id)
    assert [request.name for request in saved.requests] == ["Second", "First"]
    current_item = window.resource_tree.currentItem()
    assert current_item is not None
    assert current_item.text(0) == "First"


def test_request_editor_uses_request_tabs_and_resizable_response_views(
    qtbot: QtBot,
) -> None:
    editor = RequestEditor()
    qtbot.addWidget(editor)

    assert isinstance(editor.request_tabs, QTabWidget)
    assert [
        editor.request_tabs.tabText(index)
        for index in range(editor.request_tabs.count())
    ] == [
        "Params",
        "Headers",
        "Body",
    ]
    assert isinstance(editor.response_splitter, QSplitter)
    assert editor.response_splitter.orientation() is Qt.Orientation.Vertical
    assert isinstance(editor.response_view, ResponseView)
    assert editor.response_view.body_view.isReadOnly()
    assert editor.response_view.headers_view.isReadOnly()
    assert (
        editor.response_view.response_tabs.currentWidget()
        is editor.response_view.body_view
    )
    assert [
        editor.response_view.response_tabs.tabText(index)
        for index in range(editor.response_view.response_tabs.count())
    ] == ["Body", "Headers"]


def test_save_as_adds_new_request_to_existing_collection(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    collection = store.add_collection(CollectionModel(name="Existing"))
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    editor = window.request_editor
    editor.request_name_input.setText("Create record")
    editor.method_input.setCurrentText("POST")
    editor.url_input.setText("https://api.example.test/records")
    editor.body_mode_input.setCurrentText(BodyMode.JSON.value)
    editor.body_input.setPlainText('{"name":"sample"}')
    answers = iter([collection.name])
    monkeypatch.setattr(
        "newpostman.ui.main_window.QInputDialog.getText",
        lambda *_args, **_kwargs: (next(answers), True),
    )

    window.save_request_as()

    saved = store.get_collection(collection.id)
    assert len(saved.requests) == 1
    assert saved.requests[0].name == "Create record"
    assert saved.requests[0].method == "POST"
    assert saved.requests[0].body == '{"name":"sample"}'
    assert not editor.is_dirty


def test_saving_existing_request_updates_collection_entry(
    qtbot: QtBot,
    tmp_path: Path,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    original = RequestModel(
        name="Read record",
        url="https://api.example.test/records/1",
    )
    collection = store.add_collection(
        CollectionModel(name="Records", requests=[original])
    )
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    editor = window.open_collection_request(collection.id, original.id)
    editor.url_input.setText("https://api.example.test/records/2")

    assert window.save_current_request()

    saved = store.get_collection(collection.id)
    assert len(saved.requests) == 1
    assert saved.requests[0].id == original.id
    assert saved.requests[0].url == "https://api.example.test/records/2"
    assert not editor.is_dirty


def test_closing_dirty_request_can_be_cancelled(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    window = MainWindow(
        store=ProjectStore(tmp_path / "project.json"),
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    window.show()
    editor = window.request_editor
    editor.url_input.setText("https://api.example.test/unsaved")
    assert editor.is_dirty
    monkeypatch.setattr(
        "newpostman.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
    )

    window.close()

    assert not window.isHidden()


def test_closing_dirty_request_can_discard_changes(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    window = MainWindow(
        store=ProjectStore(tmp_path / "project.json"),
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    window.show()
    window.request_editor.url_input.setText("https://api.example.test/unsaved")
    monkeypatch.setattr(
        "newpostman.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Discard,
    )

    window.close()

    assert window.isHidden()


def test_closing_dirty_tab_can_be_cancelled(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    window = MainWindow(
        store=ProjectStore(tmp_path / "project.json"),
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    editor = window.request_editor
    editor.url_input.setText("https://api.example.test/unsaved")
    original_count = window.workspace_tabs.count()
    monkeypatch.setattr(
        "newpostman.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
    )

    assert not window.close_workspace_tab(window.workspace_tabs.currentIndex())

    assert window.workspace_tabs.count() == original_count
    assert window.workspace_tabs.currentWidget() is editor


def test_closing_dirty_existing_request_and_saving_persists_changes(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    original = RequestModel(
        name="Read record",
        url="https://api.example.test/records/1",
    )
    collection = store.add_collection(
        CollectionModel(name="Records", requests=[original])
    )
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    window.show()
    editor = window.open_collection_request(collection.id, original.id)
    editor.url_input.setText("https://api.example.test/records/2")
    monkeypatch.setattr(
        "newpostman.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Save,
    )

    window.close()

    saved = store.get_collection(collection.id)
    assert saved.requests[0].url == "https://api.example.test/records/2"
    assert window.isHidden()


def test_closing_dirty_new_request_and_saving_runs_save_as(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    store = ProjectStore(tmp_path / "project.json")
    window = MainWindow(
        store=store,
        client=client_factory(httpx.MockTransport(lambda _: httpx.Response(200))),
    )
    qtbot.addWidget(window)
    window.show()
    editor = window.request_editor
    editor.request_name_input.setText("Create record")
    editor.url_input.setText("https://api.example.test/records")
    monkeypatch.setattr(
        "newpostman.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Save,
    )
    monkeypatch.setattr(
        "newpostman.ui.main_window.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Records", True),
    )

    window.close()

    saved_collection = store.list_collections()[0]
    assert saved_collection.name == "Records"
    assert saved_collection.requests[0].name == "Create record"
    assert window.isHidden()
