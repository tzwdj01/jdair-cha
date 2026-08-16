from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..data.normalization import (
    normalize_alarm_events,
    normalize_device_status_events,
    normalize_media_files,
)
from ..data.store import InspectionStore


SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class SourceIngestionResult:
    source: str
    accepted_count: int
    invalid_row_count: int
    quality_flags: tuple[str, ...]
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class IngestionReport:
    results: tuple[SourceIngestionResult, ...]
    generated_at: dt.datetime
    completed: bool


class InspectionIngestor:
    """Persist collected inspection rows through normalization into the store.

    This is the write-side seam for AEE/MCS8 data: a future ingestion scheduler
    collects raw rows (DevOnlineList, RecordFileList, AlarmList), then calls
    this ingestor to normalize and persist them. It is fully testable with
    in-memory stores and does not depend on AEE authentication; the live AEE
    token/session behavior is a separate, still-unverified prerequisite that is
    not assumed here.

    Every result reports accepted and invalid row counts plus quality flags, so
    partial or low-confidence data is never silently treated as complete.
    """

    def __init__(
        self,
        store: InspectionStore,
        source_timezone: dt.tzinfo = SHANGHAI,
    ) -> None:
        self._store = store
        self._source_timezone = source_timezone

    async def ingest_device_status(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        observed_at: dt.datetime,
        ingested_at: dt.datetime,
    ) -> SourceIngestionResult:
        normalized = normalize_device_status_events(
            rows,
            source_timezone=self._source_timezone,
            observed_at=observed_at,
            ingested_at=ingested_at,
        )
        await self._store.upsert_device_status_events(normalized.events)
        return SourceIngestionResult(
            source="device_status",
            accepted_count=len(normalized.events),
            invalid_row_count=normalized.invalid_row_count,
            quality_flags=normalized.quality_flags,
        )

    async def ingest_media_files(
        self,
        files: Iterable[Mapping[str, Any]],
        *,
        observed_at: dt.datetime,
        ingested_at: dt.datetime,
        include_restricted: bool = False,
    ) -> SourceIngestionResult:
        normalized = normalize_media_files(
            files,
            source_timezone=self._source_timezone,
            observed_at=observed_at,
            ingested_at=ingested_at,
            include_restricted=include_restricted,
        )
        await self._store.upsert_media_files(normalized.files)
        return SourceIngestionResult(
            source="media_files",
            accepted_count=len(normalized.files),
            invalid_row_count=normalized.invalid_row_count,
            quality_flags=normalized.quality_flags,
        )

    async def ingest_alarms(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        observed_at: dt.datetime,
        ingested_at: dt.datetime,
        include_restricted: bool = False,
    ) -> SourceIngestionResult:
        normalized = normalize_alarm_events(
            rows,
            source_timezone=self._source_timezone,
            observed_at=observed_at,
            ingested_at=ingested_at,
            include_restricted=include_restricted,
        )
        await self._store.upsert_alarm_events(normalized.events)
        return SourceIngestionResult(
            source="alarms",
            accepted_count=len(normalized.events),
            invalid_row_count=normalized.invalid_row_count,
            quality_flags=normalized.quality_flags,
        )

    async def ingest_all(
        self,
        payloads: Mapping[
            str,
            Iterable[Mapping[str, Any]],
        ],
        *,
        observed_at: dt.datetime,
        ingested_at: dt.datetime,
        source_errors: Mapping[str, str] | None = None,
    ) -> IngestionReport:
        """Orchestrate every source and keep the run resumable.

        Each source is persisted independently. A failure in one source is
        reported (``error_code`` on that result) instead of aborting the whole
        run, so an earlier successful source is never rolled back into a
        half-baked state and a retry is idempotent. Raw exception text is
        never placed into the report; the detailed error is left to the
        caller's logging.
        """

        results: list[SourceIngestionResult] = []
        if "device_status" in payloads:
            results.append(
                await self._ingest_source(
                    self.ingest_device_status(
                        payloads["device_status"],
                        observed_at=observed_at,
                        ingested_at=ingested_at,
                    ),
                    "device_status",
                )
            )
        if "media_files" in payloads:
            results.append(
                await self._ingest_source(
                    self.ingest_media_files(
                        payloads["media_files"],
                        observed_at=observed_at,
                        ingested_at=ingested_at,
                    ),
                    "media_files",
                )
            )
        if "alarms" in payloads:
            results.append(
                await self._ingest_source(
                    self.ingest_alarms(
                        payloads["alarms"],
                        observed_at=observed_at,
                        ingested_at=ingested_at,
                    ),
                    "alarms",
                )
            )

        for source, error_code in sorted(
            dict(source_errors or {}).items()
        ):
            results.append(
                SourceIngestionResult(
                    source=source,
                    accepted_count=0,
                    invalid_row_count=0,
                    quality_flags=("source_collection_failed",),
                    error_code=error_code,
                )
            )
        completed = all(
            result.error_code is None
            and result.invalid_row_count == 0
            for result in results
        )
        return IngestionReport(
            results=tuple(
                sorted(results, key=lambda item: item.source)
            ),
            generated_at=dt.datetime.now(dt.timezone.utc),
            completed=completed,
        )

    async def _ingest_source(
        self,
        pending,
        source: str,
    ) -> SourceIngestionResult:
        try:
            return await pending
        except Exception:
            return SourceIngestionResult(
                source=source,
                accepted_count=0,
                invalid_row_count=0,
                quality_flags=("source_ingest_failed",),
                error_code="SOURCE_INGEST_FAILED",
            )
