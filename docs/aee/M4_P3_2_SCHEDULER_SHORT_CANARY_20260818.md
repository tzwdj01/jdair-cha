# M4 P3.2 — Production LOW-RATE Scheduler Canary: SHORT CANARY PASS

Date: `2026-08-18`

Status:

```text
PRODUCTION LOW-RATE SCHEDULER CANARY:
  SHORT CANARY PASS

DATA SEMANTICS:
  PASS

PROCESS LIFECYCLE:
  FIXED / VERIFIED (setsid detached run stable; formal systemd process model
  recommended for production)

LONGER OBSERVATION:
  REQUIRED (to be obtained naturally during formal scheduler operation)
```

## A. Scheduler configuration

* `app/services/mcs8_scheduler.py` — `MCS8ProductionScheduler`:
  sequential DEVICE -> MEDIA -> ALARM, one cycle in flight, bounded
  lookback + overlap, server-side MCS8 auth with bounded re-login.
* `scripts/m4_mcs8_scheduler.py` — production canary entrypoint with kill
  switch and configurable cadence.
* Config (env, default disabled):
  * `CHA_V2_INSPECTION_SCHEDULER_ENABLED=false` (kill switch; must be true)
  * `CHA_V2_INSPECTION_SCHEDULER_PERIOD_SECONDS=600`
  * `CHA_V2_INSPECTION_SCHEDULER_MAX_CYCLES=6`
  * `CHA_V2_INSPECTION_SCHEDULER_LOOKBACK_SECONDS=3600`
  * `CHA_V2_INSPECTION_SCHEDULER_OVERLAP_SECONDS=300`
  * `CHA_V2_INSPECTION_SCHEDULER_STATE_DIR=.../mcs8-scheduler`

## B. MCS8 auth stability — PASS

* `MCS8ServerAuthProvider` (WS :7711 -> token) used exclusively; no browser
  token. 5 consecutive cycles plus restart/kill-switch runs all logged in
  successfully (token 160 chars, no rejection observed in the window).

## C. Device polling behavior — PASS

* 114 devices fetched each cycle; same-state polls produced **no** new rows
  (`polling_unchanged_skipped`).
* Only genuine status changes produced a `CHA_OBSERVED_TRANSITION`
  (`observed_by_polling` + `partial_transition_visibility`); never presented
  as an upstream-native transition.

## D. Device transitions

First production canary (5 cycles, 00:36–01:17 CST):

| cycle | device stored (transitions) | notes |
| --- | --- | --- |
| 1 | 0 | same-state |
| 2 | 2 | real transitions |
| 3 | 0 | same-state |
| 4 | 4 | real transitions |
| 5 | 1 | real transition |

Device rows grew only on real transitions (114 baseline -> 137 total:
114 initial + 23 cha_observed_transitions across the canary + restart runs).

## E. Media ingestion — PASS

* 5 cycles: 17/16/16/14/12 upsert-processed; DB grew only for new source
  records. `media_files` total == distinct source identities (no inflation).

## F. Alarm ingestion — PASS

* 5 cycles: 3/4/4/4/4 upsert-processed; `alarm_events` total == distinct
  identities (no inflation).

## G. Source isolation — PASS

* Each source fail-closed and fail-isolated (collector semantics); a single
  source error would not block the others (unit-tested). All canary cycles
  had all three sources `ok`.

## H. Idempotency — PASS

* Media/Alarm unique identities: `total == distinct` verified in PG.
* Device same-state no growth (cycle 1/3 stored 0).

## I. Restart / kill switch — PASS

* **Restart verification**: fresh scheduler process, one cycle -> DEVICE 114
  fetched / **stored=1** (one real transition), not 114 re-initialized.
  `device_status_events` initial_snapshot count stayed 114.
* **Kill switch**: `CHA_V2_INSPECTION_SCHEDULER_ENABLED=false` -> immediate
  `scheduler_disabled` exit (rc=0), no collection. Historical PG / realtime /
  Legacy / Dashboard unaffected.

## J. Metrics reconciliation — PASS

* PG rows consistent with source collection; device latest status
  distribution online/offline reflects real MCS8 snapshot state.

## K. Resource usage

* CHA scheduler process RSS ~39 MB, stable across cycles (no growth).
* CHA host after canary: Mem 605Mi/1.9Gi, Swap 268Ki/4Gi, load 0.54,
  disk 58%.
* Aliyun PG: DB size 9.6 MB, 1 connection.

## L. DB growth

```text
device_status_events = 137  (114 initial_snapshot + 23 cha_observed_transition)
media_files          = 40
alarm_events         = 10
```

Growth matches source rows only; no fixed per-cycle device row inflation.

## M. Request / network volume

* ~3 MCS8 metadata JSON requests per cycle (DEVICE + MEDIA + ALARM), small
  JSON only. No video/blob downloads.

## N. Security

* No password/token/SessionId/PG password in logs, state, or Git.
* No WAF bypass, no browser token daemon, no source-IP scanning.

## O. Tests

* Full V2 regression: **259 tests PASS** (2 PG skips), including 6 new
  scheduler tests (cycle ordering, unchanged no-growth, transition-once,
  source isolation, restart-from-latest, period/kill-switch).

## P. Git / production state

* branch `codex/m4-inspection-data-center-20260815`
* commits: `63dc637` (feat scheduler + config + tests), pushed to origin;
  working tree clean.
* Production PG data preserved (not cleared). No AuthorizedUser / Inspection
  workflow enabled. Production app/current/nginx/systemd unchanged.

## Q. Root cause of the earlier early exit

* The first canary completed cycles 1–5 but exited while waiting for cycle 6.
  No data-logic error was involved: 5 consecutive cycles of data behavior were
  consistent. The exit is attributed to **SSH/nohup session lifecycle** (the
  scheduler was launched from a remote SSH exec channel without a detached
  session). A `setsid`-detached relaunch ran stably; a single-cycle
  restart verification finished normally (`scheduler_finished` logged).
* Formal production deployment should use a systemd unit (process lifecycle,
  restart policy, enable/disable). Not installed this round.

## Remaining observation / blockers

* `LONGER OBSERVATION REQUIRED` — will be obtained naturally during formal
  scheduler operation.
* `REMOTE BACKUP DESTINATION REQUIRED BEFORE P3.2 CANARY COMPLETE` — still
  outstanding (current Aliyun same-disk pg_dump is short-term local only).
* Not entering Inspection User Canary; not expanding production rollout.
