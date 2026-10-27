# 核心資料模型與引擎原型

本文件中的程式碼是完整核心方向的設計原型，不代表所有程式碼均已建立或測試。現行實作已包含 RequestModel、BodyMode、Environment、Collection、變數解析、Python Script、Response Extractor 與背景 Runner；Dataset 等仍待後續切片實作。

## Pydantic 模型、變數解析與 API 引擎

```python
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx
from jsonpath_ng.ext import parse as parse_jsonpath
from pydantic import BaseModel, ConfigDict, Field


class BodyMode(StrEnum):
    NONE = "none"
    JSON = "json"
    RAW = "raw"


class ExtractorKind(StrEnum):
    JSONPATH = "jsonpath"
    REGEX = "regex"


class ExtractorModel(BaseModel):
    """從回應本文萃取值並寫入指定執行期變數。"""

    model_config = ConfigDict(validate_assignment=True)

    target_variable: str = Field(min_length=1)
    kind: ExtractorKind
    expression: str = Field(min_length=1)
    group_index: int = Field(default=1, ge=1)


class RequestModel(BaseModel):
    """一次 HTTP 請求的可持久化設定。"""

    model_config = ConfigDict(validate_assignment=True)

    name: str = "Untitled request"
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    body_mode: BodyMode = BodyMode.NONE
    body: str = ""
    before_request_script: str = ""
    after_request_script: str = ""
    extractors: list[ExtractorModel] = Field(default_factory=list)


class EnvironmentModel(BaseModel):
    name: str
    variables: dict[str, Any] = Field(default_factory=dict)


class CollectionModel(BaseModel):
    name: str
    requests: list[RequestModel] = Field(default_factory=list)


@dataclass
class RunContext:
    """一個 Dataset iteration 的變數狀態；每列資料建立新實例。"""

    environment: EnvironmentModel
    data_row: dict[str, Any] = field(default_factory=dict)
    runtime_variables: dict[str, Any] = field(default_factory=dict)


class MissingVariableError(ValueError):
    pass


class VariableEngine:
    """使用 Data row > Runtime > Environment 優先序解析 {{key}}。"""

    _token_pattern = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")

    def __init__(self, context: RunContext) -> None:
        self.context = context

    def _resolve(self, key: str) -> Any:
        if key in self.context.data_row:
            return self.context.data_row[key]
        if key in self.context.runtime_variables:
            return self.context.runtime_variables[key]
        if key in self.context.environment.variables:
            return self.context.environment.variables[key]
        raise MissingVariableError(f"未定義變數：{{{{{key}}}}}")

    @staticmethod
    def _to_text(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if value is None:
            return ""
        return str(value)

    def render(self, text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            return self._to_text(self._resolve(match.group(1)))

        return self._token_pattern.sub(replace, text)

    def render_request(self, request: RequestModel) -> RequestModel:
        """複製請求後解析文字欄位，保留原始設定供 UI 重用。"""
        resolved = request.model_copy(deep=True)
        resolved.url = self.render(resolved.url)
        resolved.headers = {
            self.render(key): self.render(value)
            for key, value in resolved.headers.items()
        }
        resolved.params = {
            self.render(key): self.render(value)
            for key, value in resolved.params.items()
        }
        if resolved.body_mode is not BodyMode.NONE:
            resolved.body = self.render(resolved.body)
        return resolved


class ResponseSnapshot(BaseModel):
    status_code: int
    elapsed_ms: float
    headers: dict[str, str]
    body_text: str
    json_body: Any | None = None


class ApiResult(BaseModel):
    request_name: str
    transport_succeeded: bool
    response: ResponseSnapshot | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApiEngine:
    """同步執行單次請求；UI/Runner 應在背景執行緒呼叫。"""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ApiEngine:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _run_script(
        source: str,
        *,
        request: RequestModel,
        response: ResponseSnapshot | None,
        context: RunContext,
    ) -> None:
        if not source.strip():
            return

        # exec 可存取 Python 一般能力；只可執行使用者明確信任的腳本。
        scope = {
            "request": request,
            "response": response,
            "variables": context.runtime_variables,
        }
        exec(source, scope, scope)

    @staticmethod
    def _snapshot(response: httpx.Response, elapsed_ms: float) -> ResponseSnapshot:
        body_text = response.text
        try:
            json_body = response.json()
        except (ValueError, json.JSONDecodeError):
            json_body = None

        return ResponseSnapshot(
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            headers=dict(response.headers),
            body_text=body_text,
            json_body=json_body,
        )

    @staticmethod
    def _extract(
        request: RequestModel,
        response: ResponseSnapshot,
        context: RunContext,
        warnings: list[str],
    ) -> None:
        for extractor in request.extractors:
            try:
                if extractor.kind is ExtractorKind.JSONPATH:
                    payload = json.loads(response.body_text)
                    matches = parse_jsonpath(extractor.expression).find(payload)
                    if not matches:
                        warnings.append(
                            f"JSONPath 未匹配：{extractor.expression}"
                        )
                        continue
                    value = matches[0].value
                else:
                    match = re.search(extractor.expression, response.body_text)
                    if match is None:
                        warnings.append(f"正則未匹配：{extractor.expression}")
                        continue
                    value = match.group(extractor.group_index)

                # 僅成功匹配時更新；同名 Runtime 值採最新萃取結果。
                context.runtime_variables[extractor.target_variable] = value
            except Exception as exc:
                warnings.append(
                    f"萃取變數 {extractor.target_variable!r} 失敗：{exc}"
                )

    def execute(
        self,
        request: RequestModel,
        context: RunContext,
    ) -> ApiResult:
        result = ApiResult(
            request_name=request.name,
            transport_succeeded=False,
        )

        try:
            resolved = VariableEngine(context).render_request(request)
        except (MissingVariableError, ValueError) as exc:
            result.errors.append(str(exc))
            return result

        try:
            self._run_script(
                resolved.before_request_script,
                request=resolved,
                response=None,
                context=context,
            )
        except Exception as exc:
            result.errors.append(f"Before request script 失敗：{exc}")
            return result

        json_body: Any | None = None
        if resolved.body_mode is BodyMode.JSON:
            try:
                json_body = json.loads(resolved.body)
            except json.JSONDecodeError as exc:
                result.errors.append(f"JSON Body 格式錯誤：{exc}")
                return result

        headers = dict(resolved.headers)
        if resolved.body_mode is BodyMode.JSON and not any(
            key.lower() == "content-type" for key in headers
        ):
            headers["Content-Type"] = "application/json"

        started = time.perf_counter()
        try:
            response = self._client.request(
                method=resolved.method.upper(),
                url=resolved.url,
                headers=headers,
                params=resolved.params,
                content=(
                    resolved.body
                    if resolved.body_mode is BodyMode.RAW
                    else (
                        json.dumps(json_body, ensure_ascii=False).encode("utf-8")
                        if resolved.body_mode is BodyMode.JSON
                        else None
                    )
                ),
            )
        except httpx.RequestError as exc:
            result.errors.append(f"HTTP 傳輸失敗：{exc}")
            return result

        elapsed_ms = (time.perf_counter() - started) * 1000
        snapshot = self._snapshot(response, elapsed_ms)
        result.transport_succeeded = True
        result.response = snapshot

        try:
            self._run_script(
                resolved.after_request_script,
                request=resolved,
                response=snapshot,
                context=context,
            )
        except Exception as exc:
            # After script 錯誤不阻止 Extractors 執行。
            result.errors.append(f"After request script 失敗：{exc}")

        self._extract(resolved, snapshot, context, result.warnings)
        return result
```

