# M4 P3.2 — Production ONE SHOT: BLOCKED — AEE Server-Side Access WAF 493

Date: `2026-08-16`

Status: `BLOCKED — AEE SERVER-SIDE ACCESS BLOCKED (JFE 493)`

## What was attempted

Per the authorized gate, a production ONE SHOT was prepared on the CHA
production host (standalone scratch, no running-app change):

* M4 ingestion modules copied to `/opt/cha-m4-canary` (scratch, not the app);
* scratch venv with `psycopg2` (Tsinghua mirror);
* AEE token extracted once from the authorized AEE session and injected into
  the CHA protected secret file `/etc/cha-aee-secrets` (0600);
* production PG connectivity already verified (previous gate): CHA →
  Aliyun PG over Tailscale, `cha_m4_app` auth OK.

## Blocking evidence

From the CHA production host, a direct request to the AEE data API with the
correct `token` header, browser UA and Referer:

```text
HTTP 493 JFE Forbidden
<html><head><title>493 JFE Forbidden</title></head>
...<center><i>43f552e0b99df0382216e0dd4c858895</i></center>... JFE
```

All three sources (DevOnlineList / RecordFileList / AlarmList) failed with
`AEE_DATA_HTTP_ERROR` (HTTP 493) from the CHA host. The earlier live AEE
verifications succeeded only inside the user's browser, which satisfies JD
Cloud's WAF (JFE) challenge that server-side `curl`/urllib does not.

## Conclusion

The production ONE SHOT cannot run because **JD Cloud WAF (JFE) blocks
server-side requests from the CHA production host to `aee.jdcloud.com`**
(HTTP 493), independent of the AEE token. Per the authorization
("token/auth failure ... immediately stop and report"), this gate is
`BLOCKED`.

No WAF bypass, no browser-token scraping daemon, and no long-running browser
automation was attempted (prohibited).

## Options for the owner (no action taken)

1. JD Cloud WAF / JFE allow-listing of the CHA production server IP and/or a
   supported server-side access path for `aee.jdcloud.com` data APIs.
2. Confirm whether a JD Cloud gateway/whitelist is the supported server-side
   integration channel (instead of direct HTTP from the CHA host).
3. After WAF access is resolved, re-run the prepared production ONE SHOT
   (script + modules + secrets are staged on the CHA host).

## Not performed

No production ingestion, no scheduler, no AuthorizedUser activation, no
Inspection rollout. Production PG (cha_m4) remains at the migrated baseline
with zero rows. No CHA app/current/nginx change.
