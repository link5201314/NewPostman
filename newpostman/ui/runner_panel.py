from __future__ import annotations

from uuid import UUID

import httpx
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from newpostman.core.collection_runner import (
    CollectionRunner,
    RunItemResult,
    RunSummary,
)
from newpostman.core.dataset_loader import DatasetLoadError, DatasetLoader
from newpostman.core.project_store import ProjectStore
from newpostman.ui.script_warning import warn_about_trusted_scripts


class RunnerPanel(QWidget):
    """提供 Collection 選擇、背景執行控制與 Runner 結果檢視。"""

    def __init__(
        self,
        store: ProjectStore,
        parent: QWidget | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        """建立 Runner 工作分頁。

        Args:
            store: 提供 Collection 與作用 Environment 的 Project 儲存服務。
            parent: 可選的 Qt 父元件。
            client: 可選的 HTTPX Client，供測試注入 MockTransport。
        """
        super().__init__(parent)
        self.store = store
        self.runner = CollectionRunner(client=client)
        self.setObjectName("runnerPanel")

        self.collection_selector = QComboBox()
        self.collection_selector.setObjectName("runnerCollection")
        self.dataset_label = QLabel("Dataset")
        self.dataset_selector = QComboBox()
        self.dataset_selector.setObjectName("runnerDataset")
        self.environment_label = QLabel()
        self.environment_label.setObjectName("runnerEnvironment")

        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("startRunner")
        self.run_button.clicked.connect(self.start_run)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelRunner")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.runner.cancel)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("runnerProgress")
        self.progress_label = QLabel("0/0")
        self.progress_label.setObjectName("runnerProgressLabel")
        self.summary_label = QLabel("尚未執行")
        self.summary_label.setObjectName("runnerSummary")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("runnerLog")
        self.log_view.setReadOnly(True)

        selection_row = QHBoxLayout()
        selection_row.addWidget(QLabel("Collection"))
        selection_row.addWidget(self.collection_selector, 1)
        selection_row.addWidget(self.dataset_label)
        selection_row.addWidget(self.dataset_selector, 1)
        selection_row.addWidget(QLabel("Environment"))
        selection_row.addWidget(self.environment_label)

        controls = QHBoxLayout()
        controls.addWidget(self.run_button)
        controls.addWidget(self.cancel_button)
        controls.addStretch()
        controls.addWidget(self.progress_label)

        layout = QVBoxLayout(self)
        layout.addLayout(selection_row)
        layout.addLayout(controls)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.log_view, 1)

        self.runner.progress.connect(self._update_progress)
        self.runner.log.connect(self.log_view.appendPlainText)
        self.runner.request_completed.connect(self._record_request_result)
        self.runner.iteration_progress.connect(self._update_iteration_progress)
        self.runner.run_finished.connect(self._show_summary)

        self.refresh_collections()
        self.refresh_datasets()
        self.refresh_environment()

    def refresh_collections(self) -> None:
        """重新載入可執行的 Collection 選項。"""
        previous_id = self.collection_selector.currentData()
        self.collection_selector.blockSignals(True)
        self.collection_selector.clear()
        for collection in self.store.list_collections():
            self.collection_selector.addItem(
                collection.name,
                str(collection.id),
            )
        previous_index = self.collection_selector.findData(previous_id)
        if previous_index >= 0:
            self.collection_selector.setCurrentIndex(previous_index)
        self.collection_selector.blockSignals(False)
        self.run_button.setEnabled(
            self.collection_selector.count() > 0 and not self.runner.is_running
        )

    def refresh_datasets(self) -> None:
        """重新載入可選 Dataset，保留目前的選擇。"""
        previous_id = self.dataset_selector.currentData()
        self.dataset_selector.blockSignals(True)
        self.dataset_selector.clear()
        self.dataset_selector.addItem("（不使用 Dataset）", "")
        for dataset in self.store.list_datasets():
            self.dataset_selector.addItem(dataset.name, str(dataset.id))
        previous_index = self.dataset_selector.findData(previous_id)
        if previous_index >= 0:
            self.dataset_selector.setCurrentIndex(previous_index)
        self.dataset_selector.blockSignals(False)

        has_datasets = bool(self.store.list_datasets())
        for widget in (self.dataset_label, self.dataset_selector):
            widget.setVisible(has_datasets)

    def refresh_environment(self) -> None:
        """顯示目前作用中的 Environment 名稱。"""
        environment = self.store.active_environment()
        self.environment_label.setText(
            environment.name if environment is not None else "（未選擇）"
        )

    def start_run(self) -> None:
        """以目前選取的 Collection 與全域作用 Environment 啟動 Runner。"""
        collection_id = self.collection_selector.currentData()
        if not collection_id or self.runner.is_running:
            return
        collection = self.store.get_collection(UUID(collection_id))
        environment = self.store.active_environment()
        dataset_rows: list[dict[str, str]] | None = None
        dataset_id = self.dataset_selector.currentData()
        if dataset_id:
            try:
                dataset = self.store.get_dataset(UUID(dataset_id))
                dataset_rows = DatasetLoader.load(dataset.path)
            except (DatasetLoadError, ValueError, OSError) as exc:
                QMessageBox.warning(self, "無法載入 Dataset", str(exc))
                return
        if any(
            request.before_script.strip() or request.after_script.strip()
            for request in collection.requests
        ):
            warn_about_trusted_scripts(self)
        self.refresh_environment()
        self.log_view.clear()
        self.summary_label.setText("執行中…")
        self.progress_bar.setRange(0, len(collection.requests))
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"0/{len(collection.requests)}")
        if not self.runner.start(
            collection,
            environment,
            dataset_rows=dataset_rows,
        ):
            self.summary_label.setText("Runner 已在執行中")
            return
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

    def _update_progress(self, completed: int, total: int) -> None:
        """更新目前完成的 Request 數量。"""
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(completed)
        self.progress_label.setText(f"{completed}/{total}")

    def _record_request_result(self, item: RunItemResult) -> None:
        """在逐項結果訊號到達時更新摘要狀態。"""
        response = item.result.response
        if response is not None:
            self.summary_label.setText(
                f"Iteration {item.iteration_index}/{item.iteration_total}，"
                f"Request {item.index}/{item.total}，"
                f"HTTP {response.status_code}"
            )
        else:
            self.summary_label.setText(
                f"Iteration {item.iteration_index}/{item.iteration_total}，"
                f"Request {item.index}/{item.total} 失敗"
            )

    def _update_iteration_progress(
        self,
        iteration_index: int,
        iteration_total: int,
        request_index: int,
        request_total: int,
    ) -> None:
        """呈現目前 Iteration 與其 Collection Request 進度。"""
        self.progress_label.setText(
            f"Iteration {iteration_index}/{iteration_total} · "
            f"Request {request_index}/{request_total}"
        )

    def _show_summary(self, summary: RunSummary) -> None:
        """呈現 Runner 完成摘要並恢復操作按鈕。"""
        state = "已取消" if summary.cancelled else "完成"
        summary_text = (
            f"{state}：成功 {summary.succeeded}，失敗 {summary.failed}，"
            f"完成 {summary.completed_iterations}/"
            f"{summary.iterations} 個 Iteration，"
            f"共 {summary.total} 個 Request"
        )
        if summary.error is not None:
            summary_text += f"；Runner 錯誤：{summary.error}"
        self.summary_label.setText(summary_text)
        self.run_button.setEnabled(self.collection_selector.count() > 0)
        self.cancel_button.setEnabled(False)