## 原型使用方式

```python
environment = EnvironmentModel(
    name="Dev",
    variables={"base_url": "https://api.example.test", "token": ""},
)
context = RunContext(environment=environment)

login = RequestModel(
    name="Login",
    method="POST",
    url="{{base_url}}/login",
    body_mode=BodyMode.JSON,
    body='{"username":"demo","password":"secret"}',
    extractors=[
        ExtractorModel(
            target_variable="token",
            kind=ExtractorKind.JSONPATH,
            expression="$.token",
        )
    ],
)

profile = RequestModel(
    name="Profile",
    method="GET",
    url="{{base_url}}/profile",
    headers={"Authorization": "Bearer {{token}}"},
)

with ApiEngine() as engine:
    login_result = engine.execute(login, context)
    profile_result = engine.execute(profile, context)
```

## 原型限制與後續工作

- 變數採文字替換；JSON Body 替換後再由 JSON parser 驗證。字串值應依 JSON 字串語法使用引號，Body 無效時不發送。
- Regex extractor 預設取第一個捕獲群組；若表達式沒有該群組，記錄警告且不更新變數。
- JSONPath 有多筆結果時取第一筆；萃取失敗不覆寫舊值。
- HTTP 4xx/5xx 仍會回傳 `transport_succeeded=True`；狀態碼斷言屬後續功能。
- Before/After scripts 是任意 Python 程式碼，不具沙箱保護。Before script 執行於變數替換後，修改 request 會影響本次發送；修改 runtime variables 不會讓本次已解析欄位重新替換。
- 上述原型尚未加入 Dataset Loader、Qt Runner、取消機制、檔案儲存與完整驗證測試。
