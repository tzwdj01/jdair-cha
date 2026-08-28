from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from ..data.inspection_records import (
    InspectionAuditEvent,
    InspectionRecord,
    InspectionRecordFilter,
    InspectionRecordPage,
    InspectionRecordViewLink,
    build_audit_event,
    build_inspection_record,
    link_view_events,
)
from ..data.store import InspectionRecordStore


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class InspectionRecordDetail:
    record: InspectionRecord
    realtime_view_event_ids: tuple[str, ...]
    audit_events: tuple[InspectionAuditEvent, ...]


@dataclass(frozen=True, slots=True)
class InspectionDashboardMetrics:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    coverage: tuple[str, int, int, str]  # (completeness, requested, available, detail)
    total_count: int
    total_duration_seconds: float
    participant_count: int
    per_account: tuple[tuple[str, int, float], ...]
    per_device: tuple[tuple[str, int, float], ...]
    aircraft_count: int
    flight_count: int
    task_count: int
    issue_found_count: int
    no_issue_count: int
    issue_rate: float | None
    issue_type_counts: tuple[tuple[str, int], ...]
    issue_level_counts: tuple[tuple[str, int], ...]
    issue_device_ranking: tuple[tuple[str, int], ...]
    issue_aircraft_ranking: tuple[tuple[str, int], ...]
    issue_station_ranking: tuple[tuple[str, int], ...]
    issue_trend: tuple[tuple[str, int], ...]


