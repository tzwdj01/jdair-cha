# M4 Phase 6 — Production Private PostgreSQL Connectivity Recovery

Date: `2026-08-30`
Status: `PASS — SCHEDULER RECOVERED / ACTIVE`

## 1. Scope and Safety Boundary

This recovery addressed only the existing private production path:

```text
CHA production runtime
  → Tailnet
  → PostgreSQL private listener
  → TLS
  → PostgreSQL authentication
  → SELECT 1
```

The Phase 6 Candidate was not rebuilt or deployed. No Dashboard Canary,
AuthorizedUser decision, application business data, schema, Nginx, public
PostgreSQL exposure, AEE/MCS8 behavior, or media architecture was changed.

The low-rate scheduler remained stopped until the private connection gate and
one controlled persistence cycle had passed.

## 2. First Failing Layer

The CHA node had a healthy Tailnet daemon and an online PostgreSQL peer. The
protected CHA runtime configuration already enforced PostgreSQL TLS with GSS
encryption disabled.

The first failing layer was the PostgreSQL listener:

* the PostgreSQL cluster configuration already included its current private
  Tailnet address;
* the active postmaster was listening only on loopback;
* bounded TCP from CHA to private PostgreSQL port `5432` was therefore refused;
* PostgreSQL did not receive a CHA startup/authentication attempt at that
  point.

Capacity, HBA authorization, TLS policy, public firewall exposure and the
completed Phase 6B application pool fix were not the first failure.

## 3. Root Cause

The PostgreSQL cluster service could start before the Tailnet interface was
ready at boot. Its cluster unit lacked an explicit dependency on the existing
`tailscaled` service. PostgreSQL consequently retained only its loopback
listener even though the configured private listener address was correct.

This was a service startup-order defect, not a reason to add a proxy,
connection-pool service, public listener, new VPN, or database infrastructure.

## 4. Minimal Recovery and Rollback

An authorized, minimal systemd drop-in was added to the existing PostgreSQL
cluster unit:

```ini
[Unit]
Wants=tailscaled.service
After=tailscaled.service
```

The preceding unit state was backed up before the change. The recovery command
was guarded to remove the new drop-in (or restore a previous one), reload
systemd and restart the existing PostgreSQL cluster if bounded readiness failed.

The guard was not needed:

* the PostgreSQL cluster restarted successfully;
* both loopback and the existing private Tailnet listener accepted PostgreSQL
  readiness checks;
* PostgreSQL did not listen on a wildcard/public interface;
* the existing least-privilege private HBA rule remained unchanged.

No PostgreSQL database data, role, schema or secret changed.

## 5. Private TLS Validation

Using the protected V2 runtime identity and its actual service home, three
fresh independent PostgreSQL connections completed:

```text
fresh SELECT 1: 3/3 PASS
TLS: active on every validated connection
```

Each observed connection was encrypted and authenticated through the existing
private path. The observed bounded latency was reasonable for the production
cross-node path.

`tailscale ping` continued to return a non-success diagnostic result in this
environment. It was not treated as a production blocker because the actual
protected TCP, PostgreSQL TLS, authentication and `SELECT 1` path passed
repeatedly. No Tailnet configuration was changed merely to alter that
diagnostic outcome.

## 6. Time Synchronization

Both production nodes retained their existing `chrony` service with normal leap
status and low observed offsets. No manual clock change and no NTP
configuration change was necessary.

```text
PG TIME SYNCHRONIZATION: PASS
```

## 7. Controlled Scheduler Recovery

Before starting the managed service, one existing bounded scheduler run was
consumed as evidence; it was not rerun:

```text
cycle index: 1
all_successful: true
sources: DEVICE, MEDIA, ALARM
stderr: empty
```

The cycle used the existing native MCS8 read-only path and production
PostgreSQL persistence. Post-cycle reconciliation found:

* no duplicate DeviceStatusEvent identity groups;
* no duplicate DeviceLocationEvent identity groups;
* no duplicate MediaFile identity groups;
* no duplicate AlarmEvent identity groups;
* expected current-state continuation rather than a new initial-observation
  flood.

The existing systemd scheduler service was then started. Immediate operational
checks found:

```text
service: active / running
restart count after managed start: 0
process RSS: about 40 MiB
immediate PostgreSQL connection errors: none
immediate fatal errors: none
```

Stable V2, Legacy and Nginx services remained active. V2 internal `live` and
`ready` checks both returned HTTP `200`.

## 8. Decision

```text
PRODUCTION PRIVATE PG CONNECTIVITY: PASS

ROOT CAUSE:
PostgreSQL was configured for the current Tailnet address but started
loopback-only because its cluster service lacked Tailnet startup ordering.
The minimal dependency drop-in and one controlled cluster restart applied the
existing private listener configuration.

PG TIME SYNCHRONIZATION: PASS

SCHEDULER: RECOVERED / ACTIVE
```

The next gated activity is the separately controlled Phase 6 AuthorizedUser
Dashboard Canary Retry. This recovery does not deploy the Candidate, perform
the Dashboard Canary, widen user access, or close M4.

## 9. Security Review

This evidence intentionally excludes credentials, tokens, cookies,
authorization headers, database addresses, connection strings and service
environment values. No production secret, backup archive or runtime log was
added to Git.
