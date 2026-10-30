from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
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

        self.freshness_label = QLabel("尚無 Response")
        self.freshness_label.setObjectName("responseFreshness")

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

        self.response_tabs = QTabWidget()
        self.response_tabs.setObjectName("responseTabs")
        self.response_tabs.addTab(self.body_view, "Body")
        self.response_tabs.addTab(self.headers_view, "Headers")

        summary = QFormLayout()
        summary.addRow("資料狀態", self.freshness_label)
        summary.addRow("狀態碼", self.status_label)
        summary.addRow("耗時 (ms)", self.elapsed_label)

        response_group = QGroupBox("Response")
        response_layout = QVBoxLayout(response_group)
        response_layout.addLayout(summary)
        response_layout.addWidget(self.response_tabs, 1)

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
        """呈現 HTTP Response；JSON 本文以可讀格式顯示。

        Args:
            status_code: HTTP 狀態碼。
            elapsed_ms: 請求耗時，單位為毫秒。
            headers: Response Headers。
            body_text: Response 原始文字本文。
        """
        self.status_label.setText(str(status_code))
        self.freshness_label.setText("本次請求 Response")
        self.elapsed_label.setText(f"{elapsed_ms:.1f}")
        self.headers_view.setPlainText(
            "\n".join(f"{key}: {value}" for key, value in headers.items())
        )
        self.body_view.setPlainText(self._format_body(body_text))
        self.response_tabs.setCurrentWidget(self.body_view)

    def mark_request_started(self) -> None:
        """保留舊 Response，並明確標示本次請求尚未完成。"""
        if self.status_label.text():
            self.freshness_label.setText("本次請求執行中；以下為上一筆 Response")
        else:
            self.freshness_label.setText("本次請求執行中，尚未收到 Response")

    def mark_request_failed(self) -> None:
        """標示本次請求失敗，避免將舊 Response 誤認為新結果。"""
        if self.status_label.text():
            self.freshness_label.setText("本次請求未收到新 Response；以下為上一筆 Response")
        else:
            self.freshness_label.setText("本次請求未收到 Response")

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
