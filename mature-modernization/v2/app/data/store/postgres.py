from __future__ import annotations

import asyncio
import datetime as dt
import os
from typing import Any, Iterable

try:  # pragma: no cover - exercised only when a PG store is constructed
    import psycopg2
except ImportError:  # pragma: no cover - psycopg2 is an optional driver
    psycopg2 = None  # type: ignore[assignment]

from ..normalization import (
    AlarmEvent,
    DeviceLocationEvent,
    DeviceStatusEvent,
    MediaFile,
)
from ..realtime_views import RealtimeViewEvent
from .pool import PostgresConnectionPool
from .repository import InspectionStore


UTC = dt.timezone.utc


class PostgresInspectionStore(InspectionStore):
    """PostgreSQL-backed InspectionStore for the migration schema.

    Connection settings are read only from environment variables
    (``CHA_PG_HOST``, ``CHA_PG_PORT``, ``CHA_PG_DATABASE``, ``CHA_PG_USER``,
    ``CHA_PG_SSLMODE``, optional ``CHA_PG_SCHEMA``; the password comes from
    ``CHA_PG_PASSWORD`` or ``PGPASSWORD``). No credential is ever hardcoded,
    logged or returned. It is intended for isolated, non-production
    rehearsal; production wiring requires the full P2.5 rollout gate.

    Upsert semantics match ``MemoryInspectionStore``: latest observation wins
    for status/location/alarm and media-with-source-id; first finalization
    wins for realtime views; media without a source id is appended.
    """

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        sslmode: str | None = None,
        schema: str = "inspection_rehearsal",
        connect_timeout: int = 10,
    ) -> None:
        self._host = host or os.environ.get("CHA_PG_HOST", "127.0.0.1")
        self._port = port or int(
            os.environ.get("CHA_PG_PORT", "5432")
        )
        self._database = database or os.environ.get(
            "CHA_PG_DATABASE",
            "cha_m4_rehearsal",
        )
        self._user = user or os.environ.get("CHA_PG_USER")
        self._password = (
            password
            or os.environ.get("CHA_PG_PASSWORD")
            or os.environ.get("PGPASSWORD")
        )
        self._sslmode = sslmode or os.environ.get("CHA_PG_SSLMODE", "prefer")
        self._schema = schema or os.environ.get("CHA_PG_SCHEMA", "inspection_rehearsal")
        self._connect_timeout = connect_timeout
        if not self._user:
            raise ValueError("CHA_PG_USER is required")
        # Four status/media/alarm connections plus the separate two-connection
        # workflow store remain deliberately bounded for the low-rate Canary.
        self._pool = PostgresConnectionPool(
            min_connections=1,
            max_connections=4,
            connection_kwargs={
                "host": self._host,
                "port": self._port,
                "dbname": self._database,
                "user": self._user,
                "password": self._password,
                "sslmode": self._sslmode,
                "connect_timeout": self._connect_timeout,
            },
        )

    def _connect(self) -> Any:
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is required to use PostgresInspectionStore; "
                "install it in the rehearsal environment"
            )
        return self._pool.connection()

    def close(self) -> None:
        """Close every pooled connection (used on service shutdown)."""

        self._pool.close()

    async def health_check(self) -> bool:
        """Verify the configured PostgreSQL store without exposing details."""

        return await asyncio.to_thread(self._health_check_sync)

    def _health_check_sync(self) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)

    def _schema_sql(self) -> str:
        return f'"{self._schema}"'

    def _qualify(self, table: str) -> str:
        return f"{self._schema_sql()}.{table}"

    async def upsert_device_status_events(
        self,
        events: Iterable[DeviceStatusEvent],
    ) -> int:
        return await asyncio.to_thread(
            self._upsert_device_status_events_sync,
            tuple(events),
        )

    def _upsert_device_status_events_sync(
        self,
        events: tuple[DeviceStatusEvent, ...],
    ) -> int:
        sql = f"""
        INSERT INTO {self._qualify('device_status_events')}
            (source_system, source_record_id, device_id, group_id,
             device_type_code, status_code, online, occurred_at,
             observed_at, ingested_at, quality_flags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_system, device_id, occurred_at, status_code, COALESCE(source_record_id, '')) DO UPDATE
        SET online = EXCLUDED.online,
            group_id = EXCLUDED.group_id,
            device_type_code = EXCLUDED.device_type_code,
            observed_at = EXCLUDED.observed_at,
            ingested_at = EXCLUDED.ingested_at,
            quality_flags = EXCLUDED.quality_flags
        WHERE (EXCLUDED.observed_at, EXCLUDED.ingested_at) >
              (device_status_events.observed_at,
               device_status_events.ingested_at)
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for event in events:
                    cursor.execute(
                        sql,
                        (
                            event.source_system,
                            event.source_record_id,
                            event.device_id,
                            event.group_id,
                            event.device_type_code,
                            event.status_code,
                            event.online,
                            _utc(event.occurred_at),
                            _utc(event.observed_at),
                            _utc(event.ingested_at),
                            list(event.quality_flags),
                        ),
                    )
        return len(events)

    async def fetch_device_status_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[DeviceStatusEvent, ...]:
        return await asyncio.to_thread(
            self._fetch_device_status_events_sync,
            start,
            end,
            _id_set(device_ids),
            source_system,
        )

    def _fetch_device_status_events_sync(
        self,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: set[str] | None,
        source_system: str | None,
    ) -> tuple[DeviceStatusEvent, ...]:
        clauses = ["occurred_at BETWEEN %s AND %s"]
        params: list[Any] = [_utc(start), _utc(end)]
        if device_ids:
            clauses.append("device_id = ANY(%s)")
            params.append(list(device_ids))
        if source_system:
            clauses.append("source_system = %s")
            params.append(source_system)
        where = " AND ".join(clauses)
        sql = f"""
        SELECT source_system, source_record_id, device_id, group_id,
               device_type_code, status_code, online, occurred_at,
               observed_at, ingested_at, quality_flags
        FROM {self._qualify('device_status_events')}
        WHERE {where}
        ORDER BY occurred_at, device_id, observed_at
        """
        rows = self._select(sql, params)
        return tuple(
            DeviceStatusEvent(
                source_system=row[0],
                source_record_id=row[1],
                device_id=row[2],
                group_id=row[3],
                device_type_code=row[4],
                status_code=row[5],
                online=row[6],
                occurred_at=_utc(row[7]),
                observed_at=_utc(row[8]),
                ingested_at=_utc(row[9]),
                quality_flags=tuple(row[10] or ()),
            )
            for row in rows
        )

    async def fetch_latest_device_statuses(
        self,
        *,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> dict[str, DeviceStatusEvent]:
        return await asyncio.to_thread(
            self._fetch_latest_device_statuses_sync,
            _id_set(device_ids),
            source_system,
        )

    def _fetch_latest_device_statuses_sync(
        self,
        device_ids: set[str] | None,
        source_system: str | None,
    ) -> dict[str, DeviceStatusEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if device_ids:
            clauses.append("device_id = ANY(%s)")
            params.append(list(device_ids))
        if source_system:
            clauses.append("source_system = %s")
            params.append(source_system)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
        SELECT DISTINCT ON (device_id)
               source_system, source_record_id, device_id, group_id,
               device_type_code, status_code, online, occurred_at,
               observed_at, ingested_at, quality_flags
        FROM {self._qualify('device_status_events')}
        {where}
        ORDER BY device_id, occurred_at DESC, observed_at DESC, ingested_at DESC
        """
        rows = self._select(sql, params)
        return {
            row[2]: DeviceStatusEvent(
                source_system=row[0],
                source_record_id=row[1],
                device_id=row[2],
                group_id=row[3],
                device_type_code=row[4],
                status_code=row[5],
                online=row[6],
                occurred_at=_utc(row[7]),
                observed_at=_utc(row[8]),
                ingested_at=_utc(row[9]),
                quality_flags=tuple(row[10] or ()),
            )
            for row in rows
        }

    async def upsert_device_location_events(
        self,
        events: Iterable[DeviceLocationEvent],
    ) -> int:
        return await asyncio.to_thread(
            self._upsert_device_location_events_sync,
            tuple(events),
        )

    def _upsert_device_location_events_sync(
        self,
        events: tuple[DeviceLocationEvent, ...],
    ) -> int:
        sql = f"""
        INSERT INTO {self._qualify('device_location_events')}
            (source_system, source_record_id, device_id, location_source,
             latitude, longitude, gps_occurred_at, speed_value,
             direction_value, accuracy_value, battery_value, gps_type_code,
             network_type_code, observed_at, ingested_at, quality_flags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_system, location_source, device_id, gps_occurred_at, latitude, longitude) DO UPDATE
        SET speed_value = EXCLUDED.speed_value,
            direction_value = EXCLUDED.direction_value,
            accuracy_value = EXCLUDED.accuracy_value,
            battery_value = EXCLUDED.battery_value,
            gps_type_code = EXCLUDED.gps_type_code,
            network_type_code = EXCLUDED.network_type_code,
            observed_at = EXCLUDED.observed_at,
            ingested_at = EXCLUDED.ingested_at,
            quality_flags = EXCLUDED.quality_flags
        WHERE (EXCLUDED.observed_at, EXCLUDED.ingested_at) >
              (device_location_events.observed_at,
               device_location_events.ingested_at)
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for event in events:
                    cursor.execute(
                        sql,
                        (
                            event.source_system,
                            event.source_record_id,
                            event.device_id,
                            event.location_source,
                            event.latitude,
                            event.longitude,
                            _utc(event.gps_occurred_at),
                            event.speed_value,
                            event.direction_value,
                            event.accuracy_value,
                            event.battery_value,
                            event.gps_type_code,
                            event.network_type_code,
                            _utc(event.observed_at),
                            _utc(event.ingested_at),
                            list(event.quality_flags),
                        ),
                    )
        return len(events)

    async def fetch_device_location_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[DeviceLocationEvent, ...]:
        return await asyncio.to_thread(
            self._fetch_device_location_events_sync,
            start,
            end,
            _id_set(device_ids),
            source_system,
        )

    def _fetch_device_location_events_sync(
        self,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: set[str] | None,
        source_system: str | None,
    ) -> tuple[DeviceLocationEvent, ...]:
        clauses = ["gps_occurred_at BETWEEN %s AND %s"]
        params: list[Any] = [_utc(start), _utc(end)]
        if device_ids:
            clauses.append("device_id = ANY(%s)")
            params.append(list(device_ids))
        if source_system:
            clauses.append("source_system = %s")
            params.append(source_system)
        sql = f"""
        SELECT source_system, source_record_id, device_id, location_source,
               latitude, longitude, gps_occurred_at, speed_value,
               direction_value, accuracy_value, battery_value, gps_type_code,
               network_type_code, observed_at, ingested_at, quality_flags
        FROM {self._qualify('device_location_events')}
        WHERE {" AND ".join(clauses)}
        ORDER BY gps_occurred_at, device_id, observed_at
        """
        rows = self._select(sql, params)
        return tuple(
            DeviceLocationEvent(
                source_system=row[0],
                source_record_id=row[1],
                device_id=row[2],
                location_source=row[3],
                latitude=row[4],
                longitude=row[5],
                gps_occurred_at=_utc(row[6]),
                speed_value=row[7],
                direction_value=row[8],
                accuracy_value=row[9],
                battery_value=row[10],
                gps_type_code=row[11],
                network_type_code=row[12],
                observed_at=_utc(row[13]),
                ingested_at=_utc(row[14]),
                quality_flags=tuple(row[15] or ()),
            )
            for row in rows
        )

    async def upsert_media_files(
        self,
        files: Iterable[MediaFile],
    ) -> int:
        return await asyncio.to_thread(
            self._upsert_media_files_sync,
            tuple(files),
        )

    def _upsert_media_files_sync(
        self,
        files: tuple[MediaFile, ...],
    ) -> int:
        insert_sql = f"""
        INSERT INTO {self._qualify('media_files')}
            (source_system, source_record_id, device_id, group_id,
             device_name_at_capture, title, file_type_code, media_kind,
             list_type_code, source_code, upload_status_code,
             file_size_bytes, duration_seconds, created_at_source,
             end_at_source, uploaded_at_source, work_no, people_no,
             people_name, description, deleted_marker, observed_at,
             ingested_at, quality_flags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        conflict_sql = insert_sql + (
            " ON CONFLICT (source_system, source_record_id, device_id) "
            "WHERE source_record_id IS NOT NULL DO UPDATE SET "
            "group_id = EXCLUDED.group_id, "
            "device_name_at_capture = EXCLUDED.device_name_at_capture, "
            "title = EXCLUDED.title, "
            "file_type_code = EXCLUDED.file_type_code, "
            "media_kind = EXCLUDED.media_kind, "
            "list_type_code = EXCLUDED.list_type_code, "
            "source_code = EXCLUDED.source_code, "
            "upload_status_code = EXCLUDED.upload_status_code, "
            "file_size_bytes = EXCLUDED.file_size_bytes, "
            "duration_seconds = EXCLUDED.duration_seconds, "
            "created_at_source = EXCLUDED.created_at_source, "
            "end_at_source = EXCLUDED.end_at_source, "
            "uploaded_at_source = EXCLUDED.uploaded_at_source, "
            "deleted_marker = EXCLUDED.deleted_marker, "
            "observed_at = EXCLUDED.observed_at, "
            "ingested_at = EXCLUDED.ingested_at, "
            "quality_flags = EXCLUDED.quality_flags "
            "WHERE (EXCLUDED.observed_at, EXCLUDED.ingested_at) > "
            "(media_files.observed_at, media_files.ingested_at)"
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for item in files:
                    values = (
                        item.source_system,
                        item.source_record_id,
                        item.device_id,
                        item.group_id,
                        item.device_name_at_capture,
                        item.title,
                        item.file_type_code,
                        item.media_kind,
                        item.list_type_code,
                        item.source_code,
                        item.upload_status_code,
                        item.file_size_bytes,
                        item.duration_seconds,
                        _opt_utc(item.created_at_source),
                        _opt_utc(item.end_at_source),
                        _opt_utc(item.uploaded_at_source),
                        item.work_no,
                        item.people_no,
                        item.people_name,
                        item.description,
                        item.deleted_marker,
                        _utc(item.observed_at),
                        _utc(item.ingested_at),
                        list(item.quality_flags),
                    )
                    if item.source_record_id:
                        cursor.execute(conflict_sql, values)
                    else:
                        cursor.execute(insert_sql, values)
        return len(files)

    async def fetch_media_files(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[MediaFile, ...]:
        return await asyncio.to_thread(
            self._fetch_media_files_sync,
            start,
            end,
            _id_set(device_ids),
            source_system,
        )

    def _fetch_media_files_sync(
        self,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: set[str] | None,
        source_system: str | None,
    ) -> tuple[MediaFile, ...]:
        clauses = ["COALESCE(created_at_source, uploaded_at_source) BETWEEN %s AND %s"]
        params: list[Any] = [_utc(start), _utc(end)]
        if device_ids:
            clauses.append("device_id = ANY(%s)")
            params.append(list(device_ids))
        if source_system:
            clauses.append("source_system = %s")
            params.append(source_system)
        sql = f"""
        SELECT source_system, source_record_id, device_id, group_id,
               device_name_at_capture, title, file_type_code, media_kind,
               list_type_code, source_code, upload_status_code,
               file_size_bytes, duration_seconds, created_at_source,
               end_at_source, uploaded_at_source, work_no, people_no,
               people_name, description, deleted_marker, observed_at,
               ingested_at, quality_flags
        FROM {self._qualify('media_files')}
        WHERE {" AND ".join(clauses)}
        ORDER BY COALESCE(created_at_source, uploaded_at_source), device_id,
                 observed_at
        """
        rows = self._select(sql, params)
        return tuple(
            MediaFile(
                source_system=row[0],
                source_record_id=row[1],
                device_id=row[2],
                group_id=row[3],
                device_name_at_capture=row[4],
                title=row[5],
                file_type_code=row[6],
                media_kind=row[7],
                list_type_code=row[8],
                source_code=row[9],
                upload_status_code=row[10],
                file_size_bytes=row[11],
                duration_seconds=row[12],
                created_at_source=_opt_utc(row[13]),
                end_at_source=_opt_utc(row[14]),
                uploaded_at_source=_opt_utc(row[15]),
                work_no=row[16],
                people_no=row[17],
                people_name=row[18],
                description=row[19],
                deleted_marker=row[20],
                observed_at=_utc(row[21]),
                ingested_at=_utc(row[22]),
                quality_flags=tuple(row[23] or ()),
            )
            for row in rows
        )

    async def upsert_realtime_view_events(
        self,
        events: Iterable[RealtimeViewEvent],
    ) -> int:
        return await asyncio.to_thread(
            self._upsert_realtime_view_events_sync,
            tuple(events),
        )

    def _upsert_realtime_view_events_sync(
        self,
        events: tuple[RealtimeViewEvent, ...],
    ) -> int:
        sql = f"""
        INSERT INTO {self._qualify('realtime_view_events')}
            (view_event_id, source_system, username, user_id, device_id,
             session_id, stream_id, opened_at, first_frame_at, closed_at,
             connection_duration_seconds, view_duration_seconds, result,
             error_code, width, height, track_state, close_reason,
             release_mode, quality_flags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s)
        ON CONFLICT (stream_id) DO NOTHING
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for event in events:
                    cursor.execute(
                        sql,
                        (
                            event.view_event_id,
                            event.source_system,
                            event.username,
                            event.user_id,
                            event.device_id,
                            event.session_id,
                            event.stream_id,
                            _utc(event.opened_at),
                            _opt_utc(event.first_frame_at),
                            _utc(event.closed_at),
                            event.connection_duration_seconds,
                            event.view_duration_seconds,
                            event.result,
                            event.error_code,
                            event.width,
                            event.height,
                            event.track_state,
                            event.close_reason,
                            event.release_mode,
                            list(event.quality_flags),
                        ),
                    )
        return len(events)

    async def fetch_realtime_view_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        usernames: Iterable[str] | None = None,
    ) -> tuple[RealtimeViewEvent, ...]:
        return await asyncio.to_thread(
            self._fetch_realtime_view_events_sync,
            start,
            end,
            _id_set(device_ids),
            _id_set(usernames),
        )

    def _fetch_realtime_view_events_sync(
        self,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: set[str] | None,
        usernames: set[str] | None,
    ) -> tuple[RealtimeViewEvent, ...]:
        clauses = ["closed_at BETWEEN %s AND %s"]
        params: list[Any] = [_utc(start), _utc(end)]
        if device_ids:
            clauses.append("device_id = ANY(%s)")
            params.append(list(device_ids))
        if usernames:
            clauses.append("username = ANY(%s)")
            params.append(list(usernames))
        sql = f"""
        SELECT view_event_id, source_system, username, user_id, device_id,
               session_id, stream_id, opened_at, first_frame_at, closed_at,
               connection_duration_seconds, view_duration_seconds, result,
               error_code, width, height, track_state, close_reason,
               release_mode, quality_flags
        FROM {self._qualify('realtime_view_events')}
        WHERE {" AND ".join(clauses)}
        ORDER BY opened_at, device_id, stream_id
        """
        rows = self._select(sql, params)
        return tuple(
            RealtimeViewEvent(
                view_event_id=row[0],
                source_system=row[1],
                username=row[2],
                user_id=row[3],
                device_id=row[4],
                session_id=row[5],
                stream_id=row[6],
                opened_at=_utc(row[7]),
                first_frame_at=_opt_utc(row[8]),
                closed_at=_utc(row[9]),
                connection_duration_seconds=row[10],
                view_duration_seconds=row[11],
                result=row[12],
                error_code=row[13],
                width=row[14],
                height=row[15],
                track_state=row[16],
                close_reason=row[17],
                release_mode=row[18],
                quality_flags=tuple(row[19] or ()),
            )
            for row in rows
        )

    async def upsert_alarm_events(
        self,
        events: Iterable[AlarmEvent],
    ) -> int:
        return await asyncio.to_thread(
            self._upsert_alarm_events_sync,
            tuple(events),
        )

    def _upsert_alarm_events_sync(
        self,
        events: tuple[AlarmEvent, ...],
    ) -> int:
        sql = f"""
        INSERT INTO {self._qualify('alarm_events')}
            (source_system, source_record_id, device_id, group_id,
             alarm_type_code, alarm_status_code, deal_status_code,
             deal_type_code, handled, occurred_at, handled_at, handler,
             deal_description, deleted_marker, observed_at, ingested_at,
             quality_flags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s)
        ON CONFLICT (source_system, source_record_id, device_id, occurred_at, alarm_type_code) DO UPDATE
        SET group_id = EXCLUDED.group_id,
            alarm_status_code = EXCLUDED.alarm_status_code,
            deal_status_code = EXCLUDED.deal_status_code,
            deal_type_code = EXCLUDED.deal_type_code,
            handled = EXCLUDED.handled,
            handled_at = EXCLUDED.handled_at,
            handler = EXCLUDED.handler,
            deal_description = EXCLUDED.deal_description,
            deleted_marker = EXCLUDED.deleted_marker,
            observed_at = EXCLUDED.observed_at,
            ingested_at = EXCLUDED.ingested_at,
            quality_flags = EXCLUDED.quality_flags
        WHERE (EXCLUDED.observed_at, EXCLUDED.ingested_at) >
              (alarm_events.observed_at, alarm_events.ingested_at)
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for event in events:
                    cursor.execute(
                        sql,
                        (
                            event.source_system,
                            event.source_record_id,
                            event.device_id,
                            event.group_id,
                            event.alarm_type_code,
                            event.alarm_status_code,
                            event.deal_status_code,
                            event.deal_type_code,
                            event.handled,
                            _utc(event.occurred_at),
                            _opt_utc(event.handled_at),
                            event.handler,
                            event.deal_description,
                            event.deleted_marker,
                            _utc(event.observed_at),
                            _utc(event.ingested_at),
                            list(event.quality_flags),
                        ),
                    )
        return len(events)

    async def fetch_alarm_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[AlarmEvent, ...]:
        return await asyncio.to_thread(
            self._fetch_alarm_events_sync,
            start,
            end,
            _id_set(device_ids),
            source_system,
        )

    def _fetch_alarm_events_sync(
        self,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: set[str] | None,
        source_system: str | None,
    ) -> tuple[AlarmEvent, ...]:
        clauses = ["occurred_at BETWEEN %s AND %s"]
        params: list[Any] = [_utc(start), _utc(end)]
        if device_ids:
            clauses.append("device_id = ANY(%s)")
            params.append(list(device_ids))
        if source_system:
            clauses.append("source_system = %s")
            params.append(source_system)
        sql = f"""
        SELECT source_system, source_record_id, device_id, group_id,
               alarm_type_code, alarm_status_code, deal_status_code,
               deal_type_code, handled, occurred_at, handled_at, handler,
               deal_description, deleted_marker, observed_at, ingested_at,
               quality_flags
        FROM {self._qualify('alarm_events')}
        WHERE {" AND ".join(clauses)}
        ORDER BY occurred_at, device_id, observed_at
        """
        rows = self._select(sql, params)
        return tuple(
            AlarmEvent(
                source_system=row[0],
                source_record_id=row[1],
                device_id=row[2],
                group_id=row[3],
                alarm_type_code=row[4],
                alarm_status_code=row[5],
                deal_status_code=row[6],
                deal_type_code=row[7],
                handled=row[8],
                occurred_at=_utc(row[9]),
                handled_at=_opt_utc(row[10]),
                handler=row[11],
                deal_description=row[12],
                deleted_marker=row[13],
                observed_at=_utc(row[14]),
                ingested_at=_utc(row[15]),
                quality_flags=tuple(row[16] or ()),
            )
            for row in rows
        )

    def _select(self, sql: str, params: list[Any]) -> list[tuple[Any, ...]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _opt_utc(value: dt.datetime | None) -> dt.datetime | None:
    return _utc(value) if value is not None else None


def _id_set(values: Iterable[str] | None) -> set[str] | None:
    if values is None:
        return None
    return set(values)
