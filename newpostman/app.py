from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from newpostman.ui.request_editor import RequestEditor


def main() -> int:
    """啟動 NewPostman 桌面應用程式。"""
    app = QApplication.instance() or QApplication(sys.argv)
    editor = RequestEditor()
    editor.resize(820, 760)
    editor.show()
    return app.exec()
