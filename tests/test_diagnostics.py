from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
from typing import Any

import httpx
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from newpostman.diagnostics import LoggingService
from newpostman.core.project_store import ProjectStore
from newpostman.models.collection import CollectionModel
from newpostman.models.request import RequestModel
from newpostman.ui.diagnostic_panel import DiagnosticPanel
from newpostman.ui.main_window import MainWindow
from newpostman.ui.request_editor import RequestEditor
from newpostman.ui.runner_panel import RunnerPanel


def test_logging_levels_are_independent_and_sensitive_values_are_redacted(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings" / "logging.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"file_level": "DEBUG", "ui_level": "WARNING"}),
        encoding="utf-8",
    )
    service = LoggingService(config_path)
    ui_messages: list[str] = []
    service.bridge.message.connect(ui_messages.append)
    logger = logging.getLogger("newpostman.tests.levels")

    try:
        logger.debug("debug detail")
        logger.info("info detail")
        logger.warning("Authorization: AR-JWT token-secret password=hunter2")

        file_content = service.log_path.read_text(encoding="utf-8")
        assert "debug detail" in file_content
        assert "info detail" in file_content
        assert "WARNING" in file_content
        assert "token-secret" not in file_content
        assert "hunter2" not in file_content
        assert len(ui_messages) == 1
        assert "WARNING" in ui_messages[0]
        assert "token-secret" not in ui_messages[0]
    finally:
        service.close()


def test_default_logging_config_is_created_with_independent_levels(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "logging.json"
    service = LoggingService(config_path)
    try:
        assert json.loads(config_path.read_text(encoding="utf-8")) == {
            "file_level": "DEBUG",
            "ui_level": "INFO",
        }
        assert service.log_path.name == "newpostman.log"
    finally:
        service.close()


def test_unhandled_application_exception_is_recorded_with_traceback(
    tmp_path: Path,
) -> None:
    service = LoggingService(tmp_path / "logging.json")
    try:
        try:
            raise RuntimeError("unexpected application failure")
        except RuntimeError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)

        file_content = service.log_path.read_text(encoding="utf-8")
        assert "未處理的應用程式例外" in file_content
        assert "unexpected application failure" in file_content
        assert "Traceback" in file_content
    finally:
        service.close()


def test_logging_rotation_keeps_configured_number_of_backups(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr("newpostman.diagnostics.MAX_LOG_BYTES", 120)
    config_path = tmp_path / "logging.json"
    service = LoggingService(config_path)
    logger = logging.getLogger("newpostman.tests.rotation")

    try:
        for index in range(12):
            logger.debug("entry-%s %s", index, "x" * 80)
        backups = list(tmp_path.glob("newpostman.log.*"))
        assert len(backups) == 3
        assert service.log_path.exists()
    finally:
        service.close()


def test_script_context_log_appears_in_ui_and_file(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "newpostman.ui.script_warning.QMessageBox.warning",
        lambda *_args: None,
    )
    service = LoggingService(tmp_path / "logging.json")
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"ok": True})
        )
    ) as client:
        editor = RequestEditor(client=client)
        qtbot.addWidget(editor)
        editor.set_request(
            RequestModel(
                name="Check entry",
                url="https://api.example.test/entry",
                before_script='context.log("custom diagnostic")',
                after_script='context.log("after diagnostic")',
            )
        )
        messages: list[str] = []
        service.bridge.message.connect(messages.append)

        try:
            with qtbot.waitSignal(editor.request_succeeded, timeout=3000):
                qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)
            assert any(
                "Script log" in message
                and "Request=Check entry" in message
                and "Before request" in message
                and "custom diagnostic" in message
                for message in messages
            )
            file_content = service.log_path.read_text(encoding="utf-8")
            assert "custom diagnostic" in file_content
            assert "after diagnostic" in file_content
            assert any(
                "After request" in message and "after diagnostic" in message
                for message in messages
            )
        finally:
            service.close()


def test_diagnostic_panel_accumulates_until_cleared(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    service = LoggingService(tmp_path / "logging.json")
    panel = DiagnosticPanel(service.bridge)
    qtbot.addWidget(panel)

    try:
        logging.getLogger("newpostman.tests.panel").warning("visible warning")
        qtbot.waitUntil(
            lambda: "visible warning" in panel.log_view.toPlainText(),
            timeout=3000,
        )
        assert "visible warning" in panel.log_view.toPlainText()
        qtbot.mouseClick(panel.clear_button, Qt.MouseButton.LeftButton)
        assert panel.log_view.toPlainText() == ""
    finally:
        service.close()


def test_response_view_marks_previous_response_during_new_send(
    qtbot: QtBot,
) -> None:
    send_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal send_count
        send_count += 1
        if send_count == 1:
            return httpx.Response(200, text="previous result")
        raise httpx.ConnectError("connection refused")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        editor = RequestEditor(client=client)
        qtbot.addWidget(editor)
        editor.url_input.setText("https://api.example.test/entry")

        with qtbot.waitSignal(editor.request_succeeded, timeout=3000):
            qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)
        assert editor.response_view.freshness_label.text() == "本次請求 Response"

        with qtbot.waitSignal(editor.request_failed, timeout=3000):
            qtbot.mouseClick(editor.send_button, Qt.MouseButton.LeftButton)
        assert "未收到新 Response" in editor.response_view.freshness_label.text()
        assert editor.response_view.body_view.toPlainText() == "previous result"


def test_runner_logs_are_forwarded_to_common_diagnostic_panel(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "newpostman.ui.script_warning.QMessageBox.warning",
        lambda *_args: None,
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="done"))
    ) as client:
        service = LoggingService(tmp_path / "logging.json")
        store = ProjectStore(tmp_path / "project.json")
        store.add_collection(
            CollectionModel(
                name="Diagnostics",
                requests=[
                    RequestModel(
                        name="Logged request",
                        url="https://api.example.test/entry",
                        before_script='context.log("runner custom message")',
                    )
                ],
            )
        )
        window = MainWindow(store=store, client=client, logging_service=service)
        qtbot.addWidget(window)

        try:
            diagnostic_panel = window.diagnostic_panel
            assert isinstance(diagnostic_panel, DiagnosticPanel)
            qtbot.mouseClick(window.run_button, Qt.MouseButton.LeftButton)
            panel = window.workspace_tabs.currentWidget()
            assert isinstance(panel, RunnerPanel)
            with qtbot.waitSignal(panel.runner.run_finished, timeout=3000):
                qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)
            qtbot.waitUntil(
                lambda: "runner custom message"
                in diagnostic_panel.log_view.toPlainText(),
                timeout=3000,
            )
            diagnostics = diagnostic_panel.log_view.toPlainText()
            assert "開始執行 Collection" in diagnostics
            assert "runner custom message" in diagnostics
            assert "HTTP response received" in diagnostics
            assert "https://api.example.test/entry" in diagnostics
        finally:
            service.close()
