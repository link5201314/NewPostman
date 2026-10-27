from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from newpostman.core.project_store import ProjectStore
from newpostman.ui.environment_manager import EnvironmentManagerDialog
from newpostman.ui.request_editor import RequestEditor


class MainWindow(QMainWindow):
    """NewPostman 主視窗與目前 Project Environment 選擇器。"""

    def __init__(
        self,
        store: ProjectStore | None = None,
        parent: QWidget | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        """建立主視窗與 Environment 資源入口。

        Args:
            store: Environment 使用的 Project 儲存服務；未提供時使用使用者資料目錄。
            parent: 可選的 Qt 父元件。
            client: 可選的 HTTPX Client，方便測試或共用連線設定。
        """
        super().__init__(parent)
        default_project_path = Path.home() / ".newpostman" / "project.json"
        self.store = store or ProjectStore(default_project_path)
        self.setWindowTitle("NewPostman")
        self.resize(1100, 760)

        self.environment_selector = QComboBox()
        self.environment_selector.setObjectName("activeEnvironment")
        self.environment_selector.currentIndexChanged.connect(
            self._set_active_environment
        )

        self.manage_environments_button = QPushButton("管理 Environments")
        self.manage_environments_button.setObjectName("manageEnvironments")
        self.manage_environments_button.clicked.connect(self.open_environment_manager)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.addWidget(QLabel("Environment"))
        toolbar_layout.addWidget(self.environment_selector)
        toolbar_layout.addWidget(self.manage_environments_button)
        toolbar_layout.addStretch()

        self.environment_sidebar = QListWidget()
        self.environment_sidebar.setObjectName("environmentResources")
        self.environment_sidebar.itemDoubleClicked.connect(
            self._activate_sidebar_environment
        )
        sidebar_layout = QVBoxLayout()
        sidebar_layout.addWidget(QLabel("ENVIRONMENTS"))
        sidebar_layout.addWidget(self.environment_sidebar, 1)
        sidebar = QWidget()
        sidebar.setLayout(sidebar_layout)
        sidebar.setMinimumWidth(210)
        sidebar.setMaximumWidth(300)

        self.request_editor = RequestEditor(client=client)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(self.request_editor)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 860])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(toolbar)
        central_layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self._refresh_environments()

    def open_environment_manager(self) -> None:
        """開啟可建立、編輯與刪除 Environment 的管理視窗。"""
        dialog = EnvironmentManagerDialog(self.store, self)
        dialog.environments_changed.connect(self._refresh_environments)
        dialog.exec()

    def _refresh_environments(self) -> None:
        environments = self.store.list_environments()
        active = self.store.active_environment()
        self.request_editor.set_environment(active)

        self.environment_selector.blockSignals(True)
        self.environment_selector.clear()
        self.environment_selector.addItem("(未選擇 Environment)", "")
        active_index = 0
        for index, environment in enumerate(environments, start=1):
            self.environment_selector.addItem(environment.name, str(environment.id))
            if active is not None and environment.id == active.id:
                active_index = index
        self.environment_selector.setCurrentIndex(active_index)
        self.environment_selector.setEnabled(bool(environments))
        self.environment_selector.blockSignals(False)

        self.environment_sidebar.clear()
        for environment in environments:
            self.environment_sidebar.addItem(environment.name)
            item = self.environment_sidebar.item(self.environment_sidebar.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, str(environment.id))
            if active is not None and environment.id == active.id:
                item.setToolTip("目前作用中的 Environment")

    def _set_active_environment(self, index: int) -> None:
        if index < 0:
            return
        environment_id = self.environment_selector.currentData()
        selected_id = UUID(environment_id) if environment_id else None
        self.store.set_active_environment(selected_id)
        self.request_editor.set_environment(self.store.active_environment())
        self._refresh_environments()

    def _activate_sidebar_environment(self, item: QListWidgetItem) -> None:
        environment_id = item.data(Qt.ItemDataRole.UserRole)
        target_index = self.environment_selector.findData(environment_id)
        if target_index >= 0:
            self.environment_selector.setCurrentIndex(target_index)
