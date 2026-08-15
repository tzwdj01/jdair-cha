# M4 Inspection History Migrations

Status: `DRAFT / NOT REHEARSED`

These PostgreSQL migrations implement the M4 historical data model described
in `docs/data/HISTORICAL_DATA_MODEL.md`.

Scope:

* `device_status_events`
* `device_location_events`
* `media_files`
* `realtime_view_events`
* `alarm_events`

WebRTC runtime-only state is never persisted.

## Validation status

The current development machine does not provide an isolated PostgreSQL
runtime, `psql`, `pg_dump` or `pg_restore`.

Therefore:

* schema design and migration SQL may be reviewed and unit-tested at the
  contract level;
* no `migration / backup / restore / rollback PASS` claim is made;
* a forward + rollback + backup + restore rehearsal must be executed in an
  isolated PostgreSQL environment before any production use.

## Identity and idempotency notes

* `device_status_events` deduplicates by
  `(source_system, device_id, occurred_at, status_code, source_record_id)`.
* `device_location_events` deduplicates by
  `(source_system, location_source, device_id, gps_occurred_at, latitude,
  longitude)`.
* `media_files` uses a partial unique index when `source_record_id` is present;
  the upstream ID uniqueness scope is still `UNVERIFIED`, so rows without a
  source ID are kept but flagged.
* `realtime_view_events` is final and idempotent per `stream_id`; the first
  finalized event wins.
* `alarm_events` collapses mutable observations to the latest
  `(observed_at, ingested_at)` per identity; this is provisional until the
  alarm lifecycle and retention semantics are verified.

## Secrets

The migration files contain no credentials, connection strings or production
configuration. Runtime connection settings belong to the deployment
environment only.
