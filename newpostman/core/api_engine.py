from __future__ import annotations

import json
import time
from typing import Self

import httpx
from pydantic import BaseModel, Field

from newpostman.models.request import BodyMode, RequestModel


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

    def execute(self, request: RequestModel) -> ApiResult:
        """發送 Request，回傳 Response 摘要或可呈現的錯誤。

        Args:
            request: 要發送的 HTTP Request 設定。

        Returns:
            含 Response 摘要或錯誤訊息的執行結果。
        """
        try:
            content: bytes | None = None
            headers = dict(request.headers)

            if request.body_mode is BodyMode.JSON:
                try:
                    json_body = json.loads(request.body)
                except json.JSONDecodeError as exc:
                    return ApiResult(error=f"JSON Body 格式錯誤：{exc.msg}")
                content = json.dumps(
                    json_body,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                if not any(key.lower() == "content-type" for key in headers):
                    headers["Content-Type"] = "application/json"
            elif request.body_mode is BodyMode.RAW:
                content = request.body.encode("utf-8")

            started_at = time.perf_counter()
            url = httpx.URL(request.url).copy_merge_params(request.params)
            response = self._client.request(
                method=request.method.upper(),
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
            return ApiResult(response=snapshot)
        except httpx.RequestError as exc:
            return ApiResult(error=f"HTTP 傳輸失敗：{exc}")
        except (httpx.InvalidURL, ValueError) as exc:
            return ApiResult(error=f"Request 設定錯誤：{exc}")
