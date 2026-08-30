# M4 Phase 6 — Scheduler Lifecycle Observability

**Date:** `2026-08-30`
**Status:** `IMPLEMENTED / LOCAL TEST PASS`
**Scope:** minimal, credential-free systemd scheduler lifecycle evidence.

## Corrected production interpretation

The prior scheduler first-cycle block was a false interpretation of incomplete
journald evidence. The production journal showed a normal sequence:

1. systemd started the scheduler;
2. the first `DEVICE -> MEDIA -> ALARM` cycle completed in approximately
   thirty seconds with PostgreSQL persistence; and
3. the process entered its configured wait interval before an operator stopped
   it.

It was not a stall, crash, restart loop, runtime-identity mismatch or SSH-key
issue. No scheduler semantics, cadence, collection domain or upstream MCS8
contract changes are introduced by this fix.

## Change

Each cycle now emits bounded structured-text lifecycle records through the
existing scheduler logger:

* `scheduler_cycle_started` with `cycle_index`;
* `scheduler_cycle_completed` with duration, DEVICE/MEDIA/ALARM source status
  and fetched/stored counts, location stored/invalid counts, aggregate store
  result and stored-row count; and
* `scheduler_waiting` with cycle index and next-cycle seconds.

An unhandled cycle exception emits `scheduler_cycle_failed` with only cycle
index and exception type before the existing failure path continues.

No password, token, session identifier, authorization header, cookie, database
connection string, public address, raw upstream response or device payload is
included in these records.

The first production application of this change exposed one configuration
detail: the initial lifecycle logger used the `uvicorn` hierarchy, while the
standalone scheduler entrypoint correctly lowers that noisy hierarchy to
`WARNING`. The collection cycle itself completed and persisted state, but its
new `INFO` records were suppressed. The logger now uses the entrypoint's own
`mcs8-scheduler` hierarchy; no collection, database, systemd or MCS8 behavior
changed.

## Automated evidence

`tests.test_mcs8_scheduler` verifies that one controlled cycle emits the start,
completed and waiting records with the expected source/location/store summary,
and that a sentinel secret string cannot appear. The focused suite passed:

```text
11 tests, 0 failures
```

## Production acceptance rule

For the authorized recovery, a scheduler cycle is accepted only when journald
contains both `scheduler_cycle_completed` and `scheduler_waiting`, PostgreSQL
persistence is verified, the service remains active, and its restart count is
stable. A process remaining alive while waiting for the configured cadence is
normal and is not evidence of a stalled cycle.
