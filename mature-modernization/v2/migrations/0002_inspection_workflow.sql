-- M4 P3 Inspection workflow schema (AuthorizedUser / InspectionRecord / audit).
-- Status: DRAFT / REHEARSED LOCALLY 2026-08-16 (NOT applied to production).
-- Forward-only: rollback = backup + restore + previous application release.

BEGIN;

CREATE TABLE IF NOT EXISTS authorized_users (
    id BIGSERIAL PRIMARY KEY,
    aee_account_id TEXT NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT,
    department TEXT,
    role TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_authorized_user_account
    ON authorized_users (aee_account_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_authorized_user_username
    ON authorized_users (username);

CREATE INDEX IF NOT EXISTS ix_authorized_user_enabled
    ON authorized_users (enabled);

CREATE TABLE IF NOT EXISTS inspection_records (
    id BIGSERIAL PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    inspector_user_id TEXT,
    inspector_username TEXT NOT NULL,
    device_id TEXT NOT NULL,
    inspection_started_at TIMESTAMPTZ NOT NULL,
    inspection_ended_at TIMESTAMPTZ NOT NULL,
    inspection_duration_seconds DOUBLE PRECISION NOT NULL,
    aircraft_no TEXT,
    flight_source_id TEXT,
    flight_no TEXT,
    routine_task_source_id TEXT,
    maintenance_task_text TEXT,
    station TEXT,
    location_text TEXT,
    has_issue BOOLEAN NOT NULL DEFAULT FALSE,
    issue_type TEXT,
    issue_level TEXT,
    issue_description TEXT,
    remark TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL,
    created_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    updated_by TEXT NOT NULL,
    submitted_at TIMESTAMPTZ,
    submitted_by TEXT,
    corrected_at TIMESTAMPTZ,
    corrected_by TEXT,
    correction_reason TEXT,
    quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_record_id
    ON inspection_records (inspection_id);

CREATE INDEX IF NOT EXISTS ix_inspection_device_time
    ON inspection_records (device_id, inspection_started_at);

CREATE INDEX IF NOT EXISTS ix_inspection_submitted_at
    ON inspection_records (submitted_at);

CREATE INDEX IF NOT EXISTS ix_inspection_status
    ON inspection_records (status);

CREATE INDEX IF NOT EXISTS ix_inspection_username
    ON inspection_records (inspector_username);

CREATE INDEX IF NOT EXISTS ix_inspection_aircraft
    ON inspection_records (aircraft_no);

CREATE INDEX IF NOT EXISTS ix_inspection_flight
    ON inspection_records (flight_no);

CREATE INDEX IF NOT EXISTS ix_inspection_station
    ON inspection_records (station);

CREATE INDEX IF NOT EXISTS ix_inspection_issue
    ON inspection_records (has_issue, issue_type, issue_level);

CREATE TABLE IF NOT EXISTS inspection_record_views (
    inspection_id TEXT NOT NULL,
    realtime_view_event_id TEXT NOT NULL,
    PRIMARY KEY (inspection_id, realtime_view_event_id)
);

CREATE INDEX IF NOT EXISTS ix_inspection_views_view_id
    ON inspection_record_views (realtime_view_event_id);

CREATE TABLE IF NOT EXISTS inspection_audit_events (
    id BIGSERIAL PRIMARY KEY,
    audit_id TEXT NOT NULL,
    inspection_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_user_id TEXT,
    actor_username TEXT NOT NULL,
    acted_at TIMESTAMPTZ NOT NULL,
    summary TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_audit_id
    ON inspection_audit_events (audit_id);

CREATE INDEX IF NOT EXISTS ix_inspection_audit_inspection
    ON inspection_audit_events (inspection_id, acted_at);

CREATE TABLE IF NOT EXISTS authorized_user_audit_events (
    id BIGSERIAL PRIMARY KEY,
    audit_id TEXT NOT NULL,
    action TEXT NOT NULL,
    operator_user_id TEXT,
    operator_username TEXT NOT NULL,
    target_username TEXT NOT NULL,
    acted_at TIMESTAMPTZ NOT NULL,
    summary TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_audit_id
    ON authorized_user_audit_events (audit_id);

CREATE INDEX IF NOT EXISTS ix_user_audit_target_time
    ON authorized_user_audit_events (target_username, acted_at);

COMMIT;
