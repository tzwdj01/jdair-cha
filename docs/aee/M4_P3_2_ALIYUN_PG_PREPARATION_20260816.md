# M4 P3.2 — Aliyun PostgreSQL Server Preparation (status)

Date: `2026-08-16`

Status: `PRODUCTION POSTGRESQL SERVER READY FOR MIGRATION`

## Update (2026-08-16, post-Tailscale auth)

Owner completed Tailscale authentication; preparation continued:

* Tailscale ready: Aliyun `<PG_TAILSCALE_IP>` (usa-ali) joined the tailnet with
  CHA `<CHA_TAILSCALE_IP>` (cn-edge). `tailscale ping` shows a **direct** path
  (pong via `<CHA_PRODUCTION_EGRESS_IP>:41641`, ~160 ms); TCP over Tailscale 40/40
  handshakes **0% loss** (public-path baseline ~2.5%).
* Swap: 2 GiB active (`swapon --show`), fstab persisted.
* DNS fixed on Aliyun (systemd-resolved eth0 → <DNS_RESOLVER_1>/<DNS_RESOLVER_2>); apt sources
  switched from unreachable `mirrors.cloud.aliyuncs.com` to
  `archive.ubuntu.com` (Aliyun intranet mirror is not reachable from this
  US-region instance).
* PostgreSQL 14.23 installed (Ubuntu official repo); psql/pg_dump/pg_restore
  14.23 verified; `SELECT version()` OK.
* Network hardening: `listen_addresses = localhost,<PG_TAILSCALE_IP>`;
  pg_hba.conf rewritten minimal (postgres peer local; `cha_m4_app,
  cha_m4_migrator` only from `<CHA_TAILSCALE_IP>/32` scram; localhost scram;
  reject `0.0.0.0/0` and `::/0`); public `<PG_CANDIDATE_PUBLIC_IP>:5432` closed (own
  public-IP vantage).
* Production DB/roles created: `cha_m4` DB (owner `cha_m4_migrator`),
  schema `inspection`, roles `cha_m4_app` (DML) + `cha_m4_migrator` (DDL);
  scram connection verified over localhost for both roles. Passwords live
  only in `/etc/cha_pg_secrets_cha_m4` (0600) on the Aliyun host.

## Notes / observation required

* CHA SSH (`jdair.top`) authentication is currently failing for the provided
  credential (Aliyun host with the same password works), so the live
  CHA-originated → Aliyun PG connection has not been exercised this session;
  TCP path over Tailscale is 0% loss. Validate at the next gate (app wiring)
  or once CHA SSH is available.
* A `sing-box` process is running on the Aliyun host (existing service, ~49
  MB RSS) — recorded as an existing service on the PG node; not modified.
* Remote backup destination is not yet provided → marked
  `REMOTE BACKUP DESTINATION REQUIRED BEFORE CANARY COMPLETION`.

## Not performed (next gates)

Migrations 0001/0002, production ONE SHOT, scheduler, AuthorizedUser,
Inspection workflow, CHA current/nginx/systemd changes — all deferred to the
next gate.

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
* After the node is in the tailnet: confirm CHA (<CHA_TAILSCALE_IP>) ↔ Aliyun
  Tailscale IP bidirectional reachability + latency.
* Remote backup destination is **not yet provided** → marked
  `REMOTE BACKUP DESTINATION REQUIRED BEFORE CANARY COMPLETION` (not a
  blocker for PG install/migration prep, but a Canary-completion blocker).

## Not performed (next gates)

PostgreSQL install, PG network hardening, database/roles creation,
migration 0001/0002, ONE SHOT, scheduler, AuthorizedUser, Inspection
workflow, CHA current/nginx/systemd changes — all deferred.
