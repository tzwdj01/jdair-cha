from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Mapping

from .normalization import DeviceStatusEvent
from .store import InspectionStore


UTC = dt.timezone.utc


@dataclass(frozen=True, slots=True)
class DeviceSnapshotProcessingResult:
    """Result of turning an MCS8 current-status snapshot into CHA events.

    A polling snapshot is NOT a native transition feed. On the first
    observation each device receives an ``INITIAL_OBSERVATION``. Later
    snapshots are compared against the store's latest known state: an
    unchanged state produces NO new event; a changed state produces exactly
    one ``CHA_OBSERVED_TRANSITION``.
    """

    events_to_store: tuple[DeviceStatusEvent, ...]
    initial_observation_count: int
    transition_count: int
    unchanged_count: int
    skipped_device_count: int
    quality_flags: tuple[str, ...]


class MCS8DeviceSnapshotProcessor:
    """Turn MCS8 current-status snapshots into honest CHA observations.

    Semantics (per the M4 P3.2 authorization):

    * First observation of a device => ``INITIAL_OBSERVATION``
      (source system ``mcs8``, quality ``initial_snapshot``).
    * Later snapshot with the same online state => no event (no row growth
      from polling).
    * Later snapshot with a changed online state => exactly one
      ``CHA_OBSERVED_TRANSITION`` flagged ``observed_by_polling`` and
      ``partial_transition_visibility`` (a poll cannot observe a transition
      that happened and recovered between two polls).

    The processor never fabricates an upstream-native transition: the
    ``mcs8`` source system is distinct from the AEE ``DevOnlineList`` native
    feed (``aee``), so the data model keeps the two clearly separated.
    """

    def __init__(self, store: InspectionStore) -> None:
        self._store = store

    async def process_snapshot(
        self,
        snapshot_events: Iterable[DeviceStatusEvent],
        *,
        source_system: str = "mcs8",
    ) -> DeviceSnapshotProcessingResult:
        candidates = tuple(snapshot_events)
        if not candidates:
            return DeviceSnapshotProcessingResult(
                events_to_store=(),
                initial_observation_count=0,
                transition_count=0,
                unchanged_count=0,
                skipped_device_count=0,
                quality_flags=(),
            )

        device_ids = {event.device_id for event in candidates}
        latest = await self._store.fetch_latest_device_statuses(
            device_ids=device_ids,
            source_system=source_system,
        )

        events_to_store: list[DeviceStatusEvent] = []
        initial_observation_count = 0
        transition_count = 0
        unchanged_count = 0

        for event in candidates:
            previous = latest.get(event.device_id)
            if previous is None:
                flags = _with_flag(
                    event.quality_flags,
                    "initial_snapshot",
                )
                events_to_store.append(_with_flags(event, flags))
                initial_observation_count += 1
                continue

            if previous.online == event.online:
                unchanged_count += 1
                continue

            flags = {
                "cha_observed_transition",
                "observed_by_polling",
                "partial_transition_visibility",
            }
            events_to_store.append(_with_flags(event, flags))
            transition_count += 1

        skipped_device_count = max(
            0,
            len({event.device_id for event in candidates})
            - len({event.device_id for event in events_to_store}),
        )
        result_flags: set[str] = set()
        if initial_observation_count:
            result_flags.add("initial_snapshot")
        if transition_count:
            result_flags.add("cha_observed_transition")
        if unchanged_count:
            result_flags.add("polling_unchanged_skipped")

        return DeviceSnapshotProcessingResult(
            events_to_store=tuple(events_to_store),
            initial_observation_count=initial_observation_count,
            transition_count=transition_count,
            unchanged_count=unchanged_count,
            skipped_device_count=skipped_device_count,
            quality_flags=tuple(sorted(result_flags)),
        )

    async def store_result(
        self,
        result: DeviceSnapshotProcessingResult,
    ) -> int:
        return await self._store.upsert_device_status_events(
            result.events_to_store
        )


def _with_flag(
    flags: tuple[str, ...],
    flag: str,
) -> tuple[str, ...]:
    return tuple(sorted(set(flags) | {flag}))


def _with_flags(
    event: DeviceStatusEvent,
    extra: set[str] | tuple[str, ...],
) -> DeviceStatusEvent:
    return DeviceStatusEvent(
        source_system=event.source_system,
        source_record_id=event.source_record_id,
        device_id=event.device_id,
        group_id=event.group_id,
        device_type_code=event.device_type_code,
        status_code=event.status_code,
        online=event.online,
        occurred_at=event.occurred_at,
        observed_at=event.observed_at,
        ingested_at=event.ingested_at,
        quality_flags=tuple(
            sorted(set(event.quality_flags) | set(extra))
        ),
    )
