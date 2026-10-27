from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import httpx
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from newpostman.core.project_store import ProjectStore, ProjectStoreError
from newpostman.models.collection import CollectionModel
from newpostman.models.dataset import DatasetModel
from newpostman.models.request import RequestModel
from newpostman.ui.environment_manager import EnvironmentManagerDialog
from newpostman.ui.request_editor import RequestEditor
from newpostman.ui.runner_panel import RunnerPanel


class MainWindow(QMainWindow):
    """NewPostman 主視窗、資源導覽與 Request 工作分頁。"""

    COLLECTION_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    RESOURCE_KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 2
    REQUEST_ROLE = int(Qt.ItemDataRole.UserRole) + 3
    DATASET_ROLE = int(Qt.ItemDataRole.UserRole) + 4

    def __init__(
        self,
        store: ProjectStore | None = None,
        parent: QWidget | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        """建立主視窗、資源導覽及單一 Request 工作分頁。

        Args:
            store: Environment 與 Collection 使用的 Project 儲存服務。
            parent: 可選的 Qt 父元件。
            client: 可選的 HTTPX Client，方便測試或共用連線設定。
        """
        super().__init__(parent)
        default_project_path = Path.home() / ".newpostman" / "project.json"
        self.store = store or ProjectStore(default_project_path)
        self._client = client
        self._runner_panel: RunnerPanel | None = None
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
        self.add_collection_button = QPushButton("新增 Collection")
        self.add_collection_button.setObjectName("addCollection")
        self.add_collection_button.clicked.connect(self._prompt_add_collection)
        self.new_request_button = QPushButton("New Request")
        self.new_request_button.setObjectName("newRequest")
        self.new_request_button.clicked.connect(self.new_request)
        self.load_dataset_button = QPushButton("載入 Dataset")
        self.load_dataset_button.setObjectName("loadDataset")
        self.load_dataset_button.clicked.connect(self._prompt_load_dataset)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveRequest")
        self.save_button.clicked.connect(self.save_current_request)
        self.save_as_button = QPushButton("Save As")
        self.save_as_button.setObjectName("saveRequestAs")
        self.save_as_button.clicked.connect(self.save_request_as)
        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("openRunner")
        self.run_button.clicked.connect(self.open_runner_tab)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.addWidget(QLabel("Environment"))
        toolbar_layout.addWidget(self.environment_selector)
        toolbar_layout.addWidget(self.manage_environments_button)
        toolbar_layout.addWidget(self.add_collection_button)
        toolbar_layout.addWidget(self.new_request_button)
        toolbar_layout.addWidget(self.load_dataset_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.run_button)
        toolbar_layout.addWidget(self.save_button)
        toolbar_layout.addWidget(self.save_as_button)

        self.resource_tree = QTreeWidget()
        self.resource_tree.setObjectName("resourceTree")
        self.resource_tree.setHeaderHidden(True)
        self.resource_tree.itemClicked.connect(self._activate_resource_item)
        self.resource_tree.currentItemChanged.connect(
            self._update_request_order_buttons
        )
        self.resource_tree.setMinimumWidth(210)
        self.resource_tree.setMaximumWidth(320)

        self.move_request_up_button = QPushButton("Request 上移")
        self.move_request_up_button.setObjectName("moveRequestUp")
        self.move_request_up_button.clicked.connect(
            lambda: self._move_selected_request(-1)
        )
        self.move_request_down_button = QPushButton("Request 下移")
        self.move_request_down_button.setObjectName("moveRequestDown")
        self.move_request_down_button.clicked.connect(
            lambda: self._move_selected_request(1)
        )
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self.resource_tree, 1)
        order_controls = QHBoxLayout()
        order_controls.addWidget(self.move_request_up_button)
        order_controls.addWidget(self.move_request_down_button)
        sidebar_layout.addLayout(order_controls)

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setObjectName("workspaceTabs")
        self.workspace_tabs.setTabsClosable(True)
        self.workspace_tabs.setMovable(True)
        self.workspace_tabs.currentChanged.connect(self._update_save_button)
        self.workspace_tabs.tabCloseRequested.connect(self.close_workspace_tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(self.workspace_tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 850])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(toolbar)
        central_layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self._refresh_resources()
        self._refresh_environments()
        self._add_request_tab(RequestModel(), collection_id=None)
        self._update_request_order_buttons()

    @property
    def request_editor(self) -> RequestEditor:
        """取得目前作用中的 RequestEditor。"""
        current = self.workspace_tabs.currentWidget()
        if isinstance(current, RequestEditor):
            return current
        raise RuntimeError("目前工作分頁不是 Request 編輯器。")

    def open_environment_manager(self) -> None:
        """開啟可建立、編輯與刪除 Environment 的管理視窗。"""
        dialog = EnvironmentManagerDialog(self.store, self)
        dialog.environments_changed.connect(self._refresh_resources)
        dialog.environments_changed.connect(self._refresh_environments)
        dialog.exec()

    def add_collection(self, name: str) -> CollectionModel:
        """建立並保存 Collection，然後更新側欄資源樹。

        Args:
            name: Collection 顯示名稱。

        Returns:
            已建立的 Collection。

        Raises:
            ValueError: Collection 名稱為空白。
        """
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Collection 名稱不可為空白。")
        collection = self.store.add_collection(CollectionModel(name=normalized_name))
        self._refresh_resources()
        return collection

    def load_dataset(self, path: Path) -> DatasetModel:
        """驗證並登錄 Dataset 檔案，更新資源樹及 Runner 選項。"""
        dataset = self.store.add_dataset(path)
        self._refresh_resources()
        return dataset

    def new_request(self) -> RequestEditor:
        """新增一個尚未保存的 Request 工作分頁。

        Returns:
            新建立並聚焦的 Request 編輯器。
        """
        return self._add_request_tab(RequestModel(), collection_id=None)

    def open_runner_tab(self) -> RunnerPanel:
        """開啟或聚焦 Runner 工作分頁。"""
        if self._runner_panel is not None:
            tab_index = self.workspace_tabs.indexOf(self._runner_panel)
            if tab_index >= 0:
                self._runner_panel.refresh_collections()
                self._runner_panel.refresh_datasets()
                self._runner_panel.refresh_environment()
                self.workspace_tabs.setCurrentIndex(tab_index)
                return self._runner_panel

        panel = RunnerPanel(self.store, client=self._client)
        self._runner_panel = panel
        tab_index = self.workspace_tabs.addTab(panel, "Runner")
        self.workspace_tabs.setCurrentIndex(tab_index)
        return panel

    def open_collection_request(
        self,
        collection_id: UUID,
        request_id: UUID,
    ) -> RequestEditor:
        """開啟 Collection Request，或聚焦已開啟的對應分頁。

        Args:
            collection_id: Request 所屬 Collection 識別碼。
            request_id: 要開啟的 Request 識別碼。

        Returns:
            顯示該 Request 的工作分頁。

        Raises:
            ProjectStoreError: 找不到 Collection 或 Request。
        """
        existing_index = self._find_request_tab(collection_id, request_id)
        if existing_index >= 0:
            self.workspace_tabs.setCurrentIndex(existing_index)
            editor = self.workspace_tabs.widget(existing_index)
            if isinstance(editor, RequestEditor):
                return editor
            raise RuntimeError("Request 工作分頁類型無效。")

        collection = self.store.get_collection(collection_id)
        request = next(
            (item for item in collection.requests if item.id == request_id),
            None,
        )
        if request is None:
            raise ProjectStoreError(f"找不到 Request：{request_id}")
        return self._add_request_tab(request, collection_id=str(collection_id))

    def save_request_as(self) -> bool:
        """將目前 Request 加入指定或新建的 Collection。

        Returns:
            若成功儲存則回傳 True；若使用者取消或資料無效則回傳 False。
        """
        if not isinstance(self.workspace_tabs.currentWidget(), RequestEditor):
            return False
        editor = self.request_editor
        try:
            request = editor.build_request()
        except ValueError as exc:
            QMessageBox.warning(self, "無法儲存 Request", str(exc))
            return False

        collection_name, accepted = QInputDialog.getText(
            self,
            "Save Request As",
            "Collection 名稱（輸入既有名稱以加入該 Collection）",
        )
        if not accepted or not collection_name.strip():
            return False

        collection = next(
            (
                item
                for item in self.store.list_collections()
                if item.name == collection_name.strip()
            ),
            None,
        )
        if collection is None:
            collection = self.add_collection(collection_name)

        if editor.collection_id == str(collection.id):
            existing_request_index = next(
                (
                    index
                    for index, item in enumerate(collection.requests)
                    if item.id == request.id
                ),
                -1,
            )
            if existing_request_index >= 0:
                collection.requests[existing_request_index] = request
            else:
                collection.requests.append(request)
        else:
            request = request.model_copy(update={"id": uuid4()})
            collection.requests.append(request)

        try:
            self.store.update_collection(collection)
        except ProjectStoreError as exc:
            QMessageBox.warning(self, "無法儲存 Collection", str(exc))
            return False

        editor.set_request(request, collection_id=str(collection.id))
        self._refresh_resources()
        self._update_current_tab_title()
        return True

    def save_current_request(self) -> bool:
        """儲存目前 Request；新 Request 會轉入 Save As 流程。

        Returns:
            成功儲存時回傳 True。
        """
        return self._save_editor(self.request_editor)

    def close_workspace_tab(self, index: int) -> bool:
        """關閉工作分頁；未儲存時先詢問使用者。

        Args:
            index: 要關閉的工作分頁索引。

        Returns:
            分頁已關閉時回傳 True，取消關閉時回傳 False。
        """
        editor = self.workspace_tabs.widget(index)
        if isinstance(editor, RunnerPanel):
            if editor.runner.is_running:
                editor.runner.cancel()
                editor.summary_label.setText("正在取消；目前 Request 結束後即可關閉。")
                return False
            self.workspace_tabs.removeTab(index)
            editor.deleteLater()
            self._runner_panel = None
            return True
        if not isinstance(editor, RequestEditor):
            return False
        if editor.is_dirty and not self._resolve_dirty_editor(editor):
            return False
        self.workspace_tabs.removeTab(index)
        editor.close()
        editor.deleteLater()
        if self.workspace_tabs.count() == 0:
            self._add_request_tab(RequestModel(), collection_id=None)
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        """關閉視窗前處理所有未儲存的 Request 分頁。

        Args:
            event: Qt 傳入的關閉事件。
        """
        for index in range(self.workspace_tabs.count()):
            editor = self.workspace_tabs.widget(index)
            if (
                isinstance(editor, RequestEditor)
                and editor.is_dirty
                and not self._resolve_dirty_editor(editor)
            ):
                event.ignore()
                return
            if isinstance(editor, RunnerPanel) and editor.runner.is_running:
                editor.runner.cancel()
                event.ignore()
                return
        for index in range(self.workspace_tabs.count()):
            editor = self.workspace_tabs.widget(index)
            if isinstance(editor, RequestEditor):
                editor.close()
            elif isinstance(editor, RunnerPanel):
                editor.close()
        event.accept()

    def _resolve_dirty_editor(self, editor: RequestEditor) -> bool:
        answer = QMessageBox.question(
            self,
            "未儲存的 Request",
            f"是否儲存「{editor.request_name_input.text()}」的變更？",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Discard:
            return True
        if answer == QMessageBox.StandardButton.Save:
            self.workspace_tabs.setCurrentWidget(editor)
            return self._save_editor(editor) and not editor.is_dirty
        return False

    def _save_editor(self, editor: RequestEditor) -> bool:
        """儲存已有 Collection 的 Request，或對新 Request 執行 Save As。

        Args:
            editor: 要儲存的 Request 編輯器。

        Returns:
            成功儲存時回傳 True。
        """
        if editor.collection_id is None:
            return self.save_request_as()
        try:
            request = editor.build_request()
            collection = self.store.get_collection(UUID(editor.collection_id))
        except (ProjectStoreError, ValueError) as exc:
            QMessageBox.warning(self, "無法儲存 Request", str(exc))
            return False

        request_index = next(
            (
                index
                for index, item in enumerate(collection.requests)
                if item.id == request.id
            ),
            -1,
        )
        if request_index < 0:
            QMessageBox.warning(
                self, "無法儲存 Request", "Collection 中找不到此 Request。"
            )
            return False
        collection.requests[request_index] = request
        try:
            self.store.update_collection(collection)
        except ProjectStoreError as exc:
            QMessageBox.warning(self, "無法儲存 Collection", str(exc))
            return False
        editor.set_request(request, collection_id=str(collection.id))
        self._refresh_resources()
        self._update_current_tab_title()
        return True

    def _prompt_add_collection(self) -> None:
        name, accepted = QInputDialog.getText(self, "新增 Collection", "名稱")
        if not accepted or not name.strip():
            return
        try:
            collection = self.add_collection(name)
        except (ProjectStoreError, ValueError) as exc:
            QMessageBox.warning(self, "無法新增 Collection", str(exc))
            return
        collections_root = self.resource_tree.topLevelItem(0)
        if collections_root is not None:
            self.resource_tree.expandItem(collections_root)
        collection_item = self._find_collection_item(collection.id)
        if collection_item is not None:
            self.resource_tree.setCurrentItem(collection_item)

    def _prompt_load_dataset(self) -> None:
        """選取 CSV／JSON 檔案並登錄為 Project Dataset。"""
        path_text, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "載入 Dataset",
            str(self.store.project_root),
            "Dataset (*.csv *.json)",
        )
        if not path_text:
            return
        try:
            self.load_dataset(Path(path_text))
        except (ProjectStoreError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "無法載入 Dataset", str(exc))

    def _refresh_resources(self) -> None:
        self.resource_tree.clear()
        collections_root = QTreeWidgetItem(["Collections"])
        collections_root.setData(0, self.RESOURCE_KIND_ROLE, "collections-root")
        environments_root = QTreeWidgetItem(["Environments"])
        environments_root.setData(0, self.RESOURCE_KIND_ROLE, "environments-root")
        datasets_root = QTreeWidgetItem(["Datasets"])
        datasets_root.setData(0, self.RESOURCE_KIND_ROLE, "datasets-root")
        self.resource_tree.addTopLevelItem(collections_root)
        self.resource_tree.addTopLevelItem(environments_root)
        self.resource_tree.addTopLevelItem(datasets_root)

        for collection in self.store.list_collections():
            collection_item = QTreeWidgetItem([collection.name])
            collection_item.setData(0, self.RESOURCE_KIND_ROLE, "collection")
            collection_item.setData(0, self.COLLECTION_ROLE, str(collection.id))
            collections_root.addChild(collection_item)
            for request in collection.requests:
                request_item = QTreeWidgetItem([request.name])
                request_item.setData(0, self.RESOURCE_KIND_ROLE, "request")
                request_item.setData(0, self.COLLECTION_ROLE, str(collection.id))
                request_item.setData(0, self.REQUEST_ROLE, str(request.id))
                collection_item.addChild(request_item)

        active = self.store.active_environment()
        for environment in self.store.list_environments():
            environment_item = QTreeWidgetItem([environment.name])
            environment_item.setData(0, self.RESOURCE_KIND_ROLE, "environment")
            environment_item.setData(0, self.REQUEST_ROLE, str(environment.id))
            if active is not None and environment.id == active.id:
                environment_item.setToolTip(0, "目前作用中的 Environment")
            environments_root.addChild(environment_item)

        for dataset in self.store.list_datasets():
            dataset_item = QTreeWidgetItem([dataset.name])
            dataset_item.setData(0, self.RESOURCE_KIND_ROLE, "dataset")
            dataset_item.setData(0, self.DATASET_ROLE, str(dataset.id))
            dataset_item.setToolTip(0, dataset.path.as_posix())
            datasets_root.addChild(dataset_item)

        self.resource_tree.expandAll()
        if self._runner_panel is not None:
            self._runner_panel.refresh_collections()
            self._runner_panel.refresh_datasets()

    def _refresh_environments(self) -> None:
        environments = self.store.list_environments()
        active = self.store.active_environment()
        for index in range(self.workspace_tabs.count()):
            editor = self.workspace_tabs.widget(index)
            if isinstance(editor, RequestEditor):
                editor.set_environment(active)

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
        if self._runner_panel is not None:
            self._runner_panel.refresh_environment()

    def _set_active_environment(self, index: int) -> None:
        if index < 0:
            return
        environment_id = self.environment_selector.currentData()
        selected_id = UUID(environment_id) if environment_id else None
        self.store.set_active_environment(selected_id)
        self._refresh_environments()
        self._refresh_resources()

    def _activate_resource_item(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.data(0, self.RESOURCE_KIND_ROLE) == "request":
            self.open_collection_request(
                UUID(item.data(0, self.COLLECTION_ROLE)),
                UUID(item.data(0, self.REQUEST_ROLE)),
            )
        elif item.data(0, self.RESOURCE_KIND_ROLE) == "environment":
            environment_id = item.data(0, self.REQUEST_ROLE)
            selector_index = self.environment_selector.findData(environment_id)
            if selector_index >= 0:
                self.environment_selector.setCurrentIndex(selector_index)

    def _add_request_tab(
        self,
        request: RequestModel,
        *,
        collection_id: str | None,
    ) -> RequestEditor:
        editor = RequestEditor(client=self._client)
        editor.set_environment(self.store.active_environment())
        editor.set_request(request, collection_id=collection_id)
        editor.request_changed.connect(self._update_current_tab_title)
        tab_index = self.workspace_tabs.addTab(editor, request.name)
        self.workspace_tabs.setCurrentIndex(tab_index)
        return editor

    def _find_request_tab(self, collection_id: UUID, request_id: UUID) -> int:
        for index in range(self.workspace_tabs.count()):
            editor = self.workspace_tabs.widget(index)
            if not isinstance(editor, RequestEditor):
                continue
            saved_request = editor.saved_request
            if (
                editor.collection_id == str(collection_id)
                and saved_request is not None
                and saved_request.id == request_id
            ):
                return index
        return -1

    def _find_collection_item(self, collection_id: UUID) -> QTreeWidgetItem | None:
        """依識別碼尋找 Collections 根項目下的 Collection。

        Args:
            collection_id: Collection 識別碼。

        Returns:
            找到時回傳樹狀項目，否則回傳 None。
        """
        root = self.resource_tree.topLevelItem(0)
        if root is None:
            return None
        for index in range(root.childCount()):
            item = root.child(index)
            if item is None:
                continue
            if item.data(0, self.COLLECTION_ROLE) == str(collection_id):
                return item
        return None

    def _update_save_button(self, _index: int = -1) -> None:
        """依目前 Request 工作分頁狀態更新 Save 控制項。

        Args:
            _index: Qt currentChanged 訊號提供的目前分頁索引。
        """
        self.save_as_button.setEnabled(self.workspace_tabs.count() > 0)
        editor = self.workspace_tabs.currentWidget()
        if isinstance(editor, RequestEditor):
            self.save_button.setEnabled(editor.is_dirty)
            self.save_as_button.setEnabled(True)
        else:
            self.save_button.setEnabled(False)
            self.save_as_button.setEnabled(False)
        self._update_request_order_buttons()

    def _update_current_tab_title(self) -> None:
        """更新目前工作分頁標題與未儲存變更標記。"""
        editor = self.workspace_tabs.currentWidget()
        if not isinstance(editor, RequestEditor):
            return
        index = self.workspace_tabs.currentIndex()
        suffix = " *" if editor.is_dirty else ""
        self.workspace_tabs.setTabText(
            index,
            f"{editor.request_name_input.text().strip() or 'Untitled request'}{suffix}",
        )
        self.save_button.setEnabled(editor.is_dirty)

    def _update_request_order_buttons(
        self,
        _current: QTreeWidgetItem | None = None,
        _previous: QTreeWidgetItem | None = None,
    ) -> None:
        """依側欄選取 Request 的位置更新排序按鈕狀態。

        Args:
            _current: Qt 傳入的目前樹狀項目。
            _previous: Qt 傳入的前一個樹狀項目。
        """
        item = self.resource_tree.currentItem()
        is_request = (
            item is not None and item.data(0, self.RESOURCE_KIND_ROLE) == "request"
        )
        parent = item.parent() if item is not None else None
        self.move_request_up_button.setEnabled(
            bool(
                is_request
                and item is not None
                and parent is not None
                and parent.indexOfChild(item) > 0
            )
        )
        self.move_request_down_button.setEnabled(
            bool(
                is_request
                and item is not None
                and parent is not None
                and parent.indexOfChild(item) < parent.childCount() - 1
            )
        )

    def _move_selected_request(self, offset: int) -> None:
        """依 Collection Request 清單順序移動目前選取項目。

        Args:
            offset: 相對索引位移；-1 表示上移，1 表示下移。
        """
        item = self.resource_tree.currentItem()
        if item is None or item.data(0, self.RESOURCE_KIND_ROLE) != "request":
            return
        collection_id = UUID(item.data(0, self.COLLECTION_ROLE))
        request_id = UUID(item.data(0, self.REQUEST_ROLE))
        collection = self.store.get_collection(collection_id)
        current_index = next(
            (
                index
                for index, request in enumerate(collection.requests)
                if request.id == request_id
            ),
            -1,
        )
        target_index = current_index + offset
        if current_index < 0 or not 0 <= target_index < len(collection.requests):
            return
        collection.requests[current_index], collection.requests[target_index] = (
            collection.requests[target_index],
            collection.requests[current_index],
        )
        self.store.update_collection(collection)
        self._refresh_resources()
        request_item = self._find_request_item(collection_id, request_id)
        if request_item is not None:
            self.resource_tree.setCurrentItem(request_item)

    def _find_request_item(
        self,
        collection_id: UUID,
        request_id: UUID,
    ) -> QTreeWidgetItem | None:
        """依識別碼尋找 Collection 資源樹中的 Request 項目。

        Args:
            collection_id: Request 所屬 Collection 識別碼。
            request_id: Request 識別碼。

        Returns:
            找到時回傳樹狀項目，否則回傳 None。
        """
        collection_item = self._find_collection_item(collection_id)
        if collection_item is None:
            return None
        for index in range(collection_item.childCount()):
            request_item = collection_item.child(index)
            if request_item is not None and request_item.data(
                0, self.REQUEST_ROLE
            ) == str(request_id):
                return request_item
        return None
