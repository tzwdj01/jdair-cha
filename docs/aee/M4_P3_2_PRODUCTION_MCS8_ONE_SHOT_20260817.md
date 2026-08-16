# M4 P3.2 — Production MCS8 ONE SHOT PASS

Date: `2026-08-17`

Status: `PRODUCTION MCS8 ONE SHOT PASS — READY FOR LOW-RATE SCHEDULER CANARY`

## Summary

受支持的服务器端通道（MCS8 native，`docs/aee/M4_P3_2_ACCESS_PATH_DIAGNOSTIC_20260816.md`）
已实现为正式 adapter 并完成真机验证 + 生产 ONE SHOT 写入。AEE 前端
（`aee.jdcloud.com`）服务端仍受 JFE 493 限制，但 MCS8 native 通道不经
JFE，不受影响。

## Adapter（已提交 Git）

* `app/data/mcs8_auth.py` — `MCS8ServerAuthProvider`：WS :7711 登录 → token
* `app/data/mcs8_http.py` — `MCS8DataHTTPClient`：REST :7712，token+SessionId
* `app/data/mcs8_adapter.py` — `MCS8ReadOnlyDataAdapter`
  * DEVICE: `/api/GetDevListByGroupId`（current snapshot, `nOnline`）
  * MEDIA: `/api/v1/RecordFileList`（bounded window）
  * ALARM: `/api/v1/AlarmList`（bounded window）
* `app/data/device_snapshot.py` — `MCS8DeviceSnapshotProcessor`（honest polling）
* `app/data/mcs8_collector.py` — `MCS8InspectionCollector`
* `app/data/normalization.py` — `normalize_mcs8_device_snapshot` +
  media/alarm `source_system` 参数（默认 "aee"，MCS8 用 "mcs8"）
* `app/data/store/*` — `fetch_latest_device_statuses`
* `scripts/m4_mcs8_oneshot.py` — 生产 ONE SHOT

Endpoint 不硬编码，使用 `CHA_V2_MCS8_HOST/WS_PORT/API_PORT/USERNAME/PASSWORD`
环境变量（凭据只从 protected env 注入）。

## Device snapshot semantics

`GetDevListByGroupId.nOnline` 是 CURRENT STATUS SNAPSHOT，不是历史 transition
feed。处理器语义：

* 首次观察 → `INITIAL_OBSERVATION`（quality `initial_snapshot`）
* 后续 poll 状态未变 → **不新增事件**
* 状态变化 → 恰好一条 `CHA_OBSERVED_TRANSITION`
  （`cha_observed_transition` + `observed_by_polling` +
  `partial_transition_visibility`）
* 诚实标记 coverage：polling 无法观察两次 poll 之间短暂 transition，
  不宣称 FULL NATIVE EVENT COVERAGE

## CHA scratch read-only live validation — PASS

在 CHA 生产服务器 scratch（`/opt/cha-m4-canary`，不触碰 running app）：

* MCS8 auth（WS :7711）→ token 160 chars ✅
* DEVICE snapshot：114 设备（14 online / 100 offline）✅
* MEDIA：今日窗口 8 条（0 invalid）✅
* ALARM：今日窗口 2 条（0 invalid）✅
* normalizer：source_system=mcs8，quality flags 正确 ✅

## Browser / AEE front-end vs MCS8 native reconciliation — PASS

相同时间窗口（2026-08-17 00:00 → now）：

| 维度 | AEE 前端（browser 路径） | MCS8 native |
| --- | --- | --- |
| Media recordsTotal | 6 | 6 |
| Media rows | 6 | 6 |
| Media devs | WXB313, WXB351, WXB360 | WXB313, WXB351, WXB360 |
| Alarm recordsTotal | 2 | 2 |
| Alarm devs | WXB360 | WXB360 |
| Device count | — | 114 |

两入口完全一致，无重大差异。（注：AEE 前端仅能从浏览器/本机路径访问，
CHA 服务器直连仍 493，这是已知 JFE source-IP 策略；MCS8 native 通道
在 CHA 服务器直接可用。）

## Production ONE SHOT — PASS

写入 Aliyun PostgreSQL `cha_m4` / `inspection`：

| Source | stored | records_total | invalid | complete |
| --- | --- | --- | --- | --- |
| device_status | 114 | 114 | 0 | true |
| media_files | 8 | 8 | 0 | true |
| alarms | 2 | 2 | 0 | true |

DEVICE 首次采集 = COLLECTION BASELINE（`initial_snapshot`），不是历史上下线
回填。Dashboard coverage 从实际 collection start 开始；30 天请求应返回
PARTIAL 而非 FULL（按真实 available coverage）。

## Idempotency — PASS

重复运行同窗口 ONE SHOT：

* device_status：`stored_count=0`（无状态变化，不新增 transition）
* media_files：`stored_count=8`（upsert 幂等，不膨胀）
* alarms：`stored_count=2`（upsert 幂等）

## PG row counts — PASS

```text
device_status_events = 114   (mcs8: 100 offline + 14 online)
media_files          = 8     (mcs8)
alarm_events         = 2     (mcs8)
```

## Metrics reconciliation — PASS

PG → store → metrics：

* Media：4 设备 / 8 文件（WXB313×3 audio、WXB351×2 video、WXB359×1 video、
  WXB360×2 video），duration/bytes 正确
* Alarm：2 条 / 1 设备 / type_counts ((205,1),(206,1))
* Device：114（14 online / 100 offline）

生产 v2 服务（m3-final-rc 0.8.0）inspection API 未接线（feature off，
`/api/v2/inspection/*` 404 为预期）。API/Dashboard 接线需要新 RC 发布，
属后续 gate，本轮不部署。

## Resource usage

* Mem 1.6/1.9 GiB、Swap 784 MiB/4 GiB、disk 22G/39G（58%）— 无异常
* jdair-cha / jdair-cha-v2 / nginx 均 active，未改动

## Security

* MCS8 password/token/SessionId 未进入 Git/docs/fixtures/logs
* 浏览器永不接触 MCS8 token/password
* 无 WAF bypass、无浏览器 token daemon、无 scheduler
* 生产 app/current/nginx/systemd 未改动

## Not performed

* 未启用 scheduler（等待授权 LOW-RATE CANARY）
* 未导入 AuthorizedUser、未开放 Inspection production workflow、
  未启用 RealtimeViewEvent 生产采集
* 未做 9 路 / PTZ / Talkback / FFmpeg / SFU / transcoding / matcher

## Git

* branch: `codex/m4-inspection-data-center-20260815`
* 新增：`feat: MCS8 native server-side data adapter for M4 P3.2` (d6a6c28)
  + `test: MCS8 adapter + device snapshot semantics + ONE SHOT script`
  (0b26aae) + `fix: MCS8 live validation fixes` (15a72cb)
* 生产 ONE SHOT 结果未写入 Git（含行数摘要，无凭据）
