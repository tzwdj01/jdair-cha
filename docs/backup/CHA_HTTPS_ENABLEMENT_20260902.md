# CHA HTTPS Enablement - 2026-09-02

## Scope and outcome

`https://cha.jdair.top/` was enabled with a hostname-valid Let's Encrypt
certificate. The Legacy root remains available over HTTP as a compatibility
fallback; this release deliberately does **not** force HTTP-to-HTTPS redirects.

## Controlled change

* Added an HTTP-01 ACME challenge location to the active Legacy Nginx site and
  its available-site counterpart.
* Issued a certificate for `cha.jdair.top` using the validated webroot path.
* Added a dedicated TLS virtual host that preserves the established routing:
  Legacy root -> Legacy service, V2 API/WebSocket prefixes -> V2 service.
* Verified the certificate hostname/SAN and the automated Certbot renewal timer.

No application code, database schema, service unit, protected runtime
environment, Legacy authentication behavior, V2 authorization behavior, or
root-path routing was changed.

## Validation evidence

| Check | Result |
| --- | --- |
| Public HTTP-01 probe | PASS (HTTP 200) |
| Certificate subject/SAN | PASS (`cha.jdair.top`) |
| Public HTTPS Legacy root | PASS (HTTP 200) |
| Public HTTP Legacy root retained | PASS (HTTP 200) |
| HTTPS V2 protected route | PASS (anonymous HTTP 401, expected) |
| Nginx configuration test and reload | PASS |
| Legacy, V2 and scheduler services | active |
| Certbot renewal timer | enabled and active |

## Rollback

If HTTPS causes a verified production issue, retain the certificate files but
disable only the new TLS virtual host:

1. Remove the `jdair-cha-https.conf` entry from Nginx's enabled-site directory.
2. Restore the two Legacy HTTP-site files from the pre-change rollback directory
   created on the host, or from the encrypted pre-HTTPS recovery snapshot.
3. Run `nginx -t`; reload Nginx only when the syntax test passes.
4. Verify `http://cha.jdair.top/` returns the Legacy application. This rollback
   does not require restarting Legacy, V2, or the scheduler.

The primary pre-change recovery artifact is stored locally outside Git, encrypted
with AES-GCM and a Windows-DPAPI protected recovery key. Its plaintext SHA-256
is `2795c104c7a926a7359dc18fe16aca0bfba930f1c309c1e554f07002d3750127` and it
contains 411 archive entries. Do not commit the archive, key, certificate, or
any protected runtime configuration.

## Follow-up boundary

An HTTP-to-HTTPS redirect may be considered only after owner acceptance of the
HTTPS path and an explicit compatibility review. It is not part of this change.
