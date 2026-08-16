# M4 P3.2 — Production Capacity Audit (BLOCKED AT CAPACITY GATE)

Date: `2026-08-16`

Status: `PRODUCTION POSTGRESQL CAPACITY DECISION REQUIRED` — P3.2 controlled
production data activation is **not** deployed.

## 1. Scope of audit

Read-only production audit (SSH, no changes) of the CHA host `jdair.top`
before any PostgreSQL / scheduler / Inspection activation, per the M4 P3.2
authorization: if CHA + PostgreSQL + backup + scheduler are to be co-located,
CPU / memory / disk / existing services / backup usage must be checked first,
and deployment must stop if capacity is unsafe.

## 2. Findings

| Dimension | Value | Verdict |
| --- | --- | --- |
| OS | Ubuntu 24.04.2 LTS x86_64 | OK |
| CPU | 2 vCPU; loadavg 0.00/0.05/0.01 | OK (idle) |
| Memory | **1.9 GiB total, 1.7 GiB used, 244 MiB available; swap 4 GiB, 752 MiB in use** | **CRITICAL** |
| Disk | 39 G total, 22 G used, 16 G avail (58%) | OK for now |
| PostgreSQL | not installed | would be new |
| V2 release | `0.8.0-m3-final-rc-media-offline-fix-20260815`, build `m3-final-rc` | current |
| systemd | `jdair-cha-v2.service`, `jdair-cha.service` active | OK |
| nginx | `jdair-cha.conf` present, 80/443 listening | OK |
| Existing services | openclaw node (≈273 MB), mcs8_web_panel (≈110 MB), v2 uvicorn, airamro-proxy node, aon-pc-proxy node, dockerd, containerd, tailscaled, jdog monitor | high memory baseline |
| Backups | `/opt/jdair-cha/backups` ≈303 MB, **on the same system disk** | risk |

## 3. Capacity decision

The host has **2 vCPU / 1.9 GiB RAM with only ≈244 MiB available and swap
already in use**. Co-locating PostgreSQL (even minimally tuned) with the
existing CHA stack, the low-rate ingestion scheduler and periodic backups
would create high memory pressure / OOM / disk-growth risk. Existing backups
also live on the same system disk.

Per the P3.2 authorization, deployment is **not forced** under insufficient
capacity. This activation is **BLOCKED at the capacity gate** pending an
owner decision.

## 4. Owner decision options

1. **Managed PostgreSQL** (preferred): cloud-managed PG >= 14 (no local
   footprint); CHA connects over TLS with `CHA_PG_*` env secrets.
2. **Approved separate PG host/server**: dedicated PostgreSQL server with
   adequate RAM/disk; not the CHA application box.
3. **Upgrade the CHA host**: increase RAM (recommended >= 4 GiB, ideally
   8 GiB) and/or separate the backup disk, then re-run the capacity audit.
4. Any combination of the above with an approved backup location **not on
   the same system disk**.

## 5. Not performed (blocked by capacity gate)

* No production PostgreSQL install;
* no migration 0001/0002 applied;
* no AEE scheduler enabled;
* no AuthorizedUser allowlist activated;
* no Inspection workflow / Dashboard enabled;
* no production backup taken (existing backups untouched);
* no production Secret written.

## 6. Rollback / safety

No production object was changed during this audit. The existing
`current` symlink, systemd services, nginx and backups are untouched.
