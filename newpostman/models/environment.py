from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentModel(BaseModel):
    """Environment 名稱及其 key-value 變數。"""

    model_config = ConfigDict(validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    variables: dict[str, str] = Field(default_factory=dict)
