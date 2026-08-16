# M4 P2.5 — Source Identity & Idempotency Audit

Date: `2026-08-16`

Input: the sanitized live 3-day window captured during M4 P2
(`DevOnlineList` 1857 rows, `RecordFileList` 805 rows, `AlarmList` 46 rows;
all `error=200`; no Token/Cookie/path/oss/coordinate/person data used).

## A. MediaFile identity audit (`RecordFileList`, 805 rows)

Upsert natural key in scope: `(source_system, source_record_id, device_id)`.

| Check | Result |
| --- | --- |
| rows | 805 |
| unique `(id, devId)` keys | 805 |
| duplicate key groups | 0 |
| TRUE_DUPLICATE (same id repeated) | 0 |
| IDENTITY_COLLISION (same key, differing content) | 0 |

**P2 correction**: the earlier P2 report said "stored 803 vs accepted 805".
That was **not** an idempotent merge. Two rows carried a missing-capture-time
sentinel `1970-01-01 08:00:00` (business-local, = epoch-zero UTC) in
`startTime`/`fileTime` (rows `WXB310` id `6a80a986…`, `WXB301` id
`6a7de878…`). Their `created_at_source` normalized to `1970-01-01T00:00:00Z`,
falling outside the query window, so the store fetch returned 803.

**Fix applied** (evidence-based, no guessing): `normalize_media_files` now
treats the observed epoch-zero sentinel as a missing time for
`created_at_source` / `end_at_source` / `uploaded_at_source` (set `None`,
flag `epoch_zero_source_time_ignored`), so the row stays queryable by its
valid upload time and PostgreSQL range indexes stay honest. After the fix:
stored 805 = fetched 805, 0 rows outside the window.

**Conclusion**: for this window the natural key
`(source_system, source_record_id, device_id)` is unique and reasonable.
No silent overwrite of legal media records occurred; no `IDENTITY_COLLISION`
to redesign around. Epoch-zero sentinels must be excluded from the PG
unique-identity consideration only as values, not as key components.

## B. DeviceStatusEvent duplicate audit (`DevOnlineList`, 1857 rows)

Storage preserves **all** 1857 rows (store upsert key includes
`source_record_id`); the dedup below exists only in the interval-metric
aggregator.

| Classification | Count |
| --- | --- |
| fetched rows | 1857 |
| unique source ids | 1857 |
| EXACT_SOURCE_DUPLICATE (same source id repeated) | 0 |
| SAME_DEVICE_TIME_STATUS_DUPLICATE (removed by metric dedup) | 303 |
| SOURCE_ID_DUPLICATE within a key group | 0 |
| WINDOW_OVERLAP_DUPLICATE (single window, n/a) | 0 |
| POTENTIAL_FALSE_DEDUP (different source ids, same key) | 303* |
| same-second 0/1 conflict slots | 173 |
| conflict slots surviving dedup | 173 / 173 |

*The 303 metric-deduped rows were compared field-by-field
(`devId`, `groupId`, `devType`, `status`, `time`) against their kept
sibling: **0 differences** — they are content-identical source-level
redundancy (the same physical transition emitted with a different source
`id`), not legitimate distinct transitions. Therefore no
`POTENTIAL_FALSE_DEDUP` that deletes a valid transition.

Same-second `0/1` rows are **never** deduped (the dedup key includes
`status`), so `conflicting_status_same_time` is preserved on 173/173 slots.

**Fix applied**: the metric aggregator now sets an explicit
`same_time_status_multi_source_dedup` quality flag whenever a
`(device, time, status)` group contains more than one distinct source id,
making the redundancy class visible instead of silent.

**Conclusion**: dedup rules are safe; storage keeps every source row; no
blocker to proceeding to a PostgreSQL rehearsal.

## C. Alarm identity

Alarm upsert key `(source_system, source_record_id, device_id, occurred_at,
alarm_type_code)`; 46/46 stored, no duplicates in the window (already
verified in M4 P2).

## D. Status

* Media identity: **confirmed** (unique natural key, epoch-zero sentinel fix).
* Device dedup: **confirmed safe** (content-identical redundancy only;
  same-second 0/1 preserved).
* PostgreSQL rehearsal remains `POSTGRESQL_REHEARSAL_BLOCKED` (see
  `M4_P2_5_POSTGRESQL_REHEARSAL.md`).
