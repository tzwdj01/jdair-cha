from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Iterable

from ..normalization import (
    AlarmEvent,
    DeviceLocationEvent,
    DeviceStatusEvent,
    MediaFile,
)
from ..realtime_views import RealtimeViewEvent


class InspectionStore(ABC):
    """Persistence seam for CHA inspection history.

    Implementations may be backed by PostgreSQL, an in-memory test store or a
    future staging adapter. Methods are deliberately narrow: durable rows in,
    scoped rows out. Deterministic aggregation stays in
    ``app.data.metrics``.
    """

    @abstractmethod
    async def upsert_device_status_events(
        self,
        events: Iterable[DeviceStatusEvent],
    ) -> int:
        """Persist status observations; latest observation wins per identity."""

    @abstractmethod
    async def fetch_device_status_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[DeviceStatusEvent, ...]:
        """Return status events in the inclusive time range, time-ordered."""

    @abstractmethod
    async def upsert_device_location_events(
        self,
        events: Iterable[DeviceLocationEvent],
    ) -> int:
        """Persist location events; latest observation wins per identity."""

    @abstractmethod
    async def fetch_device_location_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[DeviceLocationEvent, ...]:
        """Return location events in the inclusive time range, time-ordered."""

    @abstractmethod
    async def upsert_media_files(
        self,
        files: Iterable[MediaFile],
    ) -> int:
        """Persist media metadata; latest observation wins when a source ID
        exists, otherwise rows are appended and flagged."""

    @abstractmethod
    async def fetch_media_files(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[MediaFile, ...]:
        """Return media rows whose source time falls in the range,
        time-ordered."""

    @abstractmethod
    async def upsert_realtime_view_events(
        self,
        events: Iterable[RealtimeViewEvent],
    ) -> int:
        """Persist finalized viewing events; the first finalization per
        ``stream_id`` wins."""

    @abstractmethod
    async def fetch_realtime_view_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        usernames: Iterable[str] | None = None,
    ) -> tuple[RealtimeViewEvent, ...]:
        """Return finalized view events closed within the range,
        time-ordered."""

    @abstractmethod
    async def upsert_alarm_events(
        self,
        events: Iterable[AlarmEvent],
    ) -> int:
        """Persist alarm observations; latest observation wins per identity."""

    @abstractmethod
    async def fetch_alarm_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[AlarmEvent, ...]:
        """Return alarm events in the inclusive time range, time-ordered."""
