from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from newpostman.core.project_store import ProjectStore, ProjectStoreError
from newpostman.models.environment import EnvironmentModel


class EnvironmentManagerDialog(QDialog):
    """管理 Project 中 Environment 與其變數。"""

    environments_changed = Signal()

    def __init__(
        self,
        store: ProjectStore,
        parent: QWidget | None = None,
    ) -> None:
        """建立 Environment 管理視窗。

        Args:
            store: Environment JSON 的 Project 儲存服務。
            parent: 可選的 Qt 父元件。
        """
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Environments")
        self.resize(620, 420)

        self.environment_list = QListWidget()
        self.environment_list.setObjectName("environmentList")
        self.environment_list.currentRowChanged.connect(self._select_environment)

        self.add_button = QPushButton("新增")
        self.add_button.setObjectName("addEnvironment")
        self.add_button.clicked.connect(self._add_environment)

        self.remove_button = QPushButton("刪除")
        self.remove_button.setObjectName("removeEnvironment")
        self.remove_button.clicked.connect(self._remove_environment)

        self.rename_button = QPushButton("重新命名")
        self.rename_button.setObjectName("renameEnvironment")
        self.rename_button.clicked.connect(self._rename_environment)

        self.variables_table = QTableWidget(0, 2)
        self.variables_table.setObjectName("environmentVariables")
        self.variables_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.variables_table.horizontalHeader().setStretchLastSection(True)

        self.add_variable_button = QPushButton("新增變數")
        self.add_variable_button.setObjectName("addEnvironmentVariable")
        self.add_variable_button.clicked.connect(self._add_variable)

        self.remove_variable_button = QPushButton("刪除變數")
        self.remove_variable_button.setObjectName("removeEnvironmentVariable")
        self.remove_variable_button.clicked.connect(self._remove_variable)

        self.save_button = QPushButton("儲存")
        self.save_button.setObjectName("saveEnvironment")
        self.save_button.clicked.connect(self._save_environment)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)

        list_buttons = QHBoxLayout()
        list_buttons.addWidget(self.add_button)
        list_buttons.addWidget(self.rename_button)
        list_buttons.addWidget(self.remove_button)

        variable_buttons = QHBoxLayout()
        variable_buttons.addWidget(self.add_variable_button)
        variable_buttons.addWidget(self.remove_variable_button)
        variable_buttons.addStretch()
        variable_buttons.addWidget(self.save_button)

        content = QVBoxLayout()
        content.addWidget(self.environment_list, 1)
        content.addLayout(list_buttons)

        editor = QVBoxLayout()
        editor.addWidget(self.variables_table, 1)
        editor.addLayout(variable_buttons)

        panes = QHBoxLayout()
        panes.addLayout(content, 1)
        panes.addLayout(editor, 2)

        layout = QVBoxLayout(self)
        layout.addLayout(panes, 1)
        layout.addWidget(button_box)

        self._refresh_environment_list()

    @staticmethod
    def make_table_item(text: str) -> QTableWidgetItem:
        """建立環境變數表格項目。

        Args:
            text: 項目要呈現的文字。

        Returns:
            可編輯的表格項目。
        """
        return QTableWidgetItem(text)

    def _refresh_environment_list(self, selected_id: UUID | None = None) -> None:
        self.environment_list.blockSignals(True)
        self.environment_list.clear()
        selected_row = 0
        for row, environment in enumerate(self.store.list_environments()):
            item = QListWidgetItem(environment.name)
            item.setData(Qt.ItemDataRole.UserRole, str(environment.id))
            self.environment_list.addItem(item)
            if environment.id == selected_id:
                selected_row = row
        self.environment_list.blockSignals(False)
        if self.environment_list.count():
            self.environment_list.setCurrentRow(selected_row)
        else:
            self.variables_table.setRowCount(0)

    def _selected_environment_id(self) -> UUID | None:
        item = self.environment_list.currentItem()
        if item is None:
            return None
        return UUID(item.data(Qt.ItemDataRole.UserRole))

    def _select_environment(self, row: int) -> None:
        if row < 0:
            self.variables_table.setRowCount(0)
            return
        environment_id = self._selected_environment_id()
        if environment_id is None:
            return
        environment = self.store.get_environment(environment_id)
        self.variables_table.setRowCount(len(environment.variables))
        for row_index, (key, value) in enumerate(environment.variables.items()):
            self.variables_table.setItem(row_index, 0, self.make_table_item(key))
            self.variables_table.setItem(
                row_index,
                1,
                self.make_table_item(value),
            )

    def _add_environment(self) -> None:
        name, accepted = QInputDialog.getText(self, "新增 Environment", "名稱")
        if not accepted or not name.strip():
            return
        try:
            environment = self.store.add_environment(
                EnvironmentModel(name=name.strip())
            )
        except (ProjectStoreError, ValueError) as exc:
            QMessageBox.warning(self, "無法新增 Environment", str(exc))
            return
        self._refresh_environment_list(environment.id)
        self.environments_changed.emit()

    def _remove_environment(self) -> None:
        environment_id = self._selected_environment_id()
        if environment_id is None:
            return
        try:
            self.store.remove_environment(environment_id)
        except ProjectStoreError as exc:
            QMessageBox.warning(self, "無法刪除 Environment", str(exc))
            return
        self._refresh_environment_list()
        self.environments_changed.emit()

    def _rename_environment(self) -> None:
        environment_id = self._selected_environment_id()
        if environment_id is None:
            return
        environment = self.store.get_environment(environment_id)
        name, accepted = QInputDialog.getText(
            self,
            "重新命名 Environment",
            "名稱",
            text=environment.name,
        )
        if not accepted or not name.strip():
            return
        environment.name = name.strip()
        try:
            self.store.update_environment(environment)
        except (ProjectStoreError, ValueError) as exc:
            QMessageBox.warning(self, "無法重新命名 Environment", str(exc))
            return
        self._refresh_environment_list(environment.id)
        self.environments_changed.emit()

    def _add_variable(self) -> None:
        row = self.variables_table.rowCount()
        self.variables_table.insertRow(row)
        self.variables_table.setItem(row, 0, self.make_table_item(""))
        self.variables_table.setItem(row, 1, self.make_table_item(""))
        self.variables_table.setCurrentCell(row, 0)

    def _remove_variable(self) -> None:
        row = self.variables_table.currentRow()
        if row >= 0:
            self.variables_table.removeRow(row)

    def _save_environment(self) -> None:
        environment_id = self._selected_environment_id()
        if environment_id is None:
            return
        current = self.store.get_environment(environment_id)
        variables: dict[str, str] = {}
        for row in range(self.variables_table.rowCount()):
            key_item = self.variables_table.item(row, 0)
            value_item = self.variables_table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            if not key:
                continue
            if key in variables:
                QMessageBox.warning(
                    self,
                    "變數名稱重複",
                    f"Environment 內已有重複的變數名稱：{key}",
                )
                return
            variables[key] = value_item.text() if value_item else ""
        current.variables = variables
        try:
            self.store.update_environment(current)
        except ProjectStoreError as exc:
            QMessageBox.warning(self, "無法儲存 Environment", str(exc))
            return
        self.environments_changed.emit()
