from __future__ import annotations

import logging
from uuid import UUID, uuid4

import httpx
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from newpostman.core.api_engine import ApiEngine
from newpostman.models.environment import EnvironmentModel
from newpostman.models.request import (
    BodyMode,
    ExtractorModel,
    ExtractorType,
    RequestModel,
)
from newpostman.ui.script_warning import warn_about_trusted_scripts
from newpostman.ui.response_view import ResponseView

logger = logging.getLogger(__name__)


class RequestEditor(QWidget):
    """提供單次 Request 編輯、發送及 Response 呈現。"""

    request_succeeded = Signal(object)
    request_failed = Signal(str)
    request_changed = Signal()

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
        self._collection_id: str | None = None
        self._saved_request: RequestModel | None = None
        self._loading_request = False
        self._request_id: UUID = uuid4()

        self.request_name_input = QLineEdit("Untitled request")
        self.request_name_input.setObjectName("requestName")
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

        self.before_script_input = QPlainTextEdit()
        self.before_script_input.setObjectName("beforeRequestScript")
        self.before_script_input.setPlaceholderText(
            "可使用 context.request 與 context.runtime_variables"
        )
        self.after_script_input = QPlainTextEdit()
        self.after_script_input.setObjectName("afterRequestScript")
        self.after_script_input.setPlaceholderText(
            "可使用 context.response、context.request 與 context.runtime_variables"
        )
        self.extractor_table = QTableWidget(0, 4)
        self.extractor_table.setObjectName("requestExtractors")
        self.extractor_table.setHorizontalHeaderLabels(
            ["執行期變數", "類型", "運算式", "捕獲群組"]
        )
        self.extractor_table.horizontalHeader().setStretchLastSection(True)
        self.add_extractor_button = QPushButton("新增 Extractor")
        self.add_extractor_button.setObjectName("addExtractor")
        self.add_extractor_button.clicked.connect(self._add_extractor_row)
        self.remove_extractor_button = QPushButton("刪除 Extractor")
        self.remove_extractor_button.setObjectName("removeExtractor")
        self.remove_extractor_button.clicked.connect(self._remove_extractor_row)
        self.script_trust_notice = QLabel(
            "安全提醒：Python Script 是受信任程式碼，可執行一般 Python 能力，"
            "包括存取本機檔案；本程式不提供沙箱隔離。"
        )
        self.script_trust_notice.setObjectName("scriptTrustNotice")
        self.script_trust_notice.setWordWrap(True)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendRequest")
        self.send_button.clicked.connect(self.send_request)

        self.error_label = QLabel()
        self.error_label.setObjectName("requestError")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b42318;")

        self.response_view = ResponseView()

        request_line = QHBoxLayout()
        request_line.addWidget(self.method_input)
        request_line.addWidget(self.url_input, 1)

        self.request_tabs = QTabWidget()
        self.request_tabs.setObjectName("requestTabs")
        self.request_tabs.addTab(self.params_input, "Params")
        self.request_tabs.addTab(self.headers_input, "Headers")

        body_page = QWidget()
        body_layout = QVBoxLayout(body_page)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.body_mode_input)
        body_layout.addWidget(self.body_input, 1)
        self.request_tabs.addTab(body_page, "Body")

        scripts_page = QWidget()
        scripts_layout = QVBoxLayout(scripts_page)
        scripts_layout.addWidget(QLabel("執行前 Script"))
        scripts_layout.addWidget(self.before_script_input, 1)
        scripts_layout.addWidget(QLabel("執行後 Script"))
        scripts_layout.addWidget(self.after_script_input, 1)
        scripts_layout.addWidget(QLabel("Response 萃取器"))
        scripts_layout.addWidget(self.extractor_table, 1)
        extractor_controls = QHBoxLayout()
        extractor_controls.addWidget(self.add_extractor_button)
        extractor_controls.addWidget(self.remove_extractor_button)
        extractor_controls.addStretch()
        scripts_layout.addLayout(extractor_controls)
        scripts_layout.addWidget(self.script_trust_notice)
        self.request_tabs.addTab(scripts_page, "腳本")

        send_row = QHBoxLayout()
        send_row.addStretch()
        send_row.addWidget(self.send_button)

        request_panel = QWidget()
        request_layout = QVBoxLayout(request_panel)
        request_layout.setContentsMargins(8, 8, 8, 8)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Request"))
        name_row.addWidget(self.request_name_input, 1)
        request_layout.addLayout(name_row)
        request_layout.addLayout(request_line)
        request_layout.addWidget(self.request_tabs, 1)
        request_layout.addWidget(self.error_label)
        request_layout.addLayout(send_row)

        self.response_splitter = QSplitter(Qt.Orientation.Vertical)
        self.response_splitter.setObjectName("requestResponseSplitter")
        self.response_splitter.addWidget(request_panel)
        self.response_splitter.addWidget(self.response_view)
        self.response_splitter.setStretchFactor(0, 3)
        self.response_splitter.setStretchFactor(1, 2)
        self.response_splitter.setSizes([420, 300])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.response_splitter, 1)

        for widget in (
            self.request_name_input,
            self.url_input,
            self.headers_input,
            self.params_input,
            self.body_input,
        ):
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._mark_request_changed)
            else:
                widget.textChanged.connect(self._mark_request_changed)
        self.method_input.currentTextChanged.connect(self._mark_request_changed)
        self.body_mode_input.currentIndexChanged.connect(self._mark_request_changed)
        self.before_script_input.textChanged.connect(self._mark_request_changed)
        self.after_script_input.textChanged.connect(self._mark_request_changed)
        self.extractor_table.cellChanged.connect(self._mark_request_changed)

    @property
    def is_dirty(self) -> bool:
        """目前 Request 是否與最後儲存版本不同。"""
        if self._loading_request:
            return False
        try:
            return self._request_snapshot() != self._saved_request
        except ValueError:
            return True

    @property
    def collection_id(self) -> str | None:
        """取得此編輯器所屬 Collection 識別碼。"""
        return self._collection_id

    @property
    def saved_request(self) -> RequestModel | None:
        """取得最後載入或儲存的 Request 快照。"""
        return (
            self._saved_request.model_copy(deep=True) if self._saved_request else None
        )

    def set_request(
        self,
        request: RequestModel,
        *,
        collection_id: str | None = None,
    ) -> None:
        """載入 Request 設定並記錄其儲存基準。

        Args:
            request: 要顯示的 Request 設定。
            collection_id: Request 所屬 Collection；尚未儲存時為 None。
        """
        self._loading_request = True
        self._request_id = request.id
        self.request_name_input.setText(request.name)
        self.method_input.setCurrentText(request.method.upper())
        self.url_input.setText(request.url)
        self.headers_input.setPlainText(
            "\n".join(f"{key}: {value}" for key, value in request.headers.items())
        )
        self.params_input.setPlainText(
            "\n".join(f"{key}={value}" for key, value in request.params.items())
        )
        self.body_mode_input.setCurrentIndex(
            self.body_mode_input.findData(request.body_mode)
        )
        self.body_input.setPlainText(request.body)
        self.before_script_input.setPlainText(request.before_script)
        self.after_script_input.setPlainText(request.after_script)
        self._set_extractors(request.extractors)
        self._collection_id = collection_id
        self._saved_request = request.model_copy(deep=True)
        self._loading_request = False

    def mark_saved(self, request: RequestModel, collection_id: str) -> None:
        """更新 Request 的已儲存基準。

        Args:
            request: 剛儲存的 Request。
            collection_id: 儲存該 Request 的 Collection 識別碼。
        """
        self._saved_request = request.model_copy(deep=True)
        self._request_id = request.id
        self._collection_id = collection_id

    def _mark_request_changed(self, *_args: object) -> None:
        """表單欄位改變時通知主視窗更新 dirty 狀態。

        Args:
            *_args: Qt 控制項變更訊號附帶的值。
        """
        if not self._loading_request:
            self.request_changed.emit()

    def build_request(self) -> RequestModel:
        """讀取並驗證目前表單內容。"""
        url = self.url_input.text().strip()
        if not url:
            raise ValueError("請輸入 URL。")
        return self._request_snapshot()

    def _request_snapshot(self) -> RequestModel:
        """建立目前表單資料快照，不執行發送前的 URL 驗證。"""
        url = self.url_input.text().strip()

        body_mode = self.body_mode_input.currentData()
        if not isinstance(body_mode, BodyMode):
            body_mode = BodyMode(self.body_mode_input.currentText())

        return RequestModel(
            id=self._request_id,
            name=self.request_name_input.text().strip() or "Untitled request",
            method=self.method_input.currentText(),
            url=url,
            headers=self._parse_headers(self.headers_input.toPlainText()),
            params=self._parse_params(self.params_input.toPlainText()),
            body_mode=body_mode,
            body=self.body_input.toPlainText(),
            before_script=self.before_script_input.toPlainText(),
            after_script=self.after_script_input.toPlainText(),
            extractors=self._extractor_snapshot(),
        )

    def _set_extractors(self, extractors: list[ExtractorModel]) -> None:
        """將 Request Extractors 載入表格。"""
        self.extractor_table.blockSignals(True)
        self.extractor_table.setRowCount(0)
        for extractor in extractors:
            row = self.extractor_table.rowCount()
            self.extractor_table.insertRow(row)
            self.extractor_table.setItem(
                row, 0, QTableWidgetItem(extractor.variable_name)
            )
            kind_selector = self._create_extractor_type_selector(extractor.kind)
            self.extractor_table.setCellWidget(row, 1, kind_selector)
            self.extractor_table.setItem(row, 2, QTableWidgetItem(extractor.expression))
            self.extractor_table.setItem(
                row, 3, QTableWidgetItem(str(extractor.group_index))
            )
        self.extractor_table.blockSignals(False)

    def _extractor_snapshot(self) -> list[ExtractorModel]:
        """讀取並驗證 Extractor 表格內容。"""
        extractors: list[ExtractorModel] = []
        for row in range(self.extractor_table.rowCount()):
            variable_item = self.extractor_table.item(row, 0)
            expression_item = self.extractor_table.item(row, 2)
            group_item = self.extractor_table.item(row, 3)
            variable_name = variable_item.text().strip() if variable_item else ""
            expression = expression_item.text() if expression_item else ""
            if not variable_name and not expression:
                continue
            kind_widget = self.extractor_table.cellWidget(row, 1)
            kind_value = (
                kind_widget.currentData() if isinstance(kind_widget, QComboBox) else None
            )
            if not isinstance(kind_value, str):
                raise ValueError(f"第 {row + 1} 個 Extractor 類型無效。")
            try:
                kind = ExtractorType(kind_value)
            except ValueError as exc:
                raise ValueError(f"第 {row + 1} 個 Extractor 類型無效。") from exc
            try:
                group_index = int(group_item.text()) if group_item else 1
            except ValueError as exc:
                raise ValueError(f"第 {row + 1} 個 Extractor Group 必須是整數。") from exc
            extractors.append(
                ExtractorModel(
                    variable_name=variable_name,
                    kind=kind,
                    expression=expression,
                    group_index=group_index,
                )
            )
        return extractors

    def _create_extractor_type_selector(
        self,
        selected_type: ExtractorType | None = None,
    ) -> QComboBox:
        """建立 Extractor 類型選單，並在使用者變更時標記 Request。"""
        selector = QComboBox()
        for extractor_type in ExtractorType:
            selector.addItem(extractor_type.value, extractor_type.value)
        if selected_type is not None:
            selector.setCurrentIndex(selector.findData(selected_type.value))
        selector.currentIndexChanged.connect(self._mark_request_changed)
        return selector

    def _add_extractor_row(self) -> None:
        """新增一列空白 Extractor 編輯欄位。"""
        row = self.extractor_table.rowCount()
        self.extractor_table.insertRow(row)
        self.extractor_table.setItem(row, 0, QTableWidgetItem(""))
        kind_selector = self._create_extractor_type_selector()
        self.extractor_table.setCellWidget(row, 1, kind_selector)
        self.extractor_table.setItem(row, 2, QTableWidgetItem(""))
        self.extractor_table.setItem(row, 3, QTableWidgetItem("1"))
        self.extractor_table.setCurrentCell(row, 0)
        self._mark_request_changed()

    def _remove_extractor_row(self) -> None:
        """移除目前選取的 Extractor 編輯列。"""
        row = self.extractor_table.currentRow()
        if row >= 0:
            self.extractor_table.removeRow(row)
            self._mark_request_changed()

    def set_environment(self, environment: EnvironmentModel | None) -> None:
        """設定此編輯器發送請求時使用的 Environment。

        Args:
            environment: 作用中的 Environment；None 表示沒有可用變數。
        """
        self._environment = environment

    @staticmethod
    def _parse_headers(raw_text: str) -> dict[str, str]:
        """將每行一個 Header 的編輯內容轉為字典。

        Args:
            raw_text: 使用者編輯的多行 Header 文字。

        Returns:
            Header 名稱與值的對應字典。

        Raises:
            ValueError: 任一非空白行不是有效的名稱和值格式。
        """
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
        """將每行一個 Param 的編輯內容轉為字典。

        Args:
            raw_text: 使用者編輯的多行查詢參數文字。

        Returns:
            Param 名稱與值的對應字典。

        Raises:
            ValueError: 任一非空白行不是有效的名稱和值格式。
        """
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
        self.response_view.mark_request_started()
        try:
            request = self.build_request()
            if request.before_script.strip() or request.after_script.strip():
                warn_about_trusted_scripts(self)
            result = self._engine.execute(request, self._environment)
        except (ValueError, httpx.InvalidURL) as exc:
            self._show_error(str(exc))
            return
        finally:
            self.send_button.setEnabled(True)

        if result.response is None:
            self._show_error(result.error or "Request 未產生 Response。")
            return

        response = result.response
        self.response_view.show_response(
            status_code=response.status_code,
            elapsed_ms=response.elapsed_ms,
            headers=response.headers,
            body_text=response.body_text,
        )
        notices = [*result.warnings]
        if result.error is not None:
            notices.insert(0, result.error)
        if notices:
            self.error_label.setText("\n".join(notices))
        if result.error is not None:
            self.request_failed.emit(result.error)
            return
        self.request_succeeded.emit(response)

    def _show_error(self, message: str) -> None:
        """顯示請求錯誤並通知訂閱者。

        Args:
            message: 要呈現的錯誤訊息。
        """
        self.response_view.mark_request_failed()
        self.error_label.setText(message)
        logger.error("Request editor error | %s", message)
        self.request_failed.emit(message)

    def closeEvent(self, event: QCloseEvent) -> None:
        """在視窗關閉時釋放由引擎持有的 HTTP 資源。

        Args:
            event: Qt 傳入的關閉事件。
        """
        self._engine.close()
        super().closeEvent(event)
