from __future__ import annotations

from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from newpostman.diagnostics import LogBridge


class DiagnosticPanel(QDockWidget):
    """顯示應用程式日誌，並允許使用者清除目前畫面內容。"""

    def __init__(self, bridge: LogBridge, parent: QWidget | None = None) -> None:
        super().__init__("診斷日誌", parent)
        self.setObjectName("diagnosticPanel")
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 6, 6, 6)
        controls = QHBoxLayout()
        self.clear_button = QPushButton("清除")
        self.clear_button.setObjectName("clearDiagnosticLog")
        self.clear_button.clicked.connect(self.clear)
        controls.addStretch()
        controls.addWidget(self.clear_button)
        layout.addLayout(controls)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("diagnosticLog")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)
        self.setWidget(content)
        bridge.message.connect(self.log_view.appendPlainText)

    def clear(self) -> None:
        """清除診斷區目前顯示的內容；後續日誌仍會繼續追加。"""
        self.log_view.clear()
