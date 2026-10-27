from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


TRUSTED_SCRIPT_WARNING = (
    "Python Script 會以受信任程式碼執行，可使用一般 Python 能力，"
    "包括讀寫本機檔案或執行其他本機操作。NewPostman 不提供安全沙箱；"
    "請只執行你信任的 Script。"
)


def warn_about_trusted_scripts(parent: QWidget) -> None:
    """執行使用者 Script 前清楚說明其一般 Python 權限與信任邊界。"""
    QMessageBox.warning(parent, "Python Script 安全提醒", TRUSTED_SCRIPT_WARNING)
