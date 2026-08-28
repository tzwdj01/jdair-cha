# M4 P3.2 — Aliyun PostgreSQL Server + Network Preflight

Date: `2026-08-16`

Status: `REVIEW REQUIRED` (server is a clean candidate; security group /
Tailscale / swap / CHA-SSH re-confirmation must close before PostgreSQL
install).

## 1. Candidate

`PRODUCTION POSTGRESQL CANDIDATE = ALIYUN SILICON VALLEY SERVER`
(`<PG_CANDIDATE_PUBLIC_IP>`, root). Read-only audit only; **no software installed**.

## 2. Server specification (A)

| Item | Value |
| --- | --- |
| OS | Ubuntu 22.04.5 LTS |
| Kernel / arch | 5.15.0-142-generic / x86_64 |
| CPU | 2 vCPU (Intel Xeon Platinum; 1 core / 2 threads) |
| RAM | 1.6 GiB total, 1.2 GiB available, **no swap** |
| Disk | 40 G total, 35 G available (7% used) |
| Hostname | iZrj9chuclxcavk71viksyZ (Aliyun) |
| Timezone / NTP | Asia/Shanghai; chrony synced (Aliyun NTP) |
| Public / private IP | <PG_CANDIDATE_PUBLIC_IP> / <PG_CANDIDATE_PRIVATE_IP> |

## 3. OS/runtime status (B)

Only Aliyun built-ins running (cloudmonitor/argusagent, aegis AliYunDun,
aliyun-assist, snapd, multipathd, tuned, unattended-upgrades). No
PostgreSQL / MySQL / Docker / nginx / 宝塔 / web server. Listening ports:
only `sshd :22` (+ localhost resolver). Clean dedicated node.

## 4. Disk / memory baseline (C)

* Disk: 35 G free — enough for PG data + WAL + short-term local backup at
  this metadata-only scale (video files stay off this server).
* Memory: 1.6 GiB with no swap — workable for a low-concurrency PG node with
  small `shared_buffers`, but **no swap means OOM risk under a spike**;
  adding a swap file (e.g. 2 G) is recommended before PG install.

## 5. Existing services (D)

None besides Aliyun platform agents (see §3). No port conflicts.

## 6. CHA ↔ Aliyun network (E)

CHA production host `jdair.top` → `<CHA_PRODUCTION_EGRESS_IP>` (China Telecom range;
JCloud guest). Path tested from the Aliyun side (same route as
CHA→Aliyun):

* ICMP (Aliyun → CHA): 100% loss — **ICMP is blocked** by the CHA cloud
  firewall (expected; use TCP for latency).
* TCP RTT (Aliyun → CHA:22, 10 handshakes): min 0.14 s, max 1.17 s
  (single outlier), typical **≈0.15 s (150 ms)**, 0 failures.
* TCP 5432 on CHA: closed (no PG exposed) ✓.
* Local (China client) → Aliyun ICMP: avg 431 ms (0% loss) — cross-Pacific
  baseline from my vantage.

## 7. Packet loss / stability (F, G)

TCP handshake success 10/10 with stable ≈150 ms RTT; no loss observed. One
1.17 s outlier in 10 samples → route is generally stable with occasional
minor jitter. Cross-Pacific link is inherent (~150 ms minimum).

## 8. Classification

`ACCEPTABLE FOR CANARY`: stable ≈150 ms RTT, no packet loss — usable for
low-concurrency CHA Canary; synchronous PG queries will pay ~150 ms per
round trip and Dashboard latency must be measured on real pages.
Not `GOOD` (RTT is high), not `UNSUITABLE` (no loss / stable).

## 9. Tailscale feasibility (H)

* CHA: tailscaled present, Tailscale IP `<CHA_TAILSCALE_IP>` (prior audit).
* Aliyun: **Tailscale not installed** — must be installed for the encrypted
  CHA → Tailscale → Aliyun PG path (an install-time action, after preflight).
* Preferred topology: CHA → Tailscale/WireGuard → Aliyun PG; public 5432
  stays closed.

## 10. Firewall / security assessment (I)

* Aliyun OS firewall: `ufw inactive`, iptables empty (policy ACCEPT) — the
  OS is effectively open and relies on the **Aliyun Security Group**, which is
  not verifiable from the OS.
* Required before PG install: Security Group must (a) restrict SSH to
  necessary sources and (b) keep **5432 closed to the public internet**
  (DB comms only via Tailscale private IP). Never `0.0.0.0/0:5432`.

## 11. PostgreSQL suitability (J)

Suitable as a dedicated low-concurrency PG node **provided**:
swap added (recommended), Security Group 5432-closed enforced, and Tailscale
installed for the private path. Metadata-only load, 35 G free disk.

## 12. Application connection-pattern risk (code review, no refactor)

`PostgresInspectionStore` / `PostgresInspectionRecordStore` open a **new
psycopg2 connection per method call** and use short transactions. Per HTTP
request this is a small number of connections (1–2), but at ≈150 ms RTT each
round trip adds latency; batch upserts loop rows on a single connection per
source (no N+1 across the network). Dashboard/API latency at low concurrency
is expected to be ~150–450 ms per request; a connection pool is a later
optimization, not this phase.

## 13. Recommendation (K)

`REVIEW REQUIRED` — server is a clean, suitable PostgreSQL candidate and the
network is `ACCEPTABLE FOR CANARY`. Close the following before install:

1. Configure Aliyun Security Group: SSH restricted; **5432 closed to public**;
2. Install Tailscale on Aliyun and join the CHA tailnet;
3. Add swap (recommend 2 G) on Aliyun;
4. Re-confirm CHA SSH access (currently auth-throttled this session) and run
   a direct CHA → Aliyun TCP probe + real Dashboard latency sample;
5. Owner confirms backup location off the Aliyun system disk or a separate
   volume if local short-term backup is to be stored there.
