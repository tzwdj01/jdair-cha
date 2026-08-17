# M4 P3.2 — Production Scheduler Operationalization & Remote Backup

Date: `2026-08-18`

Status:

```text
PRODUCTION SCHEDULER ACTIVE (systemd)
READY FOR INSPECTION USER CANARY
REMOTE BACKUP OWNER ACTION REQUIRED
```

## A. systemd service

* Unit: `/etc/systemd/system/jdair-cha-m4-scheduler.service`
  * `Type=simple`, `User=jdair-demo`, `Group=jdair-demo`
  * `EnvironmentFile=/etc/jdair-cha/m4-scheduler.env` (0600 root)
  * `Restart=on-failure`, `RestartSec=10`, `TimeoutStopSec=30`
  * `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=full`,
    `ProtectHome=true`, `ReadWritePaths=/opt/jdair-cha/m4-scheduler`
* Status: `enabled` + `active`.
* Runtime: `/opt/jdair-cha/m4-scheduler` (own venv with psycopg2, app
  package, scripts; owner jdair-demo).
* No more SSH nohup / temporary setsid / held SSH session.

## B. Scheduler configuration

* `CHA_V2_INSPECTION_SCHEDULER_ENABLED=true` (kill switch)
* `CHA_V2_INSPECTION_SCHEDULER_PERIOD_SECONDS=600`
* `CHA_V2_INSPECTION_SCHEDULER_MAX_CYCLES=0` (run until stopped by systemd)
* `CHA_V2_INSPECTION_SCHEDULER_LOOKBACK_SECONDS=3600`
* `CHA_V2_INSPECTION_SCHEDULER_OVERLAP_SECONDS=300`
* `CHA_V2_INSPECTION_SCHEDULER_STATE_DIR=/opt/jdair-cha/m4-scheduler/state`
* MCS8 native auth (WS :7711 -> token) + Aliyun production PostgreSQL.
* No `aee.jdcloud.com`, no browser token.

## C. First managed cycle — PASS

Service-start cycle 1:

```text
device_status: fetched=114 stored=0 invalid=0 ok
media_files:   fetched=10 stored=10 invalid=0 ok
alarms:        fetched=5  stored=5  invalid=0 ok
```

PG rows after the managed cycle: device 139 / media 43 / alarm 11
(growth only from real new source rows / transitions).

## D. Kill switch — PASS

`CHA_V2_INSPECTION_SCHEDULER_ENABLED=false` -> instance logs
`scheduler_disabled` and exits rc=0 **without collecting**. Historical PG
queries, Legacy, Realtime, and Dashboard remain unaffected.

## E. Restart behavior — PASS

`systemctl restart` -> new process starts, first cycle runs from PG latest
known device state: DEVICE fetched=114 / stored=1 (one real transition),
**no re-generation of 114 INITIAL_OBSERVATION** (`initial_snapshot` count
stayed 114). Media/Alarm idempotent (no duplicate growth).

## F. Logging

* systemd journald for the scheduler; bounded, rotating via journald.
* No MCS8 password / token / SessionId / PG password in logs (redaction
  verified; env file 0600).

## G. Remote backup

* **Local short-term backup (READY)**: `ops/cha_m4_pg_backup.sh` +
  `jdair-cha-m4-pg-backup.timer` (daily, `Persistent=true`):
  custom-format `pg_dump` -> SHA256 -> `pg_restore -l` readability check ->
  14-day retention, stored under `/opt/jdair-cha/backups/pg/`. Manual run
  verified: 46 KB dump, SHA256 recorded, TOC 110 entries readable.
* **Remote / off-host copy: OWNER ACTION REQUIRED.** The project owner has
  not yet provided an object-storage bucket or another controlled server as
  the off-host destination. Same-disk dump is short-term local only;
  `PRODUCTION BACKUP COMPLETE` must not be declared until an off-host copy
  exists. Scheduler operation continues regardless.

## H. PG data growth

```text
device_status_events = 139  (114 initial_snapshot + 25 cha_observed_transition)
media_files          = 43
alarm_events         = 11
```

Growth matches source rows; no per-cycle device row inflation.

## I. Resource usage

* CHA: Mem 673 MiB/1.9 GiB, load 0.18, disk 60%; scheduler RSS ~39 MB stable.
* Aliyun PG: DB size ~9.7 MB, 1 connection.

## J. Security

* Protected env `/etc/jdair-cha/m4-scheduler.env` (0600 root) assembled from
  secret sources; no credentials in Git/docs/logs.
* No WAF bypass, no browser token, no source-IP scanning.

## K. Git / production state

* branch `codex/m4-inspection-data-center-20260815`
* commits to push: scheduler operationalization + backup assets.
* Production: scheduler service active/enabled; PG data preserved; no
  AuthorizedUser / Inspection workflow enabled; app/current/nginx of the
  existing v1/v2 services unchanged (only new scheduler + backup units added).

## Non-goals (not started)

* No AuthorizedUser production rollout, no Inspection User Canary, no final
  Dashboard redesign, no M5.

## Next owner action

1. Provide **remote backup destination** (object storage or controlled
   server) to close `REMOTE BACKUP OWNER ACTION REQUIRED`.
2. Authorize **Inspection User Canary** as a separate gate.
