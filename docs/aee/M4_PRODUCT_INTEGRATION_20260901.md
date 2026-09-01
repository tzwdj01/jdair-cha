# M4 V2 + Legacy Product Integration — Production Validation

**Status:** `DEPLOYED / USABLE` — ready for Owner Business Acceptance.

## Product decision

M0–M4 V2 functions and the stable Legacy application are intentionally
coexisting production products. This release does not replace or retire
Legacy, and it does not move the site root to V2.

- **Root entry:** `/` remains the Legacy application.
- **V2 primary entry:** `/api/v2/dashboard`.
- **New inspection business entry:** `/api/v2/dashboard/workbench`.
- **Legacy access from V2:** the shared V2 navigation provides
  `经典视频监控` → `/`.

## Integration stages

- **Current:** V2 features are integrated into the same production system as
  Legacy.
- **Now:** this release solves navigation and discoverability; it does not
  change the root entry.
- **After Owner acceptance:** the Owner may decide whether V2 becomes the
  default business entry.
- **Only after explicit Owner approval:** Legacy may later be presented as a
  classic entry or considered for retirement. Neither decision is part of this
  release.

## Released artifact

| Item | Verified value |
| --- | --- |
| Commit | `9b6722237feecaf84c7e8f81a17cfc43732cd024` |
| Package SHA-256 | `3de945ca0f498578bdcde4628724f02ab225e44ddfe7bb4f231496ea3167412d` |
| Production release | `20260901111110-m4-product-navigation-legacy-9b67222` |
| Exact identity | package commit, package hash and runtime markers matched |

## Navigation

All existing V2 Dashboard templates load the same data-free navigation asset.
It exposes:

1. `监察总览` → `/api/v2/dashboard`
2. `视频监察` → `/api/v2/dashboard/workbench`
3. `经典视频监控` → `/`
4. `监察记录` → `/api/v2/dashboard/inspections`
5. `设备运行` → `/api/v2/dashboard/devices`
6. `视频上传` → `/api/v2/dashboard/media`
7. `监察使用` → `/api/v2/dashboard/realtime`
8. `告警异常` → `/api/v2/dashboard/alarms`
9. `航班/任务` → `/api/v2/dashboard/tasks`
10. `设备定位` → `/api/v2/dashboard/map`
11. `数据质量` → `/api/v2/dashboard/data-quality`

The `用户权限` route (`/api/v2/dashboard/users`) remains discoverable only
after the already-existing server-side admin AuthorizedUser check succeeds.
The navigation does not grant privileges and does not expose credentials.

## Production postflight

- V2, Legacy, Nginx and the low-rate scheduler were `active`.
- V2 `/health/live` and `/health/ready` returned HTTP 200.
- The production navigation asset returned HTTP 200 and contained the explicit
  Legacy link.
- The Legacy root returned HTTP 200.
- Source and extracted-package test suites each completed 336 tests with no
  failures; package-only release-tooling skips are intentional.
- The scheduler had completed successive normal low-rate collection cycles
  after its current start and was waiting normally between cycles. Its
  cumulative restart count is historical and no active restart loop was seen.

## AEE boundary and follow-up

AEE Visual remains `STATIC_ONLY / LIVE_VERIFICATION_BLOCKED`. The available
lawful browser context redirected `/v3/visual` to login; no credential was
entered, stored or copied. This does not block the deployed V2/Legacy product
integration.

The only deferred AEE media questions are:

1. one representative uploaded/recorded file's SignedUrl/preview lifecycle;
2. 9/16 multi-tile session, first-frame and release behaviour; and
3. dynamic realtime UX/resource-lifecycle comparison.

Each remains `AEE VERIFICATION REQUIRED` under
`docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`. No FFmpeg, copied media,
transcoding, custom SFU or workaround is introduced.

## Owner acceptance boundary

The next step is Owner Business Acceptance of the deployed V2 navigation and
video-inspection workflow. It may create one deliberate owner-owned test
InspectionRecord, but must not change the root-entry strategy, retire Legacy,
or promote M4 to closed without a separate owner decision.
