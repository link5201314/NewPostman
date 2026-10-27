from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BodyMode(StrEnum):
    """Request 本文的傳送模式。"""

    NONE = "none"
    JSON = "json"
    RAW = "raw"


class RequestModel(BaseModel):
    """單一 HTTP Request 的設定。"""

    model_config = ConfigDict(validate_assignment=True)

    name: str = "Untitled request"
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    body_mode: BodyMode = BodyMode.NONE
    body: str = ""
