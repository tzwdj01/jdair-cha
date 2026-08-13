from __future__ import annotations

from pydantic import BaseModel, Field


class AddStreamRequest(BaseModel):
    device_id: str = Field(
        min_length=2,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
