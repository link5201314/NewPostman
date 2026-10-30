from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QStandardPaths, Signal

DEFAULT_FILE_LEVEL = "DEBUG"
DEFAULT_UI_LEVEL = "INFO"
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
SUPPORTED_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|proxy-authorization|cookie|set-cookie|password|"
    r"passwd|client_secret|access_token|refresh_token|api_key)"
    r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_AUTH_PATTERN = re.compile(
    r"(?i)(authorization|proxy-authorization)(\s*[:=]\s*)"
    r"(?:Bearer|Basic|AR-JWT)\s+[^\s,;&]+"
)


class LogSettings:
    """獨立設定本地檔案與 UI 的日誌等級。"""

    def __init__(self, file_level: str, ui_level: str) -> None:
        self.file_level = file_level
        self.ui_level = ui_level

    @classmethod
    def from_json(cls, data: Any) -> LogSettings:
        """從 JSON 物件讀取設定；無效等級分別回退預設值。"""
        if not isinstance(data, dict):
            raise ValueError("logging.json 根節點必須是 JSON 物件。")
        file_level = cls._normalize_level(data.get("file_level"), DEFAULT_FILE_LEVEL)
        ui_level = cls._normalize_level(data.get("ui_level"), DEFAULT_UI_LEVEL)
        return cls(file_level=file_level, ui_level=ui_level)

    @staticmethod
    def _normalize_level(value: Any, default: str) -> str:
        if not isinstance(value, str):
            return default
        level = value.upper()
        return level if level in SUPPORTED_LEVELS else default

    def to_json(self) -> dict[str, str]:
        """轉成可持久化的設定字典。"""
        return {"file_level": self.file_level, "ui_level": self.ui_level}


class LogBridge(QObject):
    """以 Qt Signal 將 Python 日誌安全地轉送至 UI 執行緒。"""

    message = Signal(str)


class _RedactingFilter(logging.Filter):
    """遮蔽日誌訊息中常見的憑證欄位。"""

    def filter(self, record: logging.LogRecord) -> bool:
        message = redact_sensitive_text(record.getMessage())
        record.msg = message
        record.args = ()
        if record.exc_info:
            record.exc_text = redact_sensitive_text(
                logging.Formatter().formatException(record.exc_info)
            )
        return True


def redact_sensitive_text(message: str) -> str:
    """遮蔽常見敏感欄位，避免一般應用程式日誌直接洩漏憑證。"""
    message = _AUTH_PATTERN.sub(r"\1\2[REDACTED]", message)
    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", message)


def default_config_path() -> Path:
    """取得作業系統使用者設定目錄中的 logging.json 路徑。"""
    app_config = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    if app_config:
        return Path(app_config) / "logging.json"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "NewPostman" / "logging.json"
    return Path.home() / ".config" / "NewPostman" / "logging.json"


class LoggingService:
    """設定應用程式日誌並提供檔案與 UI 的獨立等級篩選。"""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or default_config_path()
        self.log_path = self.config_path.with_name("newpostman.log")
        self.bridge = LogBridge()
        self.settings, config_error = self._load_settings()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("newpostman")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        self._logger = logger
        self._handlers: list[logging.Handler] = []
        self._install_handlers()
        if config_error:
            logger.warning("讀取日誌設定失敗，使用預設值：%s", config_error)
        logger.info("日誌檔案：%s", self.log_path)
        self._previous_sys_hook = sys.excepthook
        self._previous_thread_hook = threading.excepthook
        sys.excepthook = self._handle_uncaught_exception
        threading.excepthook = self._handle_uncaught_thread_exception

    def _load_settings(self) -> tuple[LogSettings, str | None]:
        if not self.config_path.exists():
            settings = LogSettings(DEFAULT_FILE_LEVEL, DEFAULT_UI_LEVEL)
            self._write_settings(settings)
            return settings, None
        try:
            settings = LogSettings.from_json(
                json.loads(self.config_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return LogSettings(DEFAULT_FILE_LEVEL, DEFAULT_UI_LEVEL), str(exc)
        return settings, None

    def _write_settings(self, settings: LogSettings) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(settings.to_json(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _install_handlers(self) -> None:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        redactor = _RedactingFilter()

        file_handler = logging.handlers.RotatingFileHandler(
            self.log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(self.settings.file_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)

        ui_handler = _UiLogHandler(self.bridge)
        ui_handler.setLevel(self.settings.ui_level)
        ui_handler.setFormatter(formatter)
        ui_handler.addFilter(redactor)

        for handler in (file_handler, ui_handler):
            self._logger.addHandler(handler)
            self._handlers.append(handler)

    def _handle_uncaught_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: Any,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            self._previous_sys_hook(exc_type, exc_value, exc_traceback)
            return
        self._logger.critical(
            "未處理的應用程式例外",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _handle_uncaught_thread_exception(
        self,
        args: threading.ExceptHookArgs,
    ) -> None:
        exception = args.exc_value or RuntimeError("執行緒未提供例外內容")
        self._logger.critical(
            "未處理的執行緒例外（thread=%s）",
            args.thread.name if args.thread is not None else "unknown",
            exc_info=(args.exc_type, exception, args.exc_traceback),
        )

    def close(self) -> None:
        """移除日誌 Handler 並還原全域例外處理器。"""
        for handler in self._handlers:
            self._logger.removeHandler(handler)
            handler.close()
        self._handlers.clear()
        if sys.excepthook == self._handle_uncaught_exception:
            sys.excepthook = self._previous_sys_hook
        if threading.excepthook == self._handle_uncaught_thread_exception:
            threading.excepthook = self._previous_thread_hook


class _UiLogHandler(logging.Handler):
    """以 Signal 將符合等級的格式化日誌送到診斷面板。"""

    def __init__(self, bridge: LogBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._bridge.message.emit(self.format(record))
        except RuntimeError:
            self.handleError(record)
