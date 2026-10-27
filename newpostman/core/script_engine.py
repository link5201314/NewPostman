from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from newpostman.models.request import RequestModel

if TYPE_CHECKING:
    from newpostman.core.api_engine import ResponseSnapshot


@dataclass(slots=True)
class ScriptContext:
    """Python Script 可使用的 Request、Response 與 Runtime variable 介面。"""

    request: RequestModel
    runtime_variables: dict[str, str]
    response: ResponseSnapshot | None = None


class ScriptExecutionError(RuntimeError):
    """使用者 Python Script 執行失敗。"""


class ScriptEngine:
    """以一般 Python 執行使用者明確提供且受信任的 Script。"""

    def execute(self, script: str, context: ScriptContext, stage: str) -> None:
        """執行 Script；程式碼具有目前 Python 程序的一般權限。

        Args:
            script: 使用者提供的 Python 程式碼。
            context: Script 可讀寫的執行上下文。
            stage: 錯誤訊息顯示的階段名稱。

        Raises:
            ScriptExecutionError: Script 發生任何一般 Python 例外。
        """
        if not script.strip():
            return
        namespace = {"context": context}
        try:
            exec(compile(script, f"<{stage} Script>", "exec"), namespace, namespace)
        # 受信任的任意 Python 程式可拋出任何 Exception 子類；此處是隔離使用者
        # Script 失敗並交由單項 Request/Runner 記錄的唯一執行邊界。
        except Exception as exc:
            raise ScriptExecutionError(f"{stage} Script 執行失敗：{exc}") from exc
