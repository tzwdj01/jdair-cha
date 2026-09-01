from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Optional client context for a CHA realtime session.

    ``maintenance_wxb`` is a narrow Legacy integration scope. The server
    enforces it when devices are listed and when streams are added; it is not a
    frontend-only filter.
    """

    scope: Literal["all", "maintenance_wxb"] = "all"


class AddStreamRequest(BaseModel):
    device_id: str = Field(
        min_length=2,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
