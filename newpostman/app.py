from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from newpostman.diagnostics import LoggingService
from newpostman.ui.main_window import MainWindow


def main() -> int:
    """啟動 NewPostman 桌面應用程式。"""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("NewPostman")
    app.setOrganizationName("NewPostman")
    logging_service = LoggingService()
    window = MainWindow(logging_service=logging_service)
    window.show()
    try:
        return app.exec()
    finally:
        logging_service.close()
