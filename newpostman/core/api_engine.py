from __future__ import annotations

import json
import logging
import time
from typing import Self

import httpx
from pydantic import BaseModel, Field

from newpostman.core.response_extractor import ResponseExtractor
from newpostman.core.script_engine import ScriptContext, ScriptEngine, ScriptExecutionError
from newpostman.core.variable_engine import MissingVariableError, VariableEngine
from newpostman.models.environment import EnvironmentModel
from newpostman.models.request import BodyMode, RequestModel
from newpostman.models.run_context import RunContext

logger = logging.getLogger(__name__)


class ResponseSnapshot(BaseModel):
    """供 UI 呈現的 HTTP Response 摘要。"""

    status_code: int
    elapsed_ms: float
    headers: dict[str, str]
    body_text: str


class ApiResult(BaseModel):
    """單次 HTTP 呼叫結果；HTTP 錯誤狀態仍是成功收到的 Response。"""

    response: ResponseSnapshot | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ApiEngine:
    """執行單一 HTTP Request，可注入 HTTPX Client 以測試傳輸。"""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        """初始化 API 引擎與 HTTPX Client。

        Args:
            client: 可選的 HTTPX Client；傳入時由呼叫端管理生命週期。
            timeout_seconds: 引擎自行建立 Client 時使用的逾時秒數。
        """
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        """關閉引擎自行建立的 HTTP Client。"""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def execute(
        self,
        request: RequestModel,
        environment: EnvironmentModel | None = None,
        *,
        run_context: RunContext | None = None,
    ) -> ApiResult:
        """發送 Request，回傳 Response 摘要或可呈現的錯誤。

        Args:
            request: 要發送的 HTTP Request 設定。
            environment: 用於解析樣板的作用 Environment。
            run_context: 可選的執行上下文；提供 Runtime variable 與 Data row。

        Returns:
            含 Response 摘要或錯誤訊息的執行結果。
        """
        context = run_context or RunContext(environment=environment)
        variables = VariableEngine(
            context.environment,
            context.runtime_variables,
            context.data_row,
        )
        script_engine = ScriptEngine()
        extractor = ResponseExtractor()
        try:
            resolved = request.model_copy(deep=True)
            resolved.url = variables.render(resolved.url)
            resolved.headers = {
                variables.render(key): variables.render(value)
                for key, value in resolved.headers.items()
            }
            resolved.params = {
                variables.render(key): variables.render(value)
                for key, value in resolved.params.items()
            }
            if resolved.body_mode is not BodyMode.NONE:
                resolved.body = variables.render(resolved.body)

            script_context = ScriptContext(
                request=resolved,
                runtime_variables=context.runtime_variables,
                request_name=resolved.name,
            )

            def log_script_message(message: str) -> None:
                logger.info(
                    "Script log | Request=%s | stage=%s | %s",
                    script_context.request_name,
                    script_context.script_stage,
                    message,
                )

            script_context.log_callback = log_script_message
            try:
                script_context.script_stage = "Before request"
                script_engine.execute(
                    resolved.before_script,
                    script_context,
                    "Before request",
                )
            except ScriptExecutionError as exc:
                logger.error("Before request Script failed | Request=%s", resolved.name)
                logger.debug("Before request Script exception", exc_info=exc)
                return ApiResult(error=str(exc))

            content: bytes | None = None
            headers = dict(resolved.headers)

            if resolved.body_mode is BodyMode.JSON:
                try:
                    json_body = json.loads(resolved.body)
                except json.JSONDecodeError as exc:
                    logger.error(
                        "Invalid JSON request body | Request=%s | %s",
                        resolved.name,
                        exc.msg,
                    )
                    return ApiResult(error=f"JSON Body 格式錯誤：{exc.msg}")
                content = json.dumps(
                    json_body,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                if not any(key.lower() == "content-type" for key in headers):
                    headers["Content-Type"] = "application/json"
            elif resolved.body_mode is BodyMode.RAW:
                content = resolved.body.encode("utf-8")

            started_at = time.perf_counter()
            url = httpx.URL(resolved.url).copy_merge_params(resolved.params)
            logger.info(
                "Sending HTTP request | Request=%s | method=%s | url=%s",
                resolved.name,
                resolved.method.upper(),
                url,
            )
            response = self._client.request(
                method=resolved.method.upper(),
                url=url,
                headers=headers,
                content=content,
            )
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            snapshot = ResponseSnapshot(
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
                headers=dict(response.headers),
                body_text=response.text,
            )
            logger.info(
                "HTTP response received | Request=%s | status=%s | elapsed_ms=%.1f",
                resolved.name,
                snapshot.status_code,
                elapsed_ms,
            )
            script_context.response = snapshot
            script_error: str | None = None
            try:
                script_context.script_stage = "After request"
                script_engine.execute(
                    resolved.after_script,
                    script_context,
                    "After request",
                )
            except ScriptExecutionError as exc:
                script_error = str(exc)
                logger.error("After request Script failed | Request=%s", resolved.name)
                logger.debug("After request Script exception", exc_info=exc)
            warnings = extractor.extract(
                snapshot.body_text,
                resolved.extractors,
                context.runtime_variables,
            )
            for warning in warnings:
                logger.warning("Response Extractor warning | Request=%s | %s", resolved.name, warning)
            return ApiResult(response=snapshot, error=script_error, warnings=warnings)
        except MissingVariableError as exc:
            logger.error("Request variable resolution failed | %s", exc)
            return ApiResult(error=str(exc))
        except httpx.RequestError as exc:
            logger.exception("HTTP transport failed")
            return ApiResult(error=f"HTTP 傳輸失敗：{exc}")
        except (httpx.InvalidURL, ValueError) as exc:
            logger.exception("Invalid request configuration")
            return ApiResult(error=f"Request 設定錯誤：{exc}")
