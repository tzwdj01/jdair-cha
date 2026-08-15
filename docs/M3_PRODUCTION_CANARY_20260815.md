# M3 Production Canary Evidence — 2026-08-15

## Result

Status:

`CONDITIONAL PASS — FULLSCREEN MANUAL VERIFICATION REQUIRED`

The production 1-stream and 4-stream realtime media gates passed. Session
cleanup, resource counters, Canary isolation, screenshot, Legacy/V2 regression,
and feature-flag safety checks passed. The only remaining acceptance item is a
normal user-operated browser fullscreen check. The attached Chrome automation
environment invoked the production fullscreen path but the browser denied
Fullscreen API activation.

M3 remains:

`IN PROGRESS / PRODUCTION CANARY VALIDATION`

It must not be declared complete until the manual fullscreen check is recorded.

## Scope

This run validated the existing M3 product only. It did not add product
capabilities and did not test PTZ, control, recording, 9-stream layout, account
pool, or production audio.

## Release and rollback baseline

Production release:

`/opt/jdair-cha/v2/releases/0.8.0-m3-final-rc-media-offline-fix-20260815`

Release package SHA-256:

`a0ac5c30ea1852fd06f7149de73a8a54e339d59cc3dfdea62a44cc2142b24f49`

Pre-release backup:

`/opt/jdair-cha/backups/jdair-cha-before-m3-realtime-20260815-184923.tar.gz`

Backup SHA-256:

`239bde1e3104d2744a969808631baaf29cf1c8193fa3944f75108167f101b2cb`

Release rehearsal and extracted-package production-venv tests:

`PASS — 73 tests`

No Nginx or database change was made.

## AEE-native device precheck

The precheck used a legally authorized AEE user with `VIDEOMONITOR`
permission, the normal AEE Monitor drag/drop flow, the same Chrome browser and
network window, and only sanitized observations.

| Device | AEE result | Codec | Resolution | First frame | Close |
| --- | --- | --- | --- | --- | --- |
| WXB309 | `mediaMonitor=opened`, `newConsumer` | H.264 `42e01f` | 1920 × 1080 | PASS | PASS |
| WXB312 | `mediaMonitor=opened`, `newConsumer` | H.264 `42e01f` | 1280 × 720 | PASS | PASS |
| WXB353 | `mediaMonitor=opened`, `newConsumer` | H.264 `42e01f` | 1920 × 1080 | PASS | PASS |
| WXB364 | `mediaMonitor=opened`, `newConsumer` | H.264 `42e01f` | 1920 × 1080 | PASS | PASS |

All AEE test tiles were closed after the precheck. No WXB358 retry was
performed.

## 1-stream Production Canary

Device:

`WXB353`

Observed:

* CHA session creation: PASS.
* AEE server-side login: PASS.
* Gateway connection: PASS.
* Media connection and room join: PASS.
* `openVideo`: accepted.
* First frame: `2026-08-15 19:02:30 CST`.
* Resolution: `1920 × 1080`.
* Track state: `live`.
* Heartbeat: PASS.
* Selective stream close: PASS, about `991.85 ms`.
* Session remained `READY` after stream close.
* Same-session reopen: PASS.
* Reopen first frame: `2026-08-15 19:04:01 CST`.
* Session close: PASS, about `1076.35 ms`.
* Gateway and Media proxy disconnect: PASS.

## 4-stream Production Canary

Devices:

* `WXB309`
* `WXB312`
* `WXB353`
* `WXB364`

First-frame evidence:

| Device | First frame | Resolution | Track |
| --- | --- | --- | --- |
| WXB312 | 19:05:39 | 1280 × 720 | live |
| WXB309 | 19:05:40 | 1920 × 1080 | live |
| WXB364 | 19:05:42 | 1920 × 1080 | live |
| WXB353 | 19:05:44 | 1920 × 1080 | live |

Additional results:

* 2 × 2 four-grid layout: PASS.
* Four streams simultaneously `PLAYING`: PASS.
* Heartbeat: PASS.
* Screenshot on WXB309: PASS.
* Selective close of WXB312: PASS, about `991.855 ms`.
* WXB309/WXB353/WXB364 survivor playback: PASS.
* Reopen WXB312: PASS.
* Reopen first frame: `19:07:40 CST`.
* Session close: PASS, about `2508.81 ms`.
* Gateway and Media proxy disconnect: PASS.

## Fullscreen

Production fullscreen button and error-handling code were invoked.

Observed result in the attached automated Chrome environment:

`浏览器未允许进入全屏`

`document.fullscreenElement` remained empty. The same result occurred after a
DOM click and a browser-coordinate click.

Classification:

`COMPLETED / UNVERIFIED`

This is not evidence of a confirmed product-code defect. The current browser
control environment did not provide the transient user activation required by
the Fullscreen API. A normal user-operated Chrome click is still required.

## Resource and telemetry result

Authenticated diagnostics after both sessions closed:

| Gauge / counter | Result |
| --- | ---: |
| realtime_active_sessions | 0 |
| realtime_active_streams | 0 |
| realtime_gateway_connections | 0 |
| realtime_media_connections | 0 |
| realtime_sessions_playing | 0 |
| realtime_streams_playing | 0 |
| realtime_sessions_degraded | 0 |
| realtime_streams_failed | 0 |
| realtime_release_failure_total | 0 |
| realtime_first_frame_timeout_total | 0 |
| realtime_abnormal_disconnect_total | 0 |
| realtime_screenshot_total | 1 |
| realtime_screenshot_failure_total | 0 |
| realtime_session_create_total | 2 |
| realtime_session_close_total | 2 |
| realtime_stream_open_total | 7 |
| realtime_stream_close_total | 7 |

One bounded closed session remained retained for diagnostics; it was not active.

## Canary isolation

An authenticated user not present in the production Canary allowlist was used.

Results:

* Realtime page: access-limited message shown.
* `GET /api/v2/realtime/diagnostics`: `403 canary_forbidden`.
* `POST /api/v2/realtime/sessions`: `403 canary_forbidden`.
* Control WebSocket: `403`.
* Gateway WebSocket: `403`.
* Media WebSocket: `403`.

No credential, cookie, token, or Authorization value is recorded in this file.

## Regression and safety

After the Canary:

* Legacy HTTP: `200`.
* V2 liveness: `200`.
* V2 readiness: `200`.
* V2 service: active.
* Unexpected service restart count: `0`.
* Realtime was restored to `false`.
* Realtime health reports `enabled=false`, `configured=true`,
  `aee_configured=true`, `canary_configured=true`.
* Audio: `false`.
* Control: `false`.
* AccountPool: `false`.
* Dashboard V2: `true`.

Realtime was not left enabled after the controlled validation.

## Six-stream evidence waiver

Production 6-stream verification:

`NOT EXECUTED — INSUFFICIENT HEALTHY MEDIA DEVICES`

Only four AEE-native media-available video devices were present in the
controlled observation window. This waiver is permitted by the current M3
Production Gate and does not invalidate the four-stream result.

Development-validated stream limit remains 6. Recommended initial production
limit is 4 until a separate six-device production capacity validation passes.

## Remaining acceptance action

1. Enable Realtime only for the existing Canary user.
2. Use one AEE-native media-available device.
3. In a normal user-operated production Chrome tab, click the tile fullscreen
   button.
4. Confirm the tile enters fullscreen and exits normally.
5. Confirm playback/session state remains healthy.
6. Close the session and confirm active session/stream/Gateway/Media gauges
   return to 0.
7. Restore Realtime to disabled.

If this passes, update this report to `PASS` and finalize the M3 Milestone
Completion Report. Do not enter M4 automatically.
