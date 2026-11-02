from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any

import httpx
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem
from pytestqt.qtbot import QtBot

from newpostman.core.collection_runner import CollectionRunner, RunItemResult
from newpostman.core.project_store import ProjectStore
from newpostman.models.collection import CollectionModel
from newpostman.models.environment import EnvironmentModel
from newpostman.models.request import (
    BodyMode,
    ExtractorModel,
    ExtractorType,
    RequestModel,
)
from newpostman.models.run_context import RunContext
from newpostman.ui.main_window import MainWindow
from newpostman.ui.request_editor import RequestEditor


@pytest.fixture
def client_factory() -> Iterator[Callable[[httpx.BaseTransport], httpx.Client]]:
    """提供由 fixture 關閉的 HTTPX Client 工廠。"""
    with ExitStack() as stack:

        def create_client(transport: httpx.BaseTransport) -> httpx.Client:
            """建立並註冊 MockTransport Client。"""
            return stack.enter_context(httpx.Client(transport=transport))

        yield create_client


def test_runner_chains_scripts_and_extractors_with_runtime_precedence(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path == "/runtime-path/edited":
            return httpx.Response(
                200,
                json={"tokens": ["first-token", "second-token"]},
            )
        return httpx.Response(200, json={"result": "complete"})

    collection = CollectionModel(
        name="Script chain",
        requests=[
            RequestModel(
                name="Authenticate",
                method="GET",
                url="https://{{host}}/{{path}}",
                before_script=(
                    "context.runtime_variables['path'] = 'runtime-path'\n"
                    "context.request.url += '/edited'\n"
                    "context.request.headers['X-Before'] = 'ran'"
                ),
                extractors=[
                    ExtractorModel(
                        variable_name="token",
                        kind=ExtractorType.JSONPATH,
                        expression="$.tokens[*]",
                    )
                ],
            ),
            RequestModel(
                name="Fetch protected resource",
                method="GET",
                url="https://{{host}}/protected",
                headers={"Authorization": "Bearer {{token}}"},
                after_script=(
                    "assert context.response is not None\n"
                    "context.runtime_variables['after_status'] = "
                    "str(context.response.status_code)"
                ),
                extractors=[
                    ExtractorModel(
                        variable_name="result",
                        kind=ExtractorType.JSONPATH,
                        expression="$.result",
                    )
                ],
            ),
            RequestModel(
                name="Verify chain values",
                method="GET",
                url="https://{{host}}/verify",
                headers={
                    "X-Token": "{{token}}",
                    "X-After": "{{after_status}}",
                    "X-Result": "{{result}}",
                },
            ),
        ],
    )
    environment = EnvironmentModel(
        name="Development",
        variables={"host": "api.example.test", "path": "base"},
    )
    runner = CollectionRunner(client=client_factory(httpx.MockTransport(handler)))
    results: list[RunItemResult] = []
    runner.request_completed.connect(results.append)

    summary = runner.run(collection, environment)

    assert [str(request.url) for request in sent] == [
        "https://api.example.test/runtime-path/edited",
        "https://api.example.test/protected",
        "https://api.example.test/verify",
    ]
    assert sent[0].headers["x-before"] == "ran"
    assert sent[1].headers["authorization"] == "Bearer first-token"
    assert sent[2].headers["x-token"] == "first-token"
    assert sent[2].headers["x-after"] == "200"
    assert sent[2].headers["x-result"] == "complete"
    assert results[0].result.error is None
    assert summary.succeeded == 3
    assert summary.failed == 0


def test_variable_resolution_prioritizes_data_row_then_runtime_then_environment(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    received_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_urls.append(str(request.url))
        return httpx.Response(200)

    collection = CollectionModel(
        name="Variable priority",
        requests=[RequestModel(name="Resolve", url="https://{{host}}/")],
    )
    context = RunContext(
        environment=EnvironmentModel(name="Development", variables={"host": "env"}),
        runtime_variables={"host": "runtime"},
        data_row={"host": "row"},
    )
    runner = CollectionRunner(client=client_factory(httpx.MockTransport(handler)))

    summary = runner.run(collection, run_context=context)

    assert summary.succeeded == 1
    assert received_urls == ["https://row/"]


def test_script_failures_are_reported_but_after_script_still_extracts_and_runner_continues(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_paths.append(request.url.path)
        return httpx.Response(200, json={"value": "extracted"})

    collection = CollectionModel(
        name="Script failures",
        requests=[
            RequestModel(
                name="Before failure",
                url="https://api.example.test/blocked",
                before_script="raise ValueError('before failed')",
            ),
            RequestModel(
                name="After failure",
                url="https://api.example.test/after",
                after_script="raise RuntimeError('after failed')",
                extractors=[
                    ExtractorModel(
                        variable_name="value",
                        kind=ExtractorType.JSONPATH,
                        expression="$.value",
                    )
                ],
            ),
            RequestModel(
                name="Use extraction",
                url="https://api.example.test/{{value}}",
            ),
        ],
    )
    runner = CollectionRunner(client=client_factory(httpx.MockTransport(handler)))
    results: list[RunItemResult] = []
    runner.request_completed.connect(results.append)

    summary = runner.run(collection)

    assert sent_paths == ["/after", "/extracted"]
    assert results[0].result.error is not None
    assert "Before request Script" in results[0].result.error
    assert results[1].result.response is not None
    assert results[1].result.error is not None
    assert "After request Script" in results[1].result.error
    assert summary.failed == 2
    assert summary.succeeded == 1


def test_regex_extractor_uses_configured_group_and_invalid_extractors_preserve_value(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    received_paths: list[str] = []

    regex_request = RequestModel(
        name="Extract regex values",
        url="https://api.example.test/regex",
        extractors=[
            ExtractorModel(
                variable_name="code",
                kind=ExtractorType.REGEX,
                expression=r"code=(\w+)-(\d+)",
                group_index=2,
            ),
            ExtractorModel(
                variable_name="code_default",
                kind=ExtractorType.REGEX,
                expression=r"code=(\w+)-(\d+)",
            ),
            ExtractorModel(
                variable_name="code",
                kind=ExtractorType.JSONPATH,
                expression="$.missing",
            ),
            ExtractorModel(
                variable_name="code",
                kind=ExtractorType.REGEX,
                expression="[",
            ),
            ExtractorModel(
                variable_name="optional",
                kind=ExtractorType.REGEX,
                expression=r"(prefix:)?code=(\w+)",
                group_index=1,
            ),
        ],
    )
    json_request = RequestModel(
        name="Extract JSONPath values",
        url="https://api.example.test/json",
        extractors=[
            ExtractorModel(
                variable_name="token",
                kind=ExtractorType.JSONPATH,
                expression="$.tokens[*]",
            ),
            ExtractorModel(
                variable_name="token",
                kind=ExtractorType.JSONPATH,
                expression="$.missing",
            ),
            ExtractorModel(
                variable_name="token",
                kind=ExtractorType.JSONPATH,
                expression="[",
            ),
        ],
    )
    following_request = RequestModel(
        name="Use successful extraction",
        url=(
            "https://api.example.test/{{code}}/{{code_default}}/"
            "{{token}}/{{optional}}"
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        received_paths.append(request.url.path)
        if request.url.path == "/json":
            return httpx.Response(200, json={"tokens": ["first", "second"]})
        return httpx.Response(200, text="code=abc-42")

    client = client_factory(httpx.MockTransport(handler))
    runner = CollectionRunner(client=client)
    results: list[RunItemResult] = []
    runner.request_completed.connect(results.append)

    summary = runner.run(
        CollectionModel(
            name="Regex",
            requests=[regex_request, json_request, following_request],
        ),
        run_context=RunContext(
            runtime_variables={"code": "existing", "optional": "preserved"}
        ),
    )

    assert summary.succeeded == 3
    assert results[2].request_name == "Use successful extraction"
    assert received_paths == [
        "/regex",
        "/json",
        "/42/abc/first/preserved",
    ]
    assert len(results[0].result.warnings) == 3
    assert len(results[1].result.warnings) == 2
    assert any(
        "optional" in warning and "未參與" in warning
        for warning in results[0].result.warnings
    )
    assert results[0].result.error is None
    assert results[1].result.error is None


def test_request_editor_exposes_scripts_without_security_popup(
    qtbot: QtBot,
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[tuple[str, str]] = []
    sent_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_headers.append(request.headers)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, text: warnings.append((title, text)),
    )
    client = client_factory(httpx.MockTransport(handler))
    editor = RequestEditor(client=client)
    qtbot.addWidget(editor)
    editor.url_input.setText("https://api.example.test/")

    assert editor.request_tabs.count() == 4
    assert editor.request_tabs.tabText(3) == "腳本"
    editor.before_script_input.setPlainText("context.request.headers['X-Test'] = '1'")
    editor.after_script_input.setPlainText("context.runtime_variables['done'] = 'yes'")
    qtbot.mouseClick(editor.add_extractor_button, Qt.MouseButton.LeftButton)
    editor.extractor_table.setItem(0, 0, QTableWidgetItem("answer"))
    editor.extractor_table.setItem(0, 2, QTableWidgetItem("$.answer"))
    request = editor.build_request()
    assert request.before_script
    assert request.after_script
    assert request.extractors[0].variable_name == "answer"
    editor.set_request(request)
    assert editor.build_request() == request

    with qtbot.waitSignal(editor.request_succeeded, timeout=3000):
        qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)

    assert not warnings
    assert "受信任程式碼" in editor.script_trust_notice.text()
    assert "不提供沙箱隔離" in editor.script_trust_notice.text()
    assert sent_headers[0]["x-test"] == "1"


def test_jsonpath_object_property_is_available_to_next_request_body(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent_requests: list[httpx.Request] = []
    record_url = (
        "https://mvdis-solarwinds.mvdis.gov.tw/ui/maps/viewer/MAPS-123"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        sent_requests.append(request)
        if request.url.path == "/entry":
            return httpx.Response(
                200,
                json={"values": {"url": record_url}},
            )
        return httpx.Response(200, json={"updated": True})

    collection = CollectionModel(
        name="Object JSONPath extraction",
        requests=[
            RequestModel(
                name="Get entry",
                method="GET",
                url="https://api.example.test/entry",
                extractors=[
                    ExtractorModel(
                        variable_name="record_url",
                        kind=ExtractorType.JSONPATH,
                        expression="$.values.url",
                    )
                ],
            ),
            RequestModel(
                name="Update entry",
                method="PUT",
                url="https://api.example.test/entry/modify",
                body_mode=BodyMode.JSON,
                body='{"values":{"url":"{{record_url}}"}}',
            ),
        ],
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )

    summary = runner.run(collection)

    assert summary.succeeded == 2
    assert summary.failed == 0
    assert len(sent_requests) == 2
    assert json.loads(sent_requests[1].content) == {
        "values": {"url": record_url}
    }


def test_before_script_variables_are_rendered_in_current_request(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_requests.append(request)
        return httpx.Response(200, json={"ok": True})

    request = RequestModel(
        name="Set request variables",
        method="POST",
        url="https://{{host}}/{{path}}",
        headers={"X-{{header_name}}": "{{header_value}}"},
        params={"{{param_name}}": "{{param_value}}"},
        body_mode=BodyMode.JSON,
        body='{"value":"{{body_value}}"}',
        before_script=(
            "assert context.request.url == 'https://{{host}}/{{path}}'\n"
            "assert context.request.body == '{\"value\":\"{{body_value}}\"}'\n"
            "context.runtime_variables.update({\n"
            "    'path': 'script-path',\n"
            "    'header_name': 'script-header',\n"
            "    'header_value': 'header-from-script',\n"
            "    'param_name': 'script-param',\n"
            "    'param_value': 'param-from-script',\n"
            "    'body_value': 'body-from-script',\n"
            "})"
        ),
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )

    summary = runner.run(
        CollectionModel(name="Before script interpolation", requests=[request]),
        EnvironmentModel(name="Development", variables={"host": "api.example.test"}),
    )

    assert summary.succeeded == 1
    assert summary.failed == 0
    assert len(sent_requests) == 1
    sent = sent_requests[0]
    assert str(sent.url) == (
        "https://api.example.test/script-path?script-param=param-from-script"
    )
    assert sent.headers["x-script-header"] == "header-from-script"
    assert json.loads(sent.content) == {"value": "body-from-script"}


def test_before_script_can_resolve_missing_variable_before_sending(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_urls.append(str(request.url))
        return httpx.Response(200)

    request = RequestModel(
        name="Resolve missing variable",
        url="https://api.example.test/{{path}}",
        before_script="context.runtime_variables['path'] = 'resolved'",
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )

    summary = runner.run(
        CollectionModel(name="Resolve before interpolation", requests=[request])
    )

    assert summary.succeeded == 1
    assert summary.failed == 0
    assert sent_urls == ["https://api.example.test/resolved"]


def test_before_script_does_not_override_data_row_variable(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_urls.append(str(request.url))
        return httpx.Response(200)

    request = RequestModel(
        name="Data row precedence",
        url="https://api.example.test/{{value}}",
        before_script="context.runtime_variables['value'] = 'runtime'",
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )

    summary = runner.run(
        CollectionModel(name="Data row precedence", requests=[request]),
        dataset_rows=[{"value": "row"}],
    )

    assert summary.succeeded == 1
    assert summary.failed == 0
    assert sent_urls == ["https://api.example.test/row"]


def test_before_script_leaves_unresolved_variable_as_error(
    client_factory: Callable[[httpx.BaseTransport], httpx.Client],
) -> None:
    sent_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_urls.append(str(request.url))
        return httpx.Response(200)

    request = RequestModel(
        name="Still missing",
        url="https://api.example.test/{{missing}}",
        before_script="context.runtime_variables['other'] = 'value'",
    )
    runner = CollectionRunner(
        client=client_factory(httpx.MockTransport(handler))
    )
    results: list[RunItemResult] = []
    runner.request_completed.connect(results.append)

    summary = runner.run(
        CollectionModel(name="Unresolved after script", requests=[request])
    )

    assert summary.succeeded == 0
    assert summary.failed == 1
    assert sent_urls == []
    assert results[0].result.error is not None
    assert "{{missing}}" in results[0].result.error
