from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Mapping, Protocol

from ..data.pagination import CollectedSource

from .ingestion import IngestionReport, InspectionIngestor


UTC = dt.timezone.utc


class RowCollector(Protocol):
    """Collect raw inspection rows for a window.

    The collector owns the upstream transport (AEE/MCS8/Legacy) and returns
    ``CollectedSource`` entries keyed by the ingestor's accepted names
    (``device_status``, ``media_files``, ``alarms``), preserving completeness
    metadata. It is the only component that depends on upstream
    authentication; the scheduler never does.
    """

    async def collect(
        self,
        start: dt.datetime,
        end: dt.datetime,
    ) -> Mapping[str, CollectedSource]:
        ...


@dataclass(frozen=True, slots=True)
class ScheduledIngestion:
    report: IngestionReport
    sources: tuple[CollectedSource, ...]


class InspectionIngestionScheduler:
    """Orchestrate collect -> normalize -> persist for inspection history.

    The scheduler is deliberately thin and source-agnostic: it computes an
    explicit window, delegates collection to an injected ``RowCollector`` and
    persists via ``InspectionIngestor``. It never assumes AEE authentication
    behavior, which remains an unverified prerequisite owned by the collector.
    """

    def __init__(
        self,
        collector: RowCollector,
        ingestor: InspectionIngestor,
    ) -> None:
        self._collector = collector
        self._ingestor = ingestor

    async def run_once(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
    ) -> ScheduledIngestion:
        start_utc = _aware_utc(start, "start")
        end_utc = _aware_utc(end, "end")
        if end_utc <= start_utc:
            raise ValueError("end must be after start")
        collected = await self._collector.collect(start_utc, end_utc)
        payloads = {
            name: source.rows
            for name, source in collected.items()
            if source.status == "ok"
        }
        source_errors = {
            name: source.error_code
            for name, source in collected.items()
            if source.status == "error"
        }
        observed_at = dt.datetime.now(UTC)
        report = await self._ingestor.ingest_all(
            payloads,
            observed_at=observed_at,
            ingested_at=observed_at,
            source_errors=source_errors,
        )
        return ScheduledIngestion(
            report=report,
            sources=tuple(collected.values()),
        )

    async def run_recent(
        self,
        *,
        days: int = 1,
    ) -> ScheduledIngestion:
        normalized_days = max(1, min(int(days), 90))
        end = dt.datetime.now(UTC)
        start = end - dt.timedelta(days=normalized_days)
        return await self.run_once(start=start, end=end)


def _aware_utc(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
