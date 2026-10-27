from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DatasetModel(BaseModel):
    """Project 登錄的外部 Dataset 檔案參照。"""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    path: Path