class InspectionRecordService:
    """CHA inspection workflow: draft / submit / correct + query + metrics.

    ``inspector_username`` / ``device_id`` are trusted server facts; the
    caller (API layer) must derive them from the authenticated CHA session
    and the realtime stream, never from ordinary user input. A record can
    only be edited in DRAFT; SUBMITTED records are corrected with a preserved
    audit trail (correction model), never overwritten in place.
    """

    def __init__(
        self,
        store: InspectionRecordStore,
        business_timezone: dt.tzinfo = SHANGHAI,
    ) -> None:
        self._store = store
        self._business_tz = business_timezone

    async def create_draft(
        self,
        *,
        inspector_user_id: str | None,
        inspector_username: str,
        device_id: str,
        inspection_started_at: dt.datetime,
        inspection_ended_at: dt.datetime,
        aircraft_no: str | None = None,
        flight_source_id: str | None = None,
        flight_no: str | None = None,
        routine_task_source_id: str | None = None,
        maintenance_task_text: str | None = None,
        station: str | None = None,
        location_text: str | None = None,
        has_issue: bool = False,
        issue_type: str | None = None,
        issue_level: str | None = None,
        issue_description: str | None = None,
        remark: str | None = None,
        realtime_view_event_ids: Iterable[str] = (),
    ) -> InspectionRecordDetail:
        record = build_inspection_record(
            inspector_user_id=inspector_user_id,
            inspector_username=inspector_username,
            device_id=device_id,
            inspection_started_at=inspection_started_at,
            inspection_ended_at=inspection_ended_at,
            aircraft_no=aircraft_no,
            flight_source_id=flight_source_id,
            flight_no=flight_no,
            routine_task_source_id=routine_task_source_id,
            maintenance_task_text=maintenance_task_text,
            station=station,
            location_text=location_text,
            has_issue=has_issue,
            issue_type=issue_type,
            issue_level=issue_level,
            issue_description=issue_description,
            remark=remark,
            status="DRAFT",
        )
        await self._store.upsert_inspection_record(record)
        await self._link_views(record.inspection_id, realtime_view_event_ids)
        await self._append_audit(
            record.inspection_id,
            "CREATED",
            record.inspector_user_id,
            record.inspector_username,
            summary="inspection draft created",
        )
        return await self.get(record.inspection_id)

    async def get(self, inspection_id: str) -> InspectionRecordDetail:
        record = await self._store.get_inspection_record(inspection_id)
        if record is None:
            raise KeyError(f"inspection record {inspection_id} not found")
        return await self._detail(record)

    async def update_draft(
        self,
        *,
        inspection_id: str,
        editor_user_id: str | None,
        editor_username: str,
        aircraft_no: str | None = None,
        flight_source_id: str | None = None,
        flight_no: str | None = None,
        routine_task_source_id: str | None = None,
        maintenance_task_text: str | None = None,
        station: str | None = None,
        location_text: str | None = None,
        has_issue: bool | None = None,
        issue_type: str | None = None,
        issue_level: str | None = None,
        issue_description: str | None = None,
        remark: str | None = None,
        realtime_view_event_ids: Iterable[str] | None = None,
    ) -> InspectionRecordDetail:
        current = await self._require(inspection_id)
        if current.status != "DRAFT":
            raise ValueError(
                f"only DRAFT records can be edited in place (status={current.status})"
            )
        merged = build_inspection_record(
            inspector_user_id=current.inspector_user_id,
            inspector_username=current.inspector_username,
            device_id=current.device_id,
            inspection_started_at=current.inspection_started_at,
            inspection_ended_at=current.inspection_ended_at,
            aircraft_no=(
                current.aircraft_no if aircraft_no is None else aircraft_no
            ),
            flight_source_id=(
                current.flight_source_id
                if flight_source_id is None
                else flight_source_id
            ),
            flight_no=current.flight_no if flight_no is None else flight_no,
            routine_task_source_id=(
                current.routine_task_source_id
                if routine_task_source_id is None
                else routine_task_source_id
            ),
            maintenance_task_text=(
                current.maintenance_task_text
                if maintenance_task_text is None
                else maintenance_task_text
            ),
            station=current.station if station is None else station,
            location_text=(
                current.location_text if location_text is None else location_text
            ),
            has_issue=current.has_issue if has_issue is None else has_issue,
            issue_type=current.issue_type if issue_type is None else issue_type,
            issue_level=current.issue_level if issue_level is None else issue_level,
            issue_description=(
                current.issue_description
                if issue_description is None
                else issue_description
            ),
            remark=current.remark if remark is None else remark,
            status=current.status,
            created_at=current.created_at,
            created_by=current.created_by,
            updated_by=editor_username,
            inspection_id=current.inspection_id,
        )
        await self._store.upsert_inspection_record(merged)
        if realtime_view_event_ids is not None:
            await self._link_views(
                inspection_id,
                realtime_view_event_ids,
            )
        await self._append_audit(
            inspection_id,
            "UPDATED",
            editor_user_id,
            editor_username,
            summary="inspection draft updated",
        )
        return await self.get(inspection_id)

    async def submit(
        self,
        *,
        inspection_id: str,
        submitter_user_id: str | None,
        submitter_username: str,
    ) -> InspectionRecordDetail:
        current = await self._require(inspection_id)
        if current.status != "DRAFT":
            raise ValueError(
                f"only DRAFT records can be submitted (status={current.status})"
            )
        submitted = _with_status(
            current,
            status="SUBMITTED",
            updated_by=submitter_username,
            submitted_at=dt.datetime.now(UTC),
            submitted_by=submitter_username,
        )
        await self._store.upsert_inspection_record(submitted)
        await self._append_audit(
            inspection_id,
            "SUBMITTED",
            submitter_user_id,
            submitter_username,
            summary="inspection record submitted",
        )
        return await self.get(inspection_id)

    async def correct(
        self,
        *,
        inspection_id: str,
        corrector_user_id: str | None,
        corrector_username: str,
        correction_reason: str,
        aircraft_no: str | None = None,
        flight_source_id: str | None = None,
        flight_no: str | None = None,
        routine_task_source_id: str | None = None,
        maintenance_task_text: str | None = None,
        station: str | None = None,
        location_text: str | None = None,
        has_issue: bool | None = None,
        issue_type: str | None = None,
        issue_level: str | None = None,
        issue_description: str | None = None,
        remark: str | None = None,
    ) -> InspectionRecordDetail:
        current = await self._require(inspection_id)
        if current.status not in {"SUBMITTED", "CORRECTED"}:
            raise ValueError(
                f"only SUBMITTED/CORRECTED records can be corrected "
                f"(status={current.status})"
            )
        merged = build_inspection_record(
            inspector_user_id=current.inspector_user_id,
            inspector_username=current.inspector_username,
            device_id=current.device_id,
            inspection_started_at=current.inspection_started_at,
            inspection_ended_at=current.inspection_ended_at,
            aircraft_no=(
                current.aircraft_no if aircraft_no is None else aircraft_no
            ),
            flight_source_id=(
                current.flight_source_id
                if flight_source_id is None
                else flight_source_id
            ),
            flight_no=current.flight_no if flight_no is None else flight_no,
            routine_task_source_id=(
                current.routine_task_source_id
                if routine_task_source_id is None
                else routine_task_source_id
            ),
            maintenance_task_text=(
                current.maintenance_task_text
                if maintenance_task_text is None
                else maintenance_task_text
            ),
            station=current.station if station is None else station,
            location_text=(
                current.location_text if location_text is None else location_text
            ),
            has_issue=current.has_issue if has_issue is None else has_issue,
            issue_type=current.issue_type if issue_type is None else issue_type,
            issue_level=current.issue_level if issue_level is None else issue_level,
            issue_description=(
                current.issue_description
                if issue_description is None
                else issue_description
            ),
            remark=current.remark if remark is None else remark,
            status="CORRECTED",
            created_at=current.created_at,
            created_by=current.created_by,
            updated_by=corrector_username,
            submitted_at=current.submitted_at,
            submitted_by=current.submitted_by,
            corrected_at=dt.datetime.now(UTC),
            corrected_by=corrector_username,
            correction_reason=correction_reason,
            inspection_id=current.inspection_id,
        )
        await self._store.upsert_inspection_record(merged)
        await self._append_audit(
            inspection_id,
            "CORRECTED",
            corrector_user_id,
            corrector_username,
            summary=correction_reason,
        )
        return await self.get(inspection_id)

    async def list(
        self,
        record_filter: InspectionRecordFilter,
    ) -> InspectionRecordPage:
        return await self._store.list_inspection_records(record_filter)

    async def dashboard_metrics(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
    ) -> InspectionDashboardMetrics:
        start_utc = _aware(start).astimezone(UTC)
        end_utc = _aware(end).astimezone(UTC)
        if end_utc <= start_utc:
            raise ValueError("end must be after start")
        page = await self._store.list_inspection_records(
            InspectionRecordFilter(
                start=start_utc,
                end=end_utc,
                page_size=200,
            )
        )
        records = list(page.items)
        # fetch all pages to cover the window (bounded local rehearsal scope)
        while len(records) < page.total:
            page = await self._store.list_inspection_records(
                InspectionRecordFilter(
                    start=start_utc,
                    end=end_utc,
                    page=page.page + 1,
                    page_size=200,
                )
            )
            records.extend(page.items)
        records = [
            record
            for record in records
            if record.status in {"SUBMITTED", "CORRECTED"}
        ]

        total_duration = sum(
            record.inspection_duration_seconds for record in records
        )
        participants = {record.inspector_username for record in records}
        account_rows: dict[str, list[InspectionRecord]] = defaultdict(list)
        device_rows: dict[str, list[InspectionRecord]] = defaultdict(list)
        for record in records:
            account_rows[record.inspector_username].append(record)
            device_rows[record.device_id].append(record)

        aircraft = {record.aircraft_no for record in records if record.aircraft_no}
        flights = {record.flight_no for record in records if record.flight_no}
        tasks = {
            record.routine_task_source_id or record.maintenance_task_text
            for record in records
            if record.routine_task_source_id or record.maintenance_task_text
        }
        issues = [record for record in records if record.has_issue]
        issue_found = len(issues)
        no_issue = len(records) - issue_found
        issue_rate = (
            round(issue_found / len(records), 4) if records else None
        )
        type_counts = Counter(record.issue_type for record in issues if record.issue_type)
        level_counts = Counter(record.issue_level for record in issues if record.issue_level)
        device_rank = Counter(record.device_id for record in issues)
        aircraft_rank = Counter(record.aircraft_no for record in issues if record.aircraft_no)
        station_rank = Counter(record.station for record in issues if record.station)
        trend: Counter[str] = Counter()
        for record in issues:
            day = (record.submitted_at or record.inspection_started_at).astimezone(
                self._business_tz
            ).date().isoformat()
            trend[day] += 1

        requested_days = max(1, round((end_utc - start_utc).days))
        business_days = {
            (record.submitted_at or record.inspection_started_at)
            .astimezone(self._business_tz)
            .date()
            for record in records
        }
        available = len(business_days)
        completeness = (
            "EMPTY"
            if available == 0
            else ("FULL" if available >= requested_days else "PARTIAL")
        )

        return InspectionDashboardMetrics(
            generated_at=dt.datetime.now(UTC),
            scope_start=start_utc,
            scope_end=end_utc,
            coverage=(
                completeness,
                requested_days,
                available,
                (
                    f"{min(business_days).isoformat()}~"
                    f"{max(business_days).isoformat()}"
                    if business_days
                    else ""
                ),
            ),
            total_count=len(records),
            total_duration_seconds=round(total_duration, 3),
            participant_count=len(participants),
            per_account=tuple(
                (
                    username,
                    len(items),
                    round(
                        sum(r.inspection_duration_seconds for r in items),
                        3,
                    ),
                )
                for username, items in sorted(account_rows.items())
            ),
            per_device=tuple(
                (
                    device_id,
                    len(items),
                    round(
                        sum(r.inspection_duration_seconds for r in items),
                        3,
                    ),
                )
                for device_id, items in sorted(device_rows.items())
            ),
            aircraft_count=len(aircraft),
            flight_count=len(flights),
            task_count=len(tasks),
            issue_found_count=issue_found,
            no_issue_count=no_issue,
            issue_rate=issue_rate,
            issue_type_counts=tuple(sorted(type_counts.items())),
            issue_level_counts=tuple(sorted(level_counts.items())),
            issue_device_ranking=tuple(
                sorted(device_rank.items(), key=lambda item: -item[1])
            ),
            issue_aircraft_ranking=tuple(
                sorted(aircraft_rank.items(), key=lambda item: -item[1])
            ),
            issue_station_ranking=tuple(
                sorted(station_rank.items(), key=lambda item: -item[1])
            ),
            issue_trend=tuple(sorted(trend.items())),
        )

    async def _detail(
        self,
        record: InspectionRecord,
    ) -> InspectionRecordDetail:
        view_ids = await self._store.fetch_view_links(record.inspection_id)
        audit = await self._store.list_audit_events(record.inspection_id)
        return InspectionRecordDetail(
            record=record,
            realtime_view_event_ids=view_ids,
            audit_events=audit,
        )

    async def _require(self, inspection_id: str) -> InspectionRecord:
        record = await self._store.get_inspection_record(inspection_id)
        if record is None:
            raise KeyError(f"inspection record {inspection_id} not found")
        return record

    async def _link_views(
        self,
        inspection_id: str,
        realtime_view_event_ids: Iterable[str],
    ) -> None:
        links = link_view_events(inspection_id, realtime_view_event_ids)
        if links:
            await self._store.link_realtime_view_events(links)

    async def _append_audit(
        self,
        inspection_id: str,
        action: str,
        actor_user_id: str | None,
        actor_username: str,
        *,
        summary: str | None,
    ) -> None:
        await self._store.append_audit_event(
            build_audit_event(
                inspection_id=inspection_id,
                action=action,
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                summary=summary,
            )
        )


