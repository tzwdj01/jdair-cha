# M4 P3.2 — Aliyun PostgreSQL Server Preparation (status)

Date: `2026-08-16`

Status: `BLOCKED — OWNER ACTION REQUIRED — TAILSCALE AUTH`

This round prepares the Aliyun PG server (no migration / scheduler /
Inspection workflow; no production change on CHA). PostgreSQL install is
held at the Tailscale gate per the authorization ("only after Security Group
confirmed, Tailscale ready, swap ready").

## Completed

* **Security Group (empirically confirmed + owner console)**: public TCP
  `5432` is closed (verified from the local China vantage and from the
  Aliyun host's own public IP), SSH `22` reachable from an allowed source;
  owner confirmed the Security Group (SSH restricted, 5432 public closed).
* **Swap**: created 2 GiB `/swapfile` (`mkswap` + `swapon`, `chmod 600`,
  fstab entry for auto-enable); verified `free -h` + `swapon --show`.
* **Tailscale**: installed `1.102.2` on Aliyun. Joining the CHA tailnet
  requires owner authentication (one-time device link).

## Pending (owner action)

* Complete Tailscale device authentication for the Aliyun node (open the
  one-time auth link and sign in to the existing CHA tailnet), then
  `tailscale up` on the Aliyun host.
* After the node is in the tailnet: confirm CHA (100.74.86.85) ↔ Aliyun
  Tailscale IP bidirectional reachability + latency.
* Remote backup destination is **not yet provided** → marked
  `REMOTE BACKUP DESTINATION REQUIRED BEFORE CANARY COMPLETION` (not a
  blocker for PG install/migration prep, but a Canary-completion blocker).

## Not performed (next gates)

PostgreSQL install, PG network hardening, database/roles creation,
migration 0001/0002, ONE SHOT, scheduler, AuthorizedUser, Inspection
workflow, CHA current/nginx/systemd changes — all deferred.
