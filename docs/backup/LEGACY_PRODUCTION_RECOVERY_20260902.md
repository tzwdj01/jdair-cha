# Legacy Production Recovery Snapshot - 2026-09-02

## Status

An application-level recovery snapshot of the active Legacy product was created
from production on 2026-09-01 UTC and verified locally. This document is safe
to commit; the encrypted production archive, its DPAPI key material, production
environment files and all credentials remain outside Git.

## Recovery identity

| Item | Value |
| --- | --- |
| Legacy service | `jdair-cha.service` |
| Active release target | `20260901125005-legacy-v2-nav-6aa499b` |
| Legacy runtime | `/opt/jdair-cha/venv` |
| Legacy reverse-proxy site | `/etc/nginx/sites-available/jdair-cha.conf` |
| Archive format | `CHALEGACY1` AES-GCM (local only) |
| Plain archive SHA-256 | `8fa803f5adb5254b190a06a0684fb21c796bbc69837278363c85f94e1c628db4` |
| Archive entries | `410` |
| Local decrypt-and-list round trip | PASS |

The Git source baseline for this snapshot is the production-oriented Legacy
history on branch `codex/legacy-production-backup-20260902`. The exact
production archive is deliberately **not** a Git object because it contains
production-only material and may include credential-bearing legacy source.

## Included in the encrypted local snapshot

* the complete Legacy release history under `/opt/jdair-cha/releases`;
* the Legacy Python runtime under `/opt/jdair-cha/venv`;
* the active `current` link target;
* `jdair-cha.service` and its effective systemd metadata;
* the Legacy Nginx site configuration and Nginx syntax-test output;
* file-level SHA-256 manifest and a recovery-scope manifest.

## Deliberate exclusions

* V2 application directory and V2 protected environment;
* scheduler protected environment;
* PostgreSQL data, schemas and backups;
* TLS private keys and certificates;
* upstream MCS8/AEE server data, user databases and media storage.

This is therefore a complete **Legacy application rollback** snapshot, not a
whole-VM or upstream-MCS8 disaster-recovery image.

## Fast Legacy rollback on the existing production host

Use this only after an approved Legacy-only change is unsatisfactory. Preserve
V2 and the scheduler; do not alter their `current` links or environment files.

1. On the owner workstation, decrypt the local snapshot with the local
   DPAPI-protected recovery tool. Verify the plain archive SHA-256 above and
   verify it lists 410 entries. Transfer that short-lived plain archive over an
   encrypted administrative channel, then remove the workstation copy after
   transfer.
2. On the target server, extract to a new staging directory. Verify the staged
   `metadata/legacy-current-target.txt` equals the release target above.
3. Copy the staged Legacy releases, Legacy venv, unit file and Nginx site into
   their matching paths. Do not copy any excluded V2, scheduler, database or
   TLS material.
4. Point `/opt/jdair-cha/current` to the target shown above, run `nginx -t`,
   then run `systemctl daemon-reload` and restart **only** `jdair-cha.service`.
5. Reload Nginx only after its syntax test passes. Verify the public Legacy
   root, Legacy login and a normal read-only Legacy API call. Confirm V2 and the
   scheduler stayed active.

Keep the pre-rollback Legacy release directory and the prior `current` link
until post-rollback business acceptance completes; that is the immediate
rollback-of-the-rollback point.

## Re-deploying Legacy on another cloud server

1. Provision a supported Linux host with the same CPU architecture. Match the
   current Python/runtime versions before reusing the archived venv; otherwise
   rebuild the venv from the archived source requirements.
2. Create the non-login service account expected by the unit, restore Legacy
   releases and venv under `/opt/jdair-cha`, restore the service unit and site
   configuration, then point `current` to the recorded target.
3. Supply upstream MCS8/AEE configuration only through a newly created,
   protected server-side environment mechanism. Do not copy any legacy
   credential fallback into Git, terminal history or a new server image.
4. Issue new TLS certificates and configure the new DNS/reverse-proxy endpoint.
   TLS private keys are intentionally not present in the snapshot.
5. Apply the minimum firewall rules required by the actual reverse-proxy and
   upstream MCS8 integration. Never restore historic broad port ranges merely
   because a legacy vendor document lists them.
6. Start `jdair-cha.service`, validate Nginx, then perform a controlled
   browser login and read-only video/device check before redirecting any DNS or
   user traffic.

The new-cloud exercise does not restore upstream MCS8 databases, media files or
PostgreSQL; those require their own independently verified recovery plans.

## GitHub backup boundary

GitHub retains this recovery runbook, the code history and the production
release identity. It must not contain the production archive, `.env` files,
tokens, cookies, passwords, private keys or database dumps. If an off-device
full-archive copy is required later, use an owner-approved encrypted backup
destination or a separately approved encrypted private release asset with an
owner-held recovery key.
