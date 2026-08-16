# M4 P3.2 — MCS8 Native Server-Side Data Adapter

Date: `2026-08-17`

Status: `IMPLEMENTED / UNIT TESTED / PENDING SCRATCH LIVE VALIDATION`

## Purpose

把 M4 的数据获取从 `aee.jdcloud.com` 前端（JFE WAF 对 CHA 服务器 493）
切换到受支持的服务器端通道 **MCS8 native server**。该通道不经过
aee.jdcloud.com JFE 前端，已在 CHA production server 只读验证
（`docs/aee/M4_P3_2_ACCESS_PATH_DIAGNOSTIC_20260816.md`）。

## Architecture

```text
CHA ONE SHOT / collector
  -> MCS8ServerAuthProvider (WS login :7711 -> token/session)
  -> MCS8DataHTTPClient (REST :7712, token header + SessionId)
  -> MCS8ReadOnlyDataAdapter
       - DEVICE:  /api/GetDevListByGroupId   (current status snapshot)
       - MEDIA:   /api/v1/RecordFileList     (bounded window)
       - ALARM:   /api/v1/AlarmList          (bounded window)
  -> normalization (source_system="mcs8")
  -> InspectionStore (PostgreSQL cha_m4 / inspection)
```

## Device snapshot semantics (关键)

MCS8 `GetDevListByGroupId.nOnline` 是 **CURRENT STATUS SNAPSHOT**，不是
`DevOnlineList` 历史 transition feed。因此：

* 首次观察某设备 => `INITIAL_OBSERVATION`
  （quality: `initial_snapshot` + `mcs8_device_snapshot`）。
* 后续 poll 若状态未变 => **不新增事件**（无行增长）。
* 状态变化 => 恰好一条 `CHA_OBSERVED_TRANSITION`
  （quality: `cha_observed_transition` + `observed_by_polling` +
  `partial_transition_visibility`）。
* Polling 无法观察两次 poll 之间发生又恢复的短暂 transition，故 coverage
  诚实标记为 `observed_by_polling` / `partial_transition_visibility`，
  **绝不宣称 FULL NATIVE EVENT COVERAGE**。

实现：`app/data/device_snapshot.py` → `MCS8DeviceSnapshotProcessor`，通过
`InspectionStore.fetch_latest_device_statuses()` 对比 PG 最近已知状态。

## Source isolation

* `source_system="mcs8"`：MCS8 native 通道（snapshot/polling 语义）。
* `source_system="aee"`：保留 AEE `DevOnlineList` / `RecordFileList` /
  `AlarmList` 历史语义与既有 fixtures/tests（不删除、不改变）。

## Endpoint configuration

不硬编码 endpoint。使用环境变量：

* `CHA_V2_MCS8_HOST`
* `CHA_V2_MCS8_WS_PORT` (default 7711)
* `CHA_V2_MCS8_API_PORT` (default 7712)
* `CHA_V2_MCS8_USERNAME`
* `CHA_V2_MCS8_PASSWORD`
* `CHA_V2_MCS8_TIMEOUT_SECONDS`
* `CHA_V2_MCS8_LOGIN_TIMEOUT_SECONDS`

凭据只从 protected environment 注入，不进入 Git/docs/fixtures/logs。

## Files

* `app/data/mcs8_auth.py` — `MCS8ServerAuthProvider`（WS 登录，无硬编码）
* `app/data/mcs8_http.py` — `MCS8DataHTTPClient`（REST，token+SessionId）
* `app/data/mcs8_adapter.py` — `MCS8ReadOnlyDataAdapter`
* `app/data/mcs8_collector.py` — `MCS8InspectionCollector`
* `app/data/device_snapshot.py` — `MCS8DeviceSnapshotProcessor`
* `app/data/normalization.py` — `normalize_mcs8_device_snapshot` +
  media/alarm `source_system` 参数
* `app/data/store/*` — `fetch_latest_device_statuses`
* `scripts/m4_mcs8_oneshot.py` — 生产 ONE SHOT
* `tests/test_mcs8_*.py`, `tests/test_device_snapshot.py`

## Security

* 浏览器永不接触 MCS8 token/password/SessionId。
* token 仅内存持有；日志不记录 password/完整 token。
* ONE SHOT 不启用 scheduler、不激活 AuthorizedUser / Inspection workflow。
* 未做 WAF bypass、无浏览器 token daemon。

## Known limits

* `DevOnlineList` 在 MCS8 native 上无历史 feed；设备在线历史以 snapshot +
  polling-observed transition 积累（coverage 诚实降级）。
* DevOnlineList normalizer 与 fixtures 保留作为已验证 source capability。
