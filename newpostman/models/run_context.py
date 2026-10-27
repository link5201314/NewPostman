from __future__ import annotations

from pydantic import BaseModel, Field

from newpostman.models.environment import EnvironmentModel


class RunContext(BaseModel):
    """單次 Collection 執行共用的 Environment 與 Runtime variable 狀態。"""

    environment: EnvironmentModel | None = None
    data_row: dict[str, str] = Field(default_factory=dict)
    runtime_variables: dict[str, str] = Field(default_factory=dict)