def _with_status(
    record: InspectionRecord,
    *,
    status: str,
    updated_by: str,
    submitted_at: dt.datetime,
    submitted_by: str,
) -> InspectionRecord:
    return build_inspection_record(
        inspector_user_id=record.inspector_user_id,
        inspector_username=record.inspector_username,
        device_id=record.device_id,
        inspection_started_at=record.inspection_started_at,
        inspection_ended_at=record.inspection_ended_at,
        aircraft_no=record.aircraft_no,
        flight_source_id=record.flight_source_id,
        flight_no=record.flight_no,
        routine_task_source_id=record.routine_task_source_id,
        maintenance_task_text=record.maintenance_task_text,
        station=record.station,
        location_text=record.location_text,
        has_issue=record.has_issue,
        issue_type=record.issue_type,
        issue_level=record.issue_level,
        issue_description=record.issue_description,
        remark=record.remark,
        status=status,
        created_at=record.created_at,
        created_by=record.created_by,
        updated_by=updated_by,
        submitted_at=submitted_at,
        submitted_by=submitted_by,
        corrected_at=record.corrected_at,
        corrected_by=record.corrected_by,
        correction_reason=record.correction_reason,
        inspection_id=record.inspection_id,
    )


def _aware(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scope times must be timezone-aware")
    return value
