-- M4 Inspection History schema
-- Status: DRAFT / NOT REHEARSED.
-- Review migrations/README.md before treating this as validated.

BEGIN;

CREATE TABLE IF NOT EXISTS device_status_events (
    id BIGSERIAL PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_record_id TEXT,
    device_id TEXT NOT NULL,
    group_id TEXT,
    device_type_code INTEGER,
    status_code INTEGER NOT NULL,
    online BOOLEAN,
    occurred_at TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_device_status_identity
    ON device_status_events (
        source_system,
        device_id,
        occurred_at,
        status_code,
        COALESCE(source_record_id, '')
    );

CREATE INDEX IF NOT EXISTS ix_device_status_device_time
    ON device_status_events (device_id, occurred_at);

CREATE INDEX IF NOT EXISTS ix_device_status_occurred_at
    ON device_status_events (occurred_at);

CREATE TABLE IF NOT EXISTS device_location_events (
    id BIGSERIAL PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_record_id TEXT,
    device_id TEXT NOT NULL,
    location_source TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    gps_occurred_at TIMESTAMPTZ NOT NULL,
    speed_value DOUBLE PRECISION,
    direction_value DOUBLE PRECISION,
    accuracy_value DOUBLE PRECISION,
    battery_value DOUBLE PRECISION,
    gps_type_code TEXT,
    network_type_code TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_device_location_identity
    ON device_location_events (
        source_system,
        location_source,
        device_id,
        gps_occurred_at,
        latitude,
        longitude
    );

CREATE INDEX IF NOT EXISTS ix_device_location_device_time
    ON device_location_events (device_id, gps_occurred_at);

CREATE INDEX IF NOT EXISTS ix_device_location_occurred_at
    ON device_location_events (gps_occurred_at);

CREATE TABLE IF NOT EXISTS media_files (
    id BIGSERIAL PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_record_id TEXT,
    device_id TEXT NOT NULL,
    group_id TEXT,
    device_name_at_capture TEXT,
    title TEXT,
    file_type_code INTEGER,
    media_kind TEXT NOT NULL,
    list_type_code INTEGER,
    source_code INTEGER,
    upload_status_code INTEGER,
    file_size_bytes BIGINT,
    duration_seconds INTEGER,
    created_at_source TIMESTAMPTZ,
    end_at_source TIMESTAMPTZ,
    uploaded_at_source TIMESTAMPTZ,
    work_no TEXT,
    people_no TEXT,
    people_name TEXT,
    description TEXT,
    deleted_marker BOOLEAN,
    observed_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_media_source_identity
    ON media_files (source_system, source_record_id, device_id)
    WHERE source_record_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_media_device_created
    ON media_files (device_id, created_at_source);

CREATE INDEX IF NOT EXISTS ix_media_device_end
    ON media_files (device_id, end_at_source);

CREATE INDEX IF NOT EXISTS ix_media_device_uploaded
    ON media_files (device_id, uploaded_at_source);

CREATE INDEX IF NOT EXISTS ix_media_uploaded_at
    ON media_files (uploaded_at_source);

CREATE INDEX IF NOT EXISTS ix_media_created_at
    ON media_files (created_at_source);

CREATE TABLE IF NOT EXISTS realtime_view_events (
    id BIGSERIAL PRIMARY KEY,
    view_event_id TEXT NOT NULL,
    source_system TEXT NOT NULL,
    username TEXT NOT NULL,
    user_id TEXT,
    device_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    stream_id TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    first_frame_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ NOT NULL,
    connection_duration_seconds DOUBLE PRECISION NOT NULL,
    view_duration_seconds DOUBLE PRECISION,
    result TEXT NOT NULL,
    error_code TEXT,
    width INTEGER,
    height INTEGER,
    track_state TEXT,
    close_reason TEXT NOT NULL,
    release_mode TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_realtime_view_stream
    ON realtime_view_events (stream_id);

CREATE INDEX IF NOT EXISTS ix_realtime_view_user_time
    ON realtime_view_events (username, closed_at);

CREATE INDEX IF NOT EXISTS ix_realtime_view_device_time
    ON realtime_view_events (device_id, closed_at);

CREATE INDEX IF NOT EXISTS ix_realtime_view_closed_at
    ON realtime_view_events (closed_at);

CREATE INDEX IF NOT EXISTS ix_realtime_view_result
    ON realtime_view_events (result);

CREATE TABLE IF NOT EXISTS alarm_events (
    id BIGSERIAL PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    group_id TEXT,
    alarm_type_code INTEGER NOT NULL,
    alarm_status_code INTEGER,
    deal_status_code INTEGER,
    deal_type_code INTEGER,
    handled BOOLEAN,
    occurred_at TIMESTAMPTZ NOT NULL,
    handled_at TIMESTAMPTZ,
    handler TEXT,
    deal_description TEXT,
    deleted_marker BOOLEAN,
    observed_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_alarm_identity
    ON alarm_events (
        source_system,
        source_record_id,
        device_id,
        occurred_at,
        alarm_type_code
    );

CREATE INDEX IF NOT EXISTS ix_alarm_device_time
    ON alarm_events (device_id, occurred_at);

CREATE INDEX IF NOT EXISTS ix_alarm_occurred_at
    ON alarm_events (occurred_at);

CREATE INDEX IF NOT EXISTS ix_alarm_type
    ON alarm_events (alarm_type_code);

COMMIT;
