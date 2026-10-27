from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any

import httpx
import pytest
from PySide6.QtCore import Qt

from newpostman.models.request import BodyMode, RequestModel
from newpostman.ui.request_editor import RequestEditor
from newpostman.ui.response_view import ResponseView


@pytest.fixture
def client_factory() -> Iterator[Callable[[httpx.BaseTransport], httpx.Client]]:
    """建立由 fixture context manager 統一管理生命週期的 HTTP Client。"""
    with ExitStack() as stack:

        def create_client(transport: httpx.BaseTransport) -> httpx.Client:
            """建立並註冊一個由 fixture 關閉的 HTTP Client。"""
            return stack.enter_context(httpx.Client(transport=transport))

        yield create_client


def test_request_model_accepts_supported_body_modes() -> None:
    request = RequestModel(
        name="Create item",
        method="POST",
        url="https://api.example.test/items",
        headers={"X-Trace": "trace-1"},
        params={"dry_run": "true"},
        body_mode=BodyMode.JSON,
        body='{"name": "sample"}',
    )

    assert request.method == "POST"
    assert request.body_mode is BodyMode.JSON
    assert request.headers == {"X-Trace": "trace-1"}
    assert request.params == {"dry_run": "true"}


@pytest.mark.parametrize(
    ("body_mode", "body", "expected_json", "expected_content"),
    [
        (BodyMode.NONE, "ignored", None, b""),
        (BodyMode.JSON, '{"name":"sample"}', {"name": "sample"}, b'{"name":"sample"}'),
        (BodyMode.RAW, "plain text", None, b"plain text"),
    ],
)
def test_request_editor_sends_selected_body_mode(
    qtbot: Any,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
    body_mode: BodyMode,
    body: str,
    expected_json: Any,
    expected_content: bytes,
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["content"] = request.content
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = client_factory(transport)
    editor = RequestEditor(client=client)
    qtbot.addWidget(editor)
    editor.method_input.setCurrentText("POST")
    editor.url_input.setText("https://api.example.test/items?existing=1")
    editor.headers_input.setPlainText("X-Trace: trace-1")
    editor.params_input.setPlainText("page=2\nq=two words")
    editor.body_mode_input.setCurrentText(body_mode.value)
    editor.body_input.setPlainText(body)

    with qtbot.waitSignal(editor.request_succeeded, timeout=3000):
        qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)

    assert captured["method"] == "POST"
    assert captured["url"] == (
        "https://api.example.test/items?existing=1&page=2&q=two+words"
    )
    assert captured["headers"]["x-trace"] == "trace-1"
    assert captured["content"] == expected_content
    if expected_json is None:
        assert "application/json" not in captured["headers"].get("content-type", "")
    else:
        assert json.loads(captured["content"]) == expected_json
        assert captured["headers"]["content-type"] == "application/json"


def test_invalid_json_body_is_not_sent(
    qtbot: Any,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    send_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal send_count
        send_count += 1
        return httpx.Response(200)

    client = client_factory(httpx.MockTransport(handler))
    editor = RequestEditor(client=client)
    qtbot.addWidget(editor)
    editor.method_input.setCurrentText("POST")
    editor.url_input.setText("https://api.example.test/items")
    editor.body_mode_input.setCurrentText(BodyMode.JSON.value)
    editor.body_input.setPlainText('{"broken":')

    with qtbot.waitSignal(editor.request_failed, timeout=3000) as signal:
        qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)

    assert send_count == 0
    assert "JSON" in signal.args[0]


def test_response_view_formats_json_and_preserves_plain_text(qtbot: Any) -> None:
    view = ResponseView()
    qtbot.addWidget(view)

    view.show_response(
        status_code=201,
        elapsed_ms=12.5,
        headers={"content-type": "application/json"},
        body_text='{"ok":true,"count":1}',
    )

    assert "201" in view.status_label.text()
    assert "12.5" in view.elapsed_label.text()
    assert json.loads(view.body_view.toPlainText()) == {"ok": True, "count": 1}

    view.show_response(
        status_code=418,
        elapsed_ms=2.0,
        headers={"content-type": "text/plain"},
        body_text="plain response",
    )

    assert "418" in view.status_label.text()
    assert view.body_view.toPlainText() == "plain response"


def test_http_error_response_is_displayed_not_transport_error(
    qtbot: Any,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    client = client_factory(
        httpx.MockTransport(lambda _: httpx.Response(503, text="service unavailable"))
    )
    editor = RequestEditor(client=client)
    qtbot.addWidget(editor)
    editor.url_input.setText("https://api.example.test/unavailable")

    with qtbot.waitSignal(editor.request_succeeded, timeout=3000):
        qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)

    assert "503" in editor.response_view.status_label.text()
    assert editor.response_view.body_view.toPlainText() == "service unavailable"
    assert "error" not in editor.error_label.text().lower()


def test_transport_error_is_shown_without_crashing(
    qtbot: Any,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    client = client_factory(
        httpx.MockTransport(
            lambda _: (_ for _ in ()).throw(httpx.ConnectError("connection refused"))
        )
    )
    editor = RequestEditor(client=client)
    qtbot.addWidget(editor)
    editor.url_input.setText("https://api.example.test/offline")

    with qtbot.waitSignal(editor.request_failed, timeout=3000) as signal:
        qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)

    assert "connection refused" in signal.args[0].lower()
    assert editor.error_label.text()
