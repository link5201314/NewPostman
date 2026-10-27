from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtWidgets import QMessageBox


@pytest.fixture(autouse=True)
def discard_unsaved_changes_during_test_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """測試清理 Qt 視窗時預設放棄未儲存變更，避免彈出互動對話框。"""
    original_question = QMessageBox.question

    def answer_question(*args: Any, **kwargs: Any) -> QMessageBox.StandardButton:
        if len(args) > 1 and args[1] == "未儲存的 Request":
            return QMessageBox.StandardButton.Discard
        return original_question(*args, **kwargs)

    monkeypatch.setattr(QMessageBox, "question", answer_question)
