from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from newpostman.models.request import RequestModel


class CollectionModel(BaseModel):
    """依序包含 Request 的 Collection。"""

    model_config = ConfigDict(validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    requests: list[RequestModel] = Field(default_factory=list)
