from __future__ import annotations

import httpx
from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from newpostman.core.api_engine import ApiEngine
from newpostman.models.environment import EnvironmentModel
from newpostman.models.request import BodyMode, RequestModel
from newpostman.ui.response_view import ResponseView


class RequestEditor(QWidget):
    """提供單次 Request 編輯、發送及 Response 呈現。"""

    request_succeeded = Signal(object)
    request_failed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        """初始化 Request 編輯表單與單次請求引擎。

        Args:
            parent: 可選的 Qt 父元件。
            client: 可選的 HTTPX Client；傳入時由呼叫端管理其生命週期。
        """
        super().__init__(parent)
        self.setWindowTitle("NewPostman - 單次 Request")
        self._engine = ApiEngine(client=client)
        self._environment: EnvironmentModel | None = None

        self.method_input = QComboBox()
        self.method_input.setObjectName("requestMethod")
        self.method_input.addItems(
            ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
        )

        self.url_input = QLineEdit()
        self.url_input.setObjectName("requestUrl")
        self.url_input.setPlaceholderText("https://api.example.com/resource")

        self.headers_input = QPlainTextEdit()
        self.headers_input.setObjectName("requestHeaders")
        self.headers_input.setPlaceholderText(
            "每行一個 Header，例如：\nAccept: application/json"
        )
        self.headers_input.setMaximumHeight(80)

        self.params_input = QPlainTextEdit()
        self.params_input.setObjectName("requestParams")
        self.params_input.setPlaceholderText("每行一個參數，例如：\npage=1")
        self.params_input.setMaximumHeight(80)

        self.body_mode_input = QComboBox()
        self.body_mode_input.setObjectName("requestBodyMode")
        for mode in BodyMode:
            self.body_mode_input.addItem(mode.value, mode)

        self.body_input = QPlainTextEdit()
        self.body_input.setObjectName("requestBody")
        self.body_input.setPlaceholderText("Request Body")

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendRequest")
        self.send_button.clicked.connect(self.send_request)

        self.error_label = QLabel()
        self.error_label.setObjectName("requestError")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b42318;")

        self.response_view = ResponseView()

        form = QFormLayout()
        form.addRow("Method", self.method_input)
        form.addRow("URL", self.url_input)
        form.addRow("Headers", self.headers_input)
        form.addRow("Params", self.params_input)
        form.addRow("Body mode", self.body_mode_input)
        form.addRow("Body", self.body_input)

        send_row = QHBoxLayout()
        send_row.addStretch()
        send_row.addWidget(self.send_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(send_row)
        layout.addWidget(self.error_label)
        layout.addWidget(self.response_view, 1)

    def build_request(self) -> RequestModel:
        """讀取並驗證目前表單內容。"""
        url = self.url_input.text().strip()
        if not url:
            raise ValueError("請輸入 URL。")

        body_mode = self.body_mode_input.currentData()
        if not isinstance(body_mode, BodyMode):
            body_mode = BodyMode(self.body_mode_input.currentText())

        return RequestModel(
            method=self.method_input.currentText(),
            url=url,
            headers=self._parse_headers(self.headers_input.toPlainText()),
            params=self._parse_params(self.params_input.toPlainText()),
            body_mode=body_mode,
            body=self.body_input.toPlainText(),
        )

    def set_environment(self, environment: EnvironmentModel | None) -> None:
        """設定此編輯器發送請求時使用的 Environment。

        Args:
            environment: 作用中的 Environment；None 表示沒有可用變數。
        """
        self._environment = environment

    @staticmethod
    def _parse_headers(raw_text: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        for line_number, line in enumerate(raw_text.splitlines(), start=1):
            if not line.strip():
                continue
            name, separator, value = line.partition(":")
            if not separator or not name.strip():
                raise ValueError(
                    f"第 {line_number} 行 Header 格式錯誤，請使用名稱: 值。"
                )
            headers[name.strip()] = value.strip()
        return headers

    @staticmethod
    def _parse_params(raw_text: str) -> dict[str, str]:
        params: dict[str, str] = {}
        for line_number, line in enumerate(raw_text.splitlines(), start=1):
            if not line.strip():
                continue
            name, separator, value = line.partition("=")
            if not separator or not name.strip():
                raise ValueError(f"第 {line_number} 行 Param 格式錯誤，請使用名稱=值。")
            params[name.strip()] = value.strip()
        return params

    def send_request(self) -> None:
        """發送表單中的 Request 並更新視圖及訊號。"""
        self.send_button.setEnabled(False)
        self.error_label.clear()
        try:
            request = self.build_request()
            result = self._engine.execute(request, self._environment)
        except (ValueError, httpx.InvalidURL) as exc:
            self._show_error(str(exc))
            return
        finally:
            self.send_button.setEnabled(True)

        if result.error is not None:
            self._show_error(result.error)
            return
        if result.response is None:
            self._show_error("Request 未產生 Response。")
            return

        response = result.response
        self.response_view.show_response(
            status_code=response.status_code,
            elapsed_ms=response.elapsed_ms,
            headers=response.headers,
            body_text=response.body_text,
        )
        self.request_succeeded.emit(response)

    def _show_error(self, message: str) -> None:
        """顯示請求錯誤並通知訂閱者。

        Args:
            message: 要呈現的錯誤訊息。
        """
        self.error_label.setText(message)
        self.request_failed.emit(message)

    def closeEvent(self, event: QCloseEvent) -> None:
        """在視窗關閉時釋放由引擎持有的 HTTP 資源。

        Args:
            event: Qt 傳入的關閉事件。
        """
        self._engine.close()
        super().closeEvent(event)
