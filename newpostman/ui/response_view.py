from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class ResponseView(QWidget):
    """顯示 HTTP 狀態、耗時、Headers 與格式化本文。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """建立唯讀的 Response 資訊檢視。

        Args:
            parent: 可選的 Qt 父元件。
        """
        super().__init__(parent)

        self.status_label = QLabel()
        self.status_label.setObjectName("responseStatus")

        self.elapsed_label = QLabel()
        self.elapsed_label.setObjectName("responseElapsed")

        self.headers_view = QPlainTextEdit()
        self.headers_view.setObjectName("responseHeaders")
        self.headers_view.setReadOnly(True)
        self.headers_view.setMaximumHeight(100)

        self.body_view = QPlainTextEdit()
        self.body_view.setObjectName("responseBody")
        self.body_view.setReadOnly(True)

        summary = QFormLayout()
        summary.addRow("狀態碼", self.status_label)
        summary.addRow("耗時 (ms)", self.elapsed_label)

        response_group = QGroupBox("Response")
        response_layout = QVBoxLayout(response_group)
        response_layout.addLayout(summary)
        response_layout.addWidget(self.headers_view)
        response_layout.addWidget(self.body_view, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(response_group)

    def show_response(
        self,
        *,
        status_code: int,
        elapsed_ms: float,
        headers: Mapping[str, str],
        body_text: str,
    ) -> None:
        """呈現 HTTP Response；JSON 本文以可讀格式顯示。"""
        self.status_label.setText(str(status_code))
        self.elapsed_label.setText(f"{elapsed_ms:.1f}")
        self.headers_view.setPlainText(
            "\n".join(f"{key}: {value}" for key, value in headers.items())
        )
        self.body_view.setPlainText(self._format_body(body_text))

    @staticmethod
    def _format_body(body_text: str) -> str:
        """格式化 JSON 本文；非 JSON 內容保持原文。

        Args:
            body_text: HTTP Response 的文字本文。

        Returns:
            格式化後的 JSON 或未修改的原始文字。
        """
        try:
            body: Any = json.loads(body_text)
        except (json.JSONDecodeError, TypeError):
            return body_text
        return json.dumps(body, ensure_ascii=False, indent=2)
