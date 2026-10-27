from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class BodyMode(StrEnum):
    """Request 本文的傳送模式。"""

    NONE = "none"
    JSON = "json"
    RAW = "raw"


class ExtractorType(StrEnum):
    """Response Body 萃取規則的類型。"""

    JSONPATH = "jsonpath"
    REGEX = "regex"


class ExtractorModel(BaseModel):
    """從 Response Body 萃取值並寫入 Runtime variable 的規則。"""

    variable_name: str = Field(min_length=1)
    kind: ExtractorType
    expression: str = Field(min_length=1)
    group_index: int = Field(default=1, ge=0)


class RequestModel(BaseModel):
    """單一 HTTP Request 的設定。"""

    model_config = ConfigDict(validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    name: str = "Untitled request"
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    body_mode: BodyMode = BodyMode.NONE
    body: str = ""
    before_script: str = ""
    after_script: str = ""
    extractors: list[ExtractorModel] = Field(default_factory=list)
