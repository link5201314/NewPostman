from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from newpostman.ui.main_window import MainWindow


def main() -> int:
    """啟動 NewPostman 桌面應用程式。"""
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
