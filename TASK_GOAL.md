# CHA Video Record System Optimization — Active Task Goal

Last updated: 2026-08-15

## 1. Overall Objective

在保持现有生产系统稳定运行、可回滚、可验证的前提下，逐步完成 CHA 视频记录系统优化。

整体演进路线按照项目已确认的 Milestone 推进。

任何实现必须遵循：

* 当前代码事实；
* 当前生产环境事实；
* 已确认 Runbook；
* 已完成 Release Report；
* 项目根目录 `AGENTS.md`；
* `docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`。

不得因为当前任务上下文压缩、线程持续时间较长或模型切换而重新猜测项目状态。

---

# 2. Source of Truth Priority

发生冲突时，按照以下优先级确认事实：

1. 当前生产环境实际状态；
2. 当前 Git repository 代码；
3. 已验证测试结果；
4. 最新 Release / Canary Report；
5. 当前 `TASK_GOAL.md`；
6. 历史设计文档；
7. 聊天历史中的旧计划。

历史计划不得覆盖已经确认的代码和生产事实。

---

# 3. Project Status

所有任务必须标记为以下状态之一：

* `COMPLETED`
* `COMPLETED / VERIFIED`
* `COMPLETED / UNVERIFIED`
* `IN PROGRESS`
* `TODO`
* `BLOCKED`
* `AEE VERIFICATION REQUIRED`

不得把已经完成且验证通过的事项重新实现。

当前事实摘要：

* 当前 Git branch：`codex/m3-release-fix-20260814`。
* 本轮 Production Canary 开始前 Git HEAD：`42d39a5`，当时与
  `origin/codex/m3-release-fix-20260814` 一致且工作树 clean。
* 当前生产 V2 release：
  `/opt/jdair-cha/v2/releases/0.8.0-m3-final-rc-media-offline-fix-20260815`。
* 当前生产 Realtime、Audio、Control、AccountPool feature flag 均为
  `false`。
* 当前生产 AEE 和 Canary 配置存在于受保护的生产环境中，不进入 Git。
* 最新生产回滚备份：
  `/opt/jdair-cha/backups/jdair-cha-before-m3-realtime-20260815-184923.tar.gz`，
  SHA-256：
  `239bde1e3104d2744a969808631baaf29cf1c8193fa3944f75108167f101b2cb`。
* 上一次 Production Canary 因选择了 AEE Media 当前不可用的 `WXB358` 而中止；
  该设备现归类为已知 upstream/device media availability exception，不再作为
  M3 Production Gate 硬性设备。
* `2026-08-14 19:57 CST` 最新生产只读复核确认：
  * liveness、readiness、Legacy dependency 均为 healthy；
  * 生产版本 `0.8.0`、build `m3-final-rc`；
  * `dashboard_v2=true`；
  * Realtime、Audio、Control、AccountPool 均为 `false`；
  * AEE Secret 和 Canary allowlist 均显示 configured；
  * health 未主动探测或登录 AEE。
* 当前 HEAD 加本轮工作树修改的全量 V2 自动化回归：`73 tests PASS`。
* `2026-08-15 18:32 CST` 生产只读复核确认：
  * current 仍为 `0.8.0-m3-final-rc-release-fix`；
  * service active，active since `2026-08-14 17:53:06 CST`；
  * liveness、readiness、Legacy dependency 均 healthy；
  * Realtime、Audio、Control、AccountPool 均为 `false`；
  * AEE Secret 7/7 configured，Canary allowlist configured；
  * 生产 env 权限 `0600 root:root`；
  * Legacy local HTTP 为 200。
* `2026-08-15 18:49–18:53 CST`：
  * 已完成新的完整增量备份、release dry-run 和 isolated release rehearsal；
  * production venv 解包测试 `73 tests PASS`；
  * 已部署带 `DEVICE_MEDIA_OFFLINE` 和补偿性 close 修复的新 release；
  * 切换后 service active、`NRestarts=0`、Legacy/V2 health PASS。
* `2026-08-15 18:53–19:21 CST`：
  * 仅对既有 Canary allowlist 临时启用 Realtime；
  * 使用 4 台 AEE-native media available 设备完成生产 1 路和 4 路验证；
  * Canary 完成后已恢复 `realtime_readonly=false`；
  * Audio、Control、AccountPool 全程保持关闭；
  * 生产 `current` 未回退，Nginx 和数据库未修改。
* `2026-08-15 23:24 CST` M3 关账前生产只读复核确认：
  * 当前 production release 仍为
    `0.8.0-m3-final-rc-media-offline-fix-20260815`；
  * V2 service active，`NRestarts=0`；
  * liveness、readiness 和 Legacy dependency 均 healthy；
  * Realtime、Audio、Control、AccountPool 均为 `false`；
  * AEE Secret 和 Canary allowlist 均为 configured，health 未主动登录 AEE；
  * production `current`、Nginx、数据库和 AEE Secret 均未修改。
* 项目负责人已批准 M3 Closure Policy：
  `M3 CLOSED / ACCEPTED WITH EVIDENCE WAIVER`。
* Fullscreen 保持 `COMPLETED / UNVERIFIED`，作为
  `POST-M3 OPERATIONAL FOLLOW-UP`；不得标记为 PASS，也不再阻塞 M3 或 M4。
* `2026-08-15` 已启动新的长期 Goal：
  `M4 — Inspection Data Center & AEE Data Capability Integration`。
* 当前 M4 Git branch：
  `codex/m4-inspection-data-center-20260815`。
* M4 的核心从媒体并发扩展转为监察数据调查、标准化、历史沉淀、关联分析、
  多页面 Dashboard 和业务下钻。
* M4 初始治理、AEE 能力目录、字段目录、CHA 当前能力清单、数据可用性矩阵、
  历史模型和 Dashboard 信息架构已提交到
  `a56baee docs: activate M4 inspection data center`。
* 当前 M4 分支已增加纯 Python、无网络/数据库副作用的确定性聚合基础：
  AEE-style 设备状态 transition 的区间截断在线时长，以及
  `RecordFileList` 原始单位文件统计。
* 当前 AEE 静态代码已确认 `/api/v1/auth/Token` 的 `access_token` 被数据请求
  helper 作为自定义 `token` HTTP header 使用；未读取或记录实际 Token。
* 已增加只读 `AEEDataHTTPClient` 基础：精确 GET allowlist、注入式服务端
  token provider、401 invalidate 后单次重试和 CHA-owned bounded errors。
  它尚未连接登录、API、scheduler、数据库或生产配置。
* 已增加 `AEEReadOnlyDataAdapter` endpoint contracts：DevTree、
  DevOnlineList、RecordFileList 的显式 timezone/range/pagination 校验和
  page-envelope completeness metadata。
* 已增加 deterministic multi-page collection：不静默吞掉 max page/record
  截断、unknown/changing total、empty page、duplicate source ID 或 invalid row。
* 已增加 normalized `DeviceStatusEvent` 和 `MediaFile` contracts：
  source/observation/ingestion 时间分离、原始 code 保留、非 1 status 不猜测为
  offline、敏感人员/备注字段默认省略。
* 已增加 conservative `DeviceLocationEvent` application contract：
  基于已审计的 Legacy `/api/GetGpsModelList` per-device query shape，验证坐标和
  device scope，分离 GPS/observation/ingestion 时间，缺失测量值保持 null，并
  显式标记 restricted location、坐标系/单位/code map 未验证。当前未连接
  LegacyClient、scheduler、PostgreSQL、API 或生产配置。
* 已增加 normalized `RealtimeViewEvent` finalization contract 和可选 sink 边界：
  首帧只记录一次，close/disconnect/timeout/shutdown 明确分类，按 `stream_id`
  幂等，且不包含 Cookie hash、AEE 凭据或媒体协商数据。
* 已增加 `/api/v1/AlarmList` endpoint contract 和 conservative
  `AlarmEvent` normalization：raw code 保留、handled 不猜测、handler/time/free
  text 默认省略。
* 已增加 deterministic Realtime/Alarm event aggregation：
  user/device viewing totals、duration/latency、result/error distribution，
  以及 raw alarm device/type/status/deal-status counts；duplicate、conflict 和
  incomplete scope 不会被静默吞掉。
* 已增加 threshold-free DeviceLocation event aggregation：
  per-device event/coordinate count、source span、latest age 和 optional-field
  coverage；aggregate 不返回坐标、不自行判定 stale/fresh，并显式处理
  duplicate、update、conflict、invalid 和 incomplete scope。
* 已增加 driver-agnostic durable store seam：
  * `InspectionStore` repository 抽象基于 normalized contracts；
  * 确定性内存实现仅供测试/本地开发；
  * PostgreSQL migration 草稿覆盖 5 张历史表；
  * idempotent upsert 语义（status/location/alarm latest-wins、
    media source-ID upsert、realtime view first-wins）。
  * 当前不声明 migration/backup/restore/rollback PASS。
* 已增加 `StoreViewEventSink`：把 realtime session manager 的 finalization
  接入 `InspectionStore`，形成 CHA 自有监察使用历史写入路径；
  open → first frame → close 会话持久化一条 `RealtimeViewEvent`，
  同一 `stream_id` 重试幂等；该 sink 为 opt-in，生产行为不变。
* 已增加只读 `InspectionDataService`（`app/services/inspection.py`）：
  基于 store + 确定性 metrics 输出设备/媒体/监察使用/告警/位置概览；
  全部指标来自持久化真实行，不猜字段；长时间离线/长时间未上传/位置过期
  等需要受治理阈值的分类明确不产出，只暴露 raw coverage/age 值。
* 已增加只读 inspection API（`app/api/inspection.py`）：
  `/api/v2/inspection/{devices,media,realtime,alarms,locations}`；
  明确可用性状态（feature off → 404、无 store → 503、有 store → 真实计算值），
  JSON-safe 序列化和显式 scope；feature flag 默认关闭，生产行为不变。
* 已增加第一批专题页：
  `GET /api/v2/dashboard/{devices,media,realtime}` 渲染三标签页面
  （`app/templates/inspection.html`），只消费已接线的 inspection API；
  store 未接入/为空时页面诚实显示“数据源未接入/待验证”，不伪造指标。
* 已增加设备时间线下钻：
  `GET /api/v2/inspection/devices/{device_id}/timeline` 返回单设备的
  status/media/location 时间线；坐标 restricted 且不输出；设备页内联渲染，
  形成 总览 → 设备 → 时间线 下钻路径。
* realtime 概览增加运行态快照：接入 realtime manager 时返回当前 active
  sessions/streams、Gateway/Media 连接；无 manager 时 `runtime=null`，
  运行态与 store 历史严格分开。
* 已完成 Legacy media-to-flight/task reference helper 的代码取证：
  当前 active batch path 只加载 routine tasks，普通 flight matcher 为未接线
  reference code；现有 city/time/score/certainty 只能作为 unverified candidate，
  不得用于 confirmed relation 或 coverage rate。
* 当前全量 V2 自动化回归为 `177 tests PASS`。
* 当前开发机没有 Docker、PostgreSQL client/server、`pg_dump` 或
  `pg_restore`。因此不能在此环境宣称 PostgreSQL migration、backup 或 restore
  rehearsal 已完成。

---

# 4. Milestones

## M0 — Baseline and Security Governance

状态：`COMPLETED / VERIFIED`

已确认事实：

* 完成生产基线调查、完整备份、校验和和回滚入口。
* 建立独立 V2 release/current 结构、健康检查和 feature flag。
* 生产备份和回滚记录见：
  `docs/MATURE_MODERNIZATION_M0_BACKUP_20260813.md`、
  `docs/MATURE_MODERNIZATION_M0_RELEASE_20260813.md`。
* 当前新增项目治理文件、AEE Reference 原则和活动目标管理。

---

## M1 — Engineering Foundation

状态：`COMPLETED / VERIFIED`

已确认事实：

* 建立 FastAPI V2 模块化服务和只读 Legacy Adapter。
* 保持原 `/api/*` 契约和旧系统入口不变。
* 完成独立健康检查、版本和功能开关接口。
* 完成增量备份及真实回退演练。
* 证据见：
  `docs/MATURE_MODERNIZATION_M1_BACKUP_20260813.md`、
  `docs/MATURE_MODERNIZATION_M1_RELEASE_20260813.md`。

---

## M2 — Situation Dashboard

状态：`COMPLETED / VERIFIED`

已确认事实：

* 态势总览页面和只读聚合接口已经实现并发布。
* 已完成真实会话、数据、浏览器视觉检查和降级验证。
* 已完成 M2 → M1 → M2 回滚演练。
* 当前生产普通业务继续运行，未被 M3 Canary 中止影响。
* 证据见：
  `docs/MATURE_MODERNIZATION_M2_BACKUP_20260813.md`、
  `docs/MATURE_MODERNIZATION_M2_RELEASE_20260813.md`。

---

## M3 — Realtime Video First Release

目标能力：

* 多账号池；
* 1 / 4 / 6 / 9 路；
* 声音；
* 截图；
* 全屏；
* 重连；
* 播放状态监控；
* 账号健康管理；
* 会话健康管理。

整体状态：`CLOSED / ACCEPTED WITH EVIDENCE WAIVER`

已完成并验证：

* `COMPLETED / VERIFIED`：M3.1 单路 CHA realtime session 正式闭环。
* `COMPLETED / VERIFIED`：Model A：
  `1 CHA session → 1 AEE login → 1 Gateway → 1 Media → N consumers`。
* `COMPLETED / VERIFIED`：1 / 4 / 6 路产品代码、布局和会话编排。
* `COMPLETED / VERIFIED`：历史真实 AEE 六路 H.264 视频验证。
* `COMPLETED / VERIFIED`：单路关闭、survivor、重新打开和完整会话关闭。
* `COMPLETED / VERIFIED`：截图、全屏、一次有界重连和播放状态监控。
* `COMPLETED / VERIFIED`：Session/Stream/Gateway/Media 运行指标和资源释放检查。
* `COMPLETED / VERIFIED`：receive-only 音频技术验证；生产开关仍为关闭。
* `COMPLETED / VERIFIED`：Canary 用户默认拒绝、HTTP/API/WebSocket 隔离的自动化测试。
* `COMPLETED / VERIFIED`：发布脚本 production venv、test fail-fast 和单次回滚路径。
* `COMPLETED / VERIFIED`：isolated final-release rehearsal。
* `COMPLETED / VERIFIED`：release-fix 生产部署、备份和关闭状态健康检查。
* `COMPLETED / VERIFIED`：AEE Media `devices is offline` 已归一化为 CHA
  `DEVICE_MEDIA_OFFLINE`；`openVideo` rejection 会执行补偿性 `closeVideo`，
  JavaScript runtime test 和全量 V2 回归通过。

当前生产验收状态：

* `COMPLETED / VERIFIED`：当前生产 release 的 1 路 Canary：
  `WXB353` 首帧、1920 × 1080、Track live、heartbeat、单路关闭、同会话 reopen
  和 session close 均通过。
* `COMPLETED / VERIFIED`：当前生产 release 的 4 路 Canary：
  `WXB309`、`WXB312`、`WXB353`、`WXB364` 四路均获得首帧并进入
  `PLAYING`；selective close、survivor、reopen、screenshot 和 session close
  均通过。
* `COMPLETED / VERIFIED`：生产环境 authenticated non-Canary 页面、两个
  Realtime API 和三个 WebSocket endpoint 均被拒绝。
* `COMPLETED / VERIFIED`：Canary 结束后
  active session/stream/Gateway/Media 均回到 0，
  `realtime_release_failure_total=0`。
* `COMPLETED / UNVERIFIED`：生产全屏按钮已触发正确 Fullscreen API 路径，但当前
  受控 Chrome 自动化/Computer Use 环境无法可靠提供并确认 Fullscreen API 所需的
  transient real-user activation。没有发现新的 CHA Fullscreen 产品代码缺陷。
  真实普通用户 Chrome 的
  `enter fullscreen → exit fullscreen → playback continues`
  证据已获非阻塞 waiver，并移动到 `POST-M3 OPERATIONAL FOLLOW-UP`。
* `NOT EXECUTED — INSUFFICIENT HEALTHY MEDIA DEVICES`：生产 6 路验证；
  当前观察窗口仅有 4 台 AEE-native media available 视频设备，按已批准 evidence
  waiver 不阻塞 4 路首发容量结论。

未实现或未进入当前已批准 release 范围：

* `TODO`：9 路产品能力和真实容量验证。
* `TODO`：多账号池和完整账号健康管理。
* `TODO`：将 receive-only Audio 对生产 Canary 开放。

以上事项在 M3 关账时均被明确排除，不影响 M3 closure。不得因本文件更新而自动开始。
重新进入这些能力必须有后续真实业务需求和明确任务授权。

Realtime 产品范围冻结：

* 保留现有 1 / 4 / 6 路、截图、状态监控、重连、资源释放和 Canary 隔离能力。
* 近期 Realtime Video 产品最大范围为 16 路；必须由 M4 的真实业务需求和独立容量
  验证驱动。
* 32 路及更高并发：`DEFERRED`。
* 近期不为并发引入复杂 AccountPool，不开发 H.265 workaround，不引入 FFmpeg、
  自建 SFU、自建 transcoding 或其它无真实业务需求的媒体架构升级。
* Realtime Video 后续作为监察数据平台的基础下钻能力，不再作为主要研发方向。

当前设备例外：

* `KNOWN UPSTREAM/DEVICE MEDIA AVAILABILITY EXCEPTION`：`WXB358` 虽在
  DevTree 中为 online，但 AEE 原生 `mediaMonitor` 稳定返回
  `devices is offline`，且不产生 `newConsumer`。
* `WXB358` 不再作为 M3 Production Canary 硬性验收设备，也不再构成项目级
  blocker。
* 其 H.265、lowercase `openvideo`、WASM/Canvas 和 `/mediaStream` 调查证据
  保留但暂停。只有未来 AEE `mediaMonitor=opened` 且产生 `newConsumer` 后，
  才作为独立 compatibility issue 恢复调查。

主要证据：

* `docs/M3_1_REALTIME_SESSION.md`
* `docs/M3_2A_AEE_MULTISTREAM_MODEL.md`
* `docs/M3_2B_FOUR_GRID_REALTIME.md`
* `docs/M3_REALTIME_ARCHITECTURE.md`
* `docs/M3_FINAL_VALIDATION_REPORT.md`
* `docs/M3_REALTIME_RUNBOOK.md`
* `docs/M3_REALTIME_PRE_RELEASE_CHECKLIST.md`
* `m3-production-canary-result.json`（本地忽略结果，不作为 Git 运行时依赖）

---

## M4 — Inspection Data Center & AEE Data Capability Integration

状态：`IN PROGRESS`

名称：

`CHA 监察数据中心与 AEE 数据能力整合`

Primary Product Goal：

系统调查、获取、标准化、沉淀和关联 AEE、MCS8、CHA Legacy、航班、例行任务和
Realtime 所能提供的监察数据，形成 CHA 自己的长期监察数据资产，并基于真实可获得
的数据建设多页面监察数据中心。

核心业务问题：

* 设备运行怎么样；
* 用户如何使用系统；
* 视频和文件上传怎么样；
* 哪里存在异常；
* 航班和任务的视频覆盖怎么样；
* 哪些对象需要监察人员优先关注。

战略原则：

1. 数据能力优先于媒体并发能力。
2. 16 路 Realtime 满足近期最大产品范围，但不代表已完成容量验证或批准立即开发。
3. 32 路及更高并发：`DEFERRED`。
4. Dashboard 可以由多个专题页面组成，不要求所有数据堆在一张大屏。
5. AEE 是上游能力参考实现，不是 UI 克隆目标或生产运行时依赖。
6. CHA 的最终价值是形成独有、可追溯、可验证的监察数据资产。
7. Realtime Video 仅作为监察数据平台的业务下钻入口，不再作为 M4 主要研发方向。

M4 工作流：

1. 审计当前 CHA 数据能力：
   `DashboardService`、`LegacyClient`、`trend_store`、Realtime telemetry、
   Realtime session manager、设备、video stats、records、flights 和 routine tasks。
2. 使用合法权限调查 AEE 数据能力，建立 capability/interface/field catalogs。
3. 对每个期望字段标记：
   `AVAILABLE`、`DERIVABLE`、`RESTRICTED`、`NOT_AVAILABLE` 或 `UNKNOWN`。
4. 只对具有明确来源和业务价值的数据设计历史模型：
   `DeviceStatusEvent`、`DeviceLocationEvent`、`MediaFile`、
   `RealtimeViewEvent`、`AlarmEvent`。
5. PostgreSQL 只用于设备状态历史、监察使用历史、必要的视频元数据索引、告警历史
   和统计指标；WebRTC runtime 临时状态不得写入 PostgreSQL。
6. 第一版 Dashboard 页面：
   * 先建设 `/dashboard/devices` 设备运行分析；
   * `/dashboard/media` 视频与文件分析；
   * `/dashboard/realtime` 监察使用分析；
   * 三个专题页数据真实、稳定后再建设 `/dashboard` 监察总览。
7. Drill-down：
   总览 → 城市/部门 → 设备 → 时间线 → 实时视频/历史视频/位置/航班任务/异常。

### M4 优先级模型（2026-08-16 更新）

`P0`：

1. 完成并维护 `DeviceStatusEvent` 标准 contract。
2. 完成并维护 `MediaFile` 标准 contract。
3. 在合法、安全条件允许时真实验证 AEE：
   * `/api/v1/DevOnlineList`；
   * `/api/v1/RecordFileList`；
   覆盖字段、时间语义、分页、retention 和 stable identity。只记录脱敏结论。
4. 在合法、安全条件允许时验证 AEE 数据接口认证边界：
   * 是否仅依赖自定义 `token` header；
   * 是否还依赖 Cookie；
   * Token 失效与刷新行为；
   不得输出或保存真实 Token/Cookie。

`P1`：

* `RealtimeViewEvent`：优先建立 CHA 自己的监察使用历史，不依赖 AEE 提供该历史。
* `AlarmEvent`：继续只读取证 alarm_id/device_id/code/type/level/occurred_at/
  status/handled/handled_at/handler；无法验证的 code map 标记 `UNKNOWN`，不猜测。

`P2`：

* Legacy Media → Flight/Routine Task 自动业务匹配。
* 在没有 stable identity、时区证据、correction lifecycle 和人工确认正负样本
  以前：禁止实现自动 matcher，禁止生成 flight/task video coverage KPI。
* 现有代码审计与 candidate-only gate 保持不变，不再作为当前主线。

`PostgreSQL`：

* 缺少 PostgreSQL runtime 不阻塞 contract 开发。
* 允许继续：schema design、migration files、repository abstraction、unit tests。
* 没有真实隔离 PostgreSQL 前：不得声明 migration / backup / restore / rollback
  PASS。

`Dashboard 第一批页面`：

* 当 `DeviceStatusEvent`、`MediaFile`、`RealtimeViewEvent` 数据模型稳定后，开始
  真正的数据页面。
* 优先：`/dashboard/devices`、`/dashboard/media`、`/dashboard/realtime`。
* 此时不要急于完成最终总览页；专题页数据真实、稳定后，再建设 `/dashboard`。

`当前最重要指标`：

* 设备：当前在线/离线、今日上线/掉线、最近上线、最近离线、今日在线时长、
  7日/30日在线率、掉线次数、长时间离线。
* 视频：今日上传数量、视频总时长、文件容量、最近上传时间、每设备上传量、
  7日/30日趋势、长时间未上传设备。
* 监察使用：当前 realtime sessions、今日观看次数、每用户观看次数、
  每用户观看时长、每设备被查看次数、每设备被查看时长、首帧成功率、失败原因。

`执行原则`：

* M4 衡量标准不是调查了多少接口、不是实现了多少自动匹配逻辑，而是是否形成
  真实、可持续积累的设备运行历史、视频上传历史、监察使用历史、异常历史，以及
  能否基于这些数据生成可靠 Dashboard。

M4 允许：

* 调查和只读接口取证；
* Backend Adapter；
* 有来源的数据模型和数据库 migration；
* 统计服务和 Dashboard API；
* 多页面 Dashboard 和测试。

M4 禁止：

* 32 路或更高并发；
* 为并发引入复杂 AccountPool；
* PTZ、Talkback、设备控制；
* H.265 workaround；
* FFmpeg、SFU、Transcoding；
* 无真实数据支持的假 Dashboard；
* 大规模重写现有系统。

生产数据库约束：

* 任何 production DB migration 前必须完成 migration rehearsal、backup 和 rollback。
* 未经明确授权不得修改 production database。

---

## M5 — Device Control

状态：`TODO`

目标能力：

* 对讲；
* 录像；
* 抓拍；
* 云台；
* 权限；
* 二次确认；
* 审计。

不得自动开始，除非：

`ACTIVE MILESTONE = M5`

---

## M6 — Legacy Page Replacement

状态：`TODO`

目标能力：

* 视频记录迁移；
* 指挥调度迁移；
* 辅助查询迁移；
* 压测；
* 恢复演练；
* 最终下线旧内嵌前端。

不得自动开始，除非：

`ACTIVE MILESTONE = M6`

---

# 5. Active Milestone

当前只允许存在一个：

`ACTIVE MILESTONE: M4`

当前状态：
`IN PROGRESS`

Milestone Name：

`Inspection Data Center & AEE Data Capability Integration`

当前只执行 M4 数据能力审计、AEE 合法取证、字段可用性矩阵、历史数据模型、
PostgreSQL rehearsal、统计服务、多页面 Dashboard 和 Drill-down。

M3 已关账。Fullscreen 保持 `COMPLETED / UNVERIFIED` 并属于
`POST-M3 OPERATIONAL FOLLOW-UP`，不得重新成为 M4 主线。

不得顺手扩展 9 路、16 路、32 路、AccountPool、Audio 生产开放、PTZ、对讲、录像
或媒体基础设施。16 路只是近期 Realtime 产品上限，不是当前实施任务。

当当前 Milestone 达到 Done Criteria 后：

1. 不自动进入下一 Milestone；
2. 更新本文件；
3. 给出 Milestone Completion Report；
4. 给出下一 Milestone 建议；
5. 等待 `TASK_GOAL.md` 将下一 Milestone 标记为 ACTIVE。

---

# 6. AEE Reference Rule

凡涉及：

* MCS8；
* AEE；
* realtime video；
* WebRTC；
* WebSocket；
* media session；
* RTP；
* codec；
* stream profile；
* capability；
* SDK；
* device compatibility；

必须遵循：

`docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`

如果 AEE 与 CHA 在同设备同场景表现不同：

必须先产生：

`AEE vs CHA Evidence`

然后才能决定修复方案。

候选 Canary 设备必须先执行最小 AEE native playback precheck，并记录：

* Device；
* Scenario；
* `mediaMonitor` 是否 `opened`；
* 是否产生 `newConsumer`；
* codec；
* track/Canvas；
* first frame；
* close/release。

若 AEE 原生 `mediaMonitor` 失败，应标记为 `MEDIA_UNAVAILABLE` 并跳过；不得计为
CHA failure，也不得围绕该设备开发 workaround。

---

# 7. Architecture Constraint

在没有形成 Architecture Escalation Evidence 之前：

不得新增：

* FFmpeg；
* media server；
* SFU；
* custom decoder；
* transcoding pipeline；
* 大型媒体基础设施；
* 复杂 workaround。

优先级：

Existing MCS8/AEE capability

→ SDK / Protocol Adapter

→ CHA Backend Adapter

→ CHA Business Aggregation

→ only then consider architecture escalation.

当前 `WXB358` 问题没有 Architecture Escalation Evidence，因此 FFmpeg、SFU、
自建 media server、custom decoder 和 protocol workaround 均为 rejected。

---

# 8. Production Safety

所有生产相关修改必须满足：

* 可回滚；
* 有 baseline；
* 有健康检查；
* 有明确 feature flag；
* 有最小 blast radius；
* Canary 优先；
* 发布前后检查服务状态；
* 发布前后检查错误日志；
* 检查 restart count；
* 检查 nginx；
* 检查 API health；
* 验证旧系统不受影响。

禁止未经验证直接扩大生产流量。

当前生产安全约束：

* Canary 已结束并恢复 `CHA_V2_FEATURE_REALTIME_READONLY=false`。
* 保持 Audio、Control 和 AccountPool 为 `false`。
* 使用现有 Canary allowlist，空 allowlist 不得代表全部用户。
* AEE 长期凭据仅允许存在于生产环境变量或 Secret 管理中。
* 下一次生产测试必须复用已验证备份/回滚流程并使用最小用户和设备范围。
* 出现重复首帧超时、资源泄漏、Gateway/Media 增长、owner 隔离失败、旧系统异常、
  5xx 或服务重启时立即停止并关闭 Realtime。

---

# 9. Verification

任何功能不能仅因为：

“代码已写完”

而标记为 `COMPLETED / VERIFIED`。

验证应根据功能至少覆盖：

* lint；
* typecheck；
* unit test；
* integration test；
* backend health；
* frontend build；
* browser behavior；
* network behavior；
* WebSocket lifecycle；
* media lifecycle；
* resource cleanup；
* regression；
* production/canary evidence。

与媒体相关的验收应尽可能记录实际测量数据。

M3 Closure：

* `COMPLETED / VERIFIED`：生产 1 路和 4 路、首帧、track live、分辨率、heartbeat、
  screenshot、selective close、survivor、reopen、session/Gateway/Media cleanup、
  Canary isolation 和 Legacy/V2 回归。
* `COMPLETED / UNVERIFIED`：Fullscreen 普通用户
  `enter → exit → playback continues` 证据。
* `EVIDENCE WAIVER`：Fullscreen 的唯一缺口由自动化环境不能可靠提供和验证瞬时
  real-user activation 导致；没有确认的 CHA 产品缺陷。该项移至
  `POST-M3 OPERATIONAL FOLLOW-UP`。

M4 Verification Requirements：

* 每个 Dashboard 指标必须记录字段来源、刷新频率、数据新鲜度、历史范围、可信度、
  持久化位置和异常处理。
* AEE 字段和接口必须来自合法观察证据；无法确认的字段标记 `UNKNOWN` 或
  `AEE VERIFICATION REQUIRED`。
* 不得为 Dashboard 猜测字段或伪造统计。
* `AVAILABLE`、`DERIVABLE`、`RESTRICTED`、`NOT_AVAILABLE`、`UNKNOWN`
  必须逐字段使用，不能用模糊描述代替。
* 历史趋势必须来自事件、快照或明确可重建的数据源；当前状态不得直接冒充历史。
* production DB migration 必须在独立环境完成 rehearsal、backup、rollback 和
  migration tests，且需另行获得生产修改授权。
* Dashboard 必须至少覆盖总览、设备运行、视频数据和实时监察运营，并提供业务
  Drill-down。

已完成：

* 4 台候选设备的 AEE-native playback precheck；
* 生产 1 路、4 路首帧、live track、分辨率、heartbeat；
* selective close、survivor、reopen、screenshot 和 session close；
* authenticated non-Canary 页面/API/三个 WebSocket 拒绝；
* Session/Stream/Gateway/Media active counters 归零；
* Legacy/V2 health、restart count 和 feature flags 复核。

---

# 10. Git Rules

开始阶段工作前：

* 检查 branch；
* 检查 `git status`；
* 检查未提交修改。

禁止覆盖用户已有修改。

Commit 应按逻辑阶段组织。

禁止：

* 无必要 force push；
* 为方便而混合无关修改；
* 把 secrets / cookies / tokens 提交到 repository。

每个 Milestone 完成时给出：

* recommended commit；
* recommended push；
* recommended tag；
* 是否适合 merge。

除非任务明确授权，否则不要擅自执行破坏性 Git 操作。

当前 Git 约束：

* 治理文件提交与未来媒体修复提交保持分离。
* 当前治理、AEE 证据和 `DEVICE_MEDIA_OFFLINE` 修复均已提交并推送远端。
* `WXB358` compatibility 调查暂停；未来恢复时应建立独立、最小范围的
  compatibility issue/提交。
* 未通过验证前不更新生产 `current`，不创建 release tag，不自动 merge。

---

# 11. Evidence / Decision Log

## M4 Issue

监察数据中心必须基于可验证的 AEE、MCS8、CHA Legacy、AMRO 和 CHA Realtime
数据源，不能为了 Dashboard 指标而猜测字段、把当前状态冒充历史，或让 CHA 前端
直接依赖 AEE 页面私有实现。

状态：`IN PROGRESS / INITIAL DATA EVIDENCE CAPTURED`

## M4 CHA Evidence

* 已完成当前 `DashboardService`、`LegacyClient`、`trend_store`、
  Realtime telemetry/session manager、设备、记录、航班和例行任务代码审计。
* 当前 V2 Dashboard 仍依赖 Legacy 的设备、视频统计、记录、航班和例行任务接口。
* 当前设备趋势仅为按需采样的聚合 JSON 快照，不是逐设备上线/离线事件历史。
* 当前 Realtime telemetry 为进程内运行态；尚无持久化
  `RealtimeViewEvent`。
* 当前 V2 尚未启用 PostgreSQL 监察数据资产；任何 production migration 仍受
  rehearsal、backup、rollback 和明确授权约束。
* 已建立初始数据能力、字段可用性、历史模型和 Dashboard 信息架构文档。
* 已实现第一批无副作用的确定性聚合函数：
  * 设备 status transition 按设备排序、去重、使用窗口前状态播种，并把未闭合在线
    区间截断到查询 `window_end`；
  * 文件统计保留 `duration` 秒和 `fileLen` 字节原始单位，并显式暴露
    pagination/query-limit 导致的 partial 状态；
  * 非 1 status map、缺失初始状态、冲突事件、非法行和未知文件类型均通过
    quality flag 暴露，不静默转换为可信数据。
* 上述聚合目前只有应用层 contracts、纯函数和单元测试；尚未连接 AEE HTTP
  Adapter、PostgreSQL repository、API 或 Dashboard。
* 已增加窄 AEE read-only HTTP transport；它不拥有账号密码、不读取浏览器存储，
  也不向前端暴露 Token。完整 data Adapter 的 login/token lifecycle 仍未完成。
* 已增加 endpoint-specific Class A adapter contracts；当前仅覆盖 live-verified 的
  DevTree、DevOnlineList 和 RecordFileList，不提前接入 TaskList、write path 或
  未稳定的 Alarm lifecycle。
* 已增加分页完整性 collector；source ID duplicate 只记录、不删除，直到其唯一性
  范围完成 AEE 验证。
* 已增加历史模型 normalization layer；当前尚未持久化，也没有 API、scheduler
  或生产 wiring。
* 已增加 CHA-native `RealtimeViewEvent` finalization contract：
  * 使用已有 authenticated username，不持久化 owner/session Cookie hash；
  * 以 stream create、首次首帧和 close/disconnect/timeout/shutdown 时间生成
    connection/view duration；
  * played、timeout、failed、cancelled、abnormal disconnect 结果可复现；
  * sink 失败不阻断媒体释放，并可通过重复 close 幂等重试；
  * 当前 sink 默认未配置，尚无 PostgreSQL repository、outbox 或历史 API。
* 已增加 AlarmList / AlarmEvent 应用层基础：
  * Adapter 只发送 live-evidenced query fields；
  * `timeType` 和 `groupWithChild` 必须由调用方显式提供，不猜测 selector default；
  * `id/devId/alarmType/alarmTime` 为事件最小必需字段；
  * alarm/status/deal codes 原样保留并标注 map partial；
  * handled/level 不推断，restricted handling fields 默认省略；
  * 当前尚未持久化，也没有 ingestion scheduler 或 Dashboard API。
* 已增加 normalized final-event 的确定性统计：
  * Realtime duration 由事件 timestamp 重算，不信任预计算值；
  * exact duplicate stream 去重，conflicting/invalid stream 排除并标记 partial；
  * Alarm mutable rows 按 latest observation 折叠；
  * 同时刻冲突 Alarm 排除，missing raw status 保持 unknown 而不是 0；
  * 当前函数只聚合调用方提供的明确 scope，不自行猜测“今日”或 retention 范围。
* 已审计当前 production baseline 对应的 Legacy phase5 GPS 路径：
  * `/api/gps-track` 调用 MCS8 `/api/GetGpsModelList`；
  * query scope 为单设备、起止时间、page 1、pagesize 5000；
  * source aliases 为 `lat/latitude`、`lng/longitude`、
    `gpsTime/dateTime/time`、`direct/direction` 和 `netWorkType`；
  * Legacy 会过滤越界及近零坐标，但会把缺失 speed/direction/accuracy 转为 0；
  * M4 历史 contract 保留坐标过滤，不复制缺失值归零行为。
* 已增加 `DeviceLocationEvent` 纯 normalization layer；位置数据统一标记
  restricted，不保留 free-text address，不猜测 coordinate system、单位、
  GPS/network code map、stale threshold、retention 或 sampling。
* 已增加 DeviceLocation deterministic aggregation：
  * 只接受 normalized events 和显式 reporting window；
  * 只返回 event count、distinct-coordinate count、source span、latest age 和
    optional-field presence counts，不返回坐标；
  * exact duplicate 删除，同位置更新折叠到 latest observation；
  * 同 source/device/time 的坐标冲突排除并标记 partial；
  * 不定义 stale threshold、sampling coverage ratio 或 coordinate system。
* 已完成 Legacy records “reference information” heuristic audit：
  * media time aliases 和 filename fallback 已记录；
  * media coordinate → plus/minus 2-hour nearest GPS → city alias 证据链已记录；
  * active batch endpoint 只查询前/当/后一天 routine-task rows；
  * `flights_near_day` 和 ordinary flight matching 在当前 release 无 active call
    path；
  * six-hour windows、fixed score 和 certainty thresholds 无业务验证；
  * 当前结论为 candidate-only，不自动确认，不生成 coverage metric。
  * 证据：
    `docs/data/LEGACY_MEDIA_BUSINESS_REFERENCE_AUDIT.md`。

## M4 AEE Evidence

状态：`LIVE+STATIC PARTIAL / LAWFUL READ-ONLY`

* 授权 AEE 会话已确认 `/api/v1/ext/DevTree` 为设备/分组树接口。
* 当前设备树可提供设备/分组标识、online/status、当前 alarm、GPS 时间/位置、
  network/storage 等投影字段；字段 code map 和刷新语义仍为部分证据。
* 授权 Statistics/Online 页面已确认 `/api/v1/DevOnlineList`、完整查询过滤和
  非空分页设备在线时长结果。当前 AEE 页面使用 `devId/status/time` transition
  rows 在浏览器端计算时长。
* 当前 AEE 算法会把未关闭的 online interval 延伸到浏览器当前时间；CHA 不复制
  该边界行为，必须保存 raw transition、显式排序/去重并按查询 end 截断。
* 授权 Server Files 页面已确认 `/api/v1/RecordFileList`、查询过滤和分页，
  并获得非空结果。字段覆盖设备、标题、媒体类型、大小、时长、文件时间、上传时间、
  来源/上传状态及工作/人员参考字段。
* 授权 File Num、Video Duration、File Size 统计页均已获得非空结果；三者不是
  独立 aggregate API，而是在浏览器按设备聚合最多 10,000 条
  `RecordFileList` rows。
* 当前 AEE 文件统计按 `fType` 统计图片/音频/视频数量，video `duration/60`
  显示分钟，`fileLen/1048576` 显示 MB。CHA 必须从 raw rows 进行可复现聚合并
  显示 truncation/partial-data 状态。
* 已确认上传文件活动与 Realtime Media 可用性必须分开建模；前者不能证明当前
  `mediaMonitor` 可以打开。
* 授权 Alarm 页面已确认 `/api/v1/AlarmList`、查询参数、可见列和非空分页结果；
  脱敏可见行包含低电量告警、百分比描述和 Waiting 处理状态。完整 raw code map、
  lifecycle、删除语义和 retention 仍需验证。
* 当前静态产品代码确认 `AlarmUpload` 推送、`/api/v1/AlarmUpdateDeal`、
  `/api/v1/DevOnlineList`、`/api/v1/TaskList` 和
  `/api/v1/JobLineByRecordId`。
* `/api/v1/DevOnlineList` 已证明可提供 transition-like 数据和在线时长来源；
  但完整非 1 status map、ordering、duplicate、retention 和边界语义仍需验证，
  因此当前不得直接照搬 AEE 浏览器算法。
* 上述证据均未记录 Cookie、Authorization、密码、可复用 Token、私有媒体 URL
  或未脱敏业务行。
* 当前 AEE bundle 静态确认：
  * `/api/v1/auth/Token` 返回的 `access_token` 被保存到 session-scoped browser
    state；
  * AEE 数据请求 helper 把该值放入自定义 HTTP `token` header；
  * 当前未发现 `Authorization: Bearer` 数据接口约定或显式 refresh contract。
* live 页面请求与上述 helper 一致，但浏览器 same-origin session state 是否也是
  服务端数据请求的必要条件、Token 生命周期和 401 后刷新方式仍需验证。

## M4 Classification

* DevTree、RecordFileList、AlarmList、DevOnlineList：`Class A`。
* Realtime media open/close/consumer：`Class B`，M4 仅作为业务下钻。
* 历史事件、数据质量、统计、Dashboard 和业务关联：`Class C`。
* AEE 页面状态、路由、UI glue 和用户配置：`Class D`。

## M4 Decision

* 先稳定 capability/interface/field catalogs 和 availability matrix，再实现
  PostgreSQL ingestion、统计 API 和 Dashboard。
* 聚合逻辑先以纯函数和脱敏 fixture 固化，避免在 AEE HTTP 认证和 PostgreSQL
  生命周期尚未验证时把网络、持久化与业务统计耦合。
* AEE `/api/v1/*` 数据接口的自定义 `token` header 已有静态证据；不得改用未经
  证实的 `Authorization: Bearer`。Token-only live sufficiency、Cookie dependency、
  生命周期和 refresh 仍需验证。
* PostgreSQL migration/repository 实现必须等到可用的隔离 PostgreSQL 环境和
  migration/backup/restore 工具链就绪；不得以 SQLite 或未演练的 SQL 替代
  PostgreSQL 验收。
* 当前不启动 production DB migration，不修改 production feature flag、Nginx、
  systemd、`current` 或 AEE Secret。
* 不引入 FFmpeg、SFU、transcoding、custom decoder 或复杂 AccountPool。
* 下一优先证据为：
  `/api/v1/DevOnlineList` raw response/status map/retention、AlarmList code
  map/lifecycle、media ID/状态语义和用户活动接口是否存在。

---

## Issue

Production Canary 中 `WXB358` 无法产生首帧；首次测试中 `WXB353` 成功播放后，
增加 `WXB358` 失败；第二次将 `WXB358` 作为第一路单独打开仍失败。

状态：`KNOWN UPSTREAM/DEVICE MEDIA AVAILABILITY EXCEPTION`

## CHA Evidence

* AEE server-side login 成功。
* Gateway WebSocket 和 Media WebSocket 建立成功。
* Media room join 成功。
* `openVideo` 路径被接受。
* `WXB358` 在等待窗口内未收到首帧，进入 `FIRST_FRAME_TIMEOUT`。
* 浏览器报告 `openvideo is not defined`。
* 两次失败 Session 均记录 `session_closed`。
* 两次 Gateway 和 Media proxy 均记录 disconnected。
* Realtime 随后恢复为关闭状态；Legacy/V2/Nginx 健康。

## AEE Evidence

状态：
`PARTIAL DEVICE EVIDENCE / WXB358 MEDIA-OFFLINE / AEE VERIFICATION REQUIRED`

已完成的合法、脱敏 AEE 对照证据见：

`docs/codex/AEE_VS_CHA_WXB358_20260814.md`

当前已确认：

* AEE 页面将 `WXB353` 映射为 `JDTY04295`，将 `WXB358` 映射为
  `JDTY04296`。
* 当前观察窗口内两台设备均为 online，device-level `enableVideo=true`。
* 首个合法测试登录没有有效 `VIDEOMONITOR` 权限；后续已切换到具备
  `VIDEOMONITOR` 权限的合法测试登录。授权账号的 permission list 包含
  `VIDEOMONITOR`，两个目标节点均为 `draggable=true`。
* 所有播放均通过 AEE Monitor 正常 drag/drop UI 发起；只增加脱敏的被动观察，
  没有绕过权限或直接伪造私有媒体请求。
* AEE 页面提供 lowercase `openvideo`、WASM decoder 和 Canvas 渲染运行时。
* 当前 live AEE SDK 与 vendored MCS8 SDK 中 lowercase `openvideo(...)`
  均只有一个调用点：`newConsumer` 的 H.265 codec 分支。该分支不会创建正常
  WebRTC consumer。
* CHA 页面没有 AEE 的 page-global H.265/WASM glue，因此当 SDK 进入该分支时会
  产生 `openvideo is not defined`。
* `2026-08-14` 当前 live AEE `mcs8Client.js` 与 CHA vendored SDK 已完成逐字节
  对照。两者唯一差异是 live SDK 仅在 `mediaHttpProxy` 非空且 `ssl == true`
  时采用 media proxy；去除该 27 字符条件后两份 bundle 完全一致。
* 上述 SDK drift 不太可能解释本次首帧失败，因为失败 Canary 已完成
  Gateway/Media 连接、room join 和 `openVideo`，之后才在浏览器触发
  `openvideo is not defined`。该判断是基于现有时序的推断，不代表可忽略未来
  SDK 版本漂移。
* AEE H.265 页面 runtime 由 `videoClient.js`、Emscripten
  `libstream_process.js/.wasm` 和 `webgl.js` 组成；它通过 same-origin
  `/mediaStream` WebSocket、WASM decoder 和 Canvas/WebGL 渲染工作。
* AEE page glue 会把媒体 token 带入 `/mediaStream` URL，并将完整
  `videoParam` 输出到浏览器 console。因此该实现只能作为 Class D 参考，
  不得直接复制到 CHA 或突破现有凭据/日志安全边界。
* 当前 AEE Monitor/SDK 的视频请求使用固定 `mediaMonitor streamType=2`；当前
  页面未发现 stream profile 选择器，但其它受支持 profile API 是否存在仍未确认。
* 当前 live/vendored SDK 的 public
  `openVideo(devId, showObject, channelId, serverId)` 没有 codec/profile 参数，
  并固定发送 video `streamType=2`。lower-level media client 虽会透传
  `streamType`，但 SDK 中没有发现受支持的其它 live-video 值或设备级
  codec/profile selector。
* SDK 中可静态确认的 literal 仅为 live video `2`、audio `0`、playback
  `-1`。浏览器/Router RTP capability API 不能证明具体设备会产生何种
  codec/profile；不得通过猜测其它 `streamType` 值来绕过证据阶段。
* `2026-08-14 20:25–20:35 CST` 授权 AEE 对照中，控制设备 `WXB353`：
  * `mediaMonitor streamType=2` 在约 `53 ms` 后返回 `status=opened`；
  * `newConsumer` 为 `video/H264`；
  * `profile-level-id=42e01f`、`packetization-mode=1`；
  * 正常 WebRTC `MediaStream`，没有调用 lowercase `openvideo`；
  * 约 `1.825 s` 进入 `playing`；
  * 分辨率 `1920 × 1080`，video track 为 `live`；
  * close/reopen 再次成功。
* `WXB353` tile close 的 `closeMediaMonitor` 均在约 `56–57 ms` 成功返回；
  track 变为 `ended`、tile 清除、show-video map 回到 0。
* 当前 AEE SDK 在 tile close 后仍将 ended consumer 对象保留在内部
  `_consumerList` 且 `closed=false`，导航回 GIS 后仍存在。该结果是 AEE
  page/SDK bookkeeping 行为，不证明上游 producer 仍开放；CHA 不应复制该
  生命周期细节，继续保留现有显式资源释放要求。
* 同一授权会话中的目标设备 `WXB358`：
  * DevTree 报告 `online=1`、`status=1`、device-level `enableVideo=true`；
  * 当前 `alarm=205`，AEE 语言表将其标记为 Low battery；但尚无证据证明该
    alarm 导致媒体失败；
  * AEE 正常发送 `mediaMonitor streamType=2`；
  * Media 服务在约 `51–67 ms` 拒绝并返回
    `devices is offline request.method "mediaMonitor"`；
  * AEE UI 约每 3 秒重试并显示 `Unable to play`；
  * 没有 `newConsumer`、没有 device-specific RTP/codec、没有 lowercase
    `openvideo`、没有 `/mediaStream`、没有 track/Canvas first frame。
* 关闭失败 tile 后，`closeMediaMonitor` 成功、show-video map 回到 0、tile
  清除，且 `WXB358` 从未创建 consumer。
* `2026-08-14 20:59–21:00 CST` 在同一合法授权 AEE 会话中再次通过正常
  drag/drop UI 重试 `WXB358`：
  * 约 58 秒观察窗口内所有 `mediaMonitor streamType=2` 请求仍返回
    `devices is offline`，一般在 `55–75 ms` 内失败；
  * AEE UI 继续约每 3 秒重试并显示 `Unable to play`；
  * 仍没有 `newConsumer`、codec/RTP、lowercase `openvideo`、
    `/mediaStream`、track/Canvas 或首帧；
  * 使用正常 `Close all` 后，audio/video `closeMediaMonitor` 分别在约
    `52–62 ms` 成功，重试停止、video 元素清除、监看网格恢复为空。
* `21:05 CST` 被动读取 AEE 可见设备树实际使用的 React dataRef：
  * `WXB353` 为 `online=1/status=1/alarm=0`，`gpsTime=21:04:42`；
  * `WXB358` 为 `online=1/status=1/alarm=205`，但最后可见
    `gpsTime=20:22:14`；
  * 两者 `battery` 字段均为 0，因此该字段不能证明 alarm 205 或低电量是媒体
    拒绝原因；
  * 这进一步证明 DevTree online/status 可以与陈旧遥测及 Media offline
    并存，但仍不足以确定上游根因。
* `21:08:49 CST` 第三次被动可用性检查：
  * `WXB353 gpsTime` 已继续更新到 `21:08:00`；
  * `WXB358` 仍为 `online=1/status=1/alarm=205`，其 `gpsTime` 仍停留在
    `20:22:14`；
  * 因目标遥测没有恢复，本次没有再次触发已实证的三秒 `mediaMonitor` 失败循环，
    避免无新增证据的上游请求负载。

尚未确认但不阻塞当前 M3 Production Gate：

* AEE Media 服务再次接受 `WXB358` 时的实际 codec/profile；
* AEE 是否能在该设备媒体可用时产生 WebRTC track 或 Canvas 首帧；
* 实际 `/mediaStream` WebSocket 生命周期和关闭释放；
* 是否存在有文档或服务端支持的 MCS8 原生 H.264 stream/profile 选择，可避免
  H.265 fallback；当前 public SDK 静态表面未发现该 selector。

只有未来 AEE Media 自然再次接受 `WXB358` 且产生 `newConsumer` 时，才恢复
以下独立 compatibility 调查：

* AEE Media 是否接受并打开 `WXB358`；
* AEE 实际 SDK 方法名称、大小写、参数和返回值；
* Gateway/Media/room/openVideo/consumer/track/first-frame 顺序；
* RTP、codec、fmtp/profile-level-id、stream profile 和 capability；
* close、leave、disconnect 和资源释放。

使用 `WXB353` 作为当前已知成功对照设备。若在线并获批准，可增加历史验证设备
`WXB301`、`WXB342`、`WXB345`、`WXB367`、`WXB368`。

## Classification

当前分类：

* Class A：当前 `WXB358` 失败首先落在设备状态/Media 可用性层；DevTree online
  与 Media `devices is offline` 不一致。
* Class B：`newConsumer`、RTP、codec/profile、正常 WebRTC consumer 和受支持的
  H.265 媒体协议。
* Class C：CHA session、Canary、布局、状态、telemetry 和资源释放编排。
* Class D：AEE 页面状态、drag/drop UI、page-global glue 和页面私有集成。

当前 AEE 设备级结果没有复现 H.265 fallback，而是在 `mediaMonitor` 阶段提前
失败。因此当前时段不是 CHA-only 播放故障。历史 Canary 的
`openvideo is not defined` 仍表明当时可能收到 H.265 consumer，但在获得设备
媒体可用时的实际 `rtpParameters` 前，不得把 `WXB358 codec=H.265` 标记为
VERIFIED。

## Decision

* 在新的受控 Canary 开始前保持生产 Realtime 关闭。
* 当前不修改 CHA 媒体协议或 SDK Adapter；授权 AEE 当前也无法打开
  `WXB358`，没有证据支持 CHA-only 修复。
* 不增加 blind `openvideo` shim，不复制 AEE token-bearing page glue。
* 已实施最小 Class C 异常处理修正：
  * 将已实证的 `devices is offline` 映射为 CHA
    `DEVICE_MEDIA_OFFLINE`，不向用户暴露原始 AEE 错误；
  * `openVideo` rejection 后执行补偿性 `closeVideo`，对称清理 monitor 状态；
  * 不改变 `streamType`、codec、AEE Adapter 协议或生产开关。
* 不再等待、轮询或重复打开 `WXB358`；其当前分类为已知 upstream/device media
  availability exception。
* Production Canary 改用 AEE 原生页面已确认 `mediaMonitor=opened`、产生
  `newConsumer` 和首帧的健康设备。
* 当前 Production Gate 为 1 → 4 路。若不足 6 台健康媒体设备，则记录
  `6-stream production verification: NOT EXECUTED — INSUFFICIENT HEALTHY MEDIA DEVICES`，
  不阻塞 M3 首发。
* 若 1 路和 4 路 Production Canary PASS，生产首发最大路数建议设为 4；保留
  development validated limit 6，未来单独完成 6 路生产容量验证后再提升。

## Production Canary Evidence — 2026-08-15

### AEE-native precheck

同一合法 `VIDEOMONITOR` 用户、同一 Chrome/网络观察窗口：

* `WXB309`：`mediaMonitor=opened`、`newConsumer`、H.264
  `profile-level-id=42e01f`、1920 × 1080、首帧 PASS、关闭 PASS。
* `WXB312`：`mediaMonitor=opened`、`newConsumer`、H.264
  `profile-level-id=42e01f`、1280 × 720、首帧 PASS、关闭 PASS。
* `WXB353`：`mediaMonitor=opened`、`newConsumer`、H.264
  `profile-level-id=42e01f`、1920 × 1080、首帧 PASS、关闭 PASS。
* `WXB364`：`mediaMonitor=opened`、`newConsumer`、H.264
  `profile-level-id=42e01f`、1920 × 1080、首帧 PASS、关闭 PASS。

### CHA Production Canary

* 单路 `WXB353`：
  * first frame `19:02:30 CST`；
  * 1920 × 1080、Track live、heartbeat PASS；
  * selective close 约 `991.85 ms`；
  * 同 session reopen first frame `19:04:01 CST`；
  * session close 约 `1076.35 ms`。
* 四路：
  * `WXB312` first frame `19:05:39`，1280 × 720；
  * `WXB309` first frame `19:05:40`，1920 × 1080；
  * `WXB364` first frame `19:05:42`，1920 × 1080；
  * `WXB353` first frame `19:05:44`，1920 × 1080；
  * 四路均 `PLAYING` / Track live；
  * `WXB309` screenshot PASS；
  * selective close `WXB312` 约 `991.855 ms`，其它三路继续播放；
  * `WXB312` reopen first frame `19:07:40`；
  * session close 约 `2508.81 ms`。
* 关闭后 diagnostics：
  * active sessions `0`；
  * active streams `0`；
  * Gateway connections `0`；
  * Media connections `0`；
  * release failures `0`；
  * first-frame timeouts `0`；
  * screenshot success `1`、screenshot failure `0`。
* authenticated non-Canary：
  * 页面显示“当前登录用户不在受控 Canary 范围内”；
  * diagnostics 和 create-session API 均 `403 canary_forbidden`；
  * control/gateway/media WebSocket 均 `403`。
* 浏览器全屏：
  * button/event handler 和错误反馈路径已在生产触发；
  * 自动化 Chrome 返回“浏览器未允许进入全屏”；
  * 当前状态为 `COMPLETED / UNVERIFIED`，需要普通用户操作复核。
  * `19:28–19:33 CST` 已再次建立 WXB353 生产播放窗口并准备人工复核；
    WXB353 于 `19:29:28` 获得 1920 × 1080 首帧和 live track，但浏览器 tab
    在确认成功进入/退出全屏前关闭。
  * page-exit cleanup 正常完成：session 约 `7.2 ms` 关闭，Gateway/Media proxy
    均断开，Realtime 随后恢复为 `false`。该结果新增证明异常离页释放，不构成
    全屏 PASS 证据。

详细脱敏证据见：

`docs/M3_PRODUCTION_CANARY_20260815.md`

## Rejected Alternatives

当前拒绝：

* FFmpeg；
* SFU；
* 自建 media server；
* custom decoder；
* transcoding pipeline；
* complex proxy/protocol translation；
* 通过扩大账号池掩盖单设备行为差异。

拒绝原因：尚无证据证明 AEE/MCS8/浏览器原生能力不能满足需求，也尚未确认问题位于
上游设备、stream profile、SDK 调用还是 CHA 编排层。

---

# 12. Done Criteria

Active Milestone 只有同时满足以下条件才能完成：

1. Scope 中功能全部实现；
2. 所有 Critical Acceptance Criteria 有实际证据；
3. 相关自动化测试通过；
4. 必要浏览器实际验证通过；
5. 媒体生命周期验证通过；
6. 无已知 blocker；
7. 无未解释的重大 warning/error；
8. 无遗留调试代码；
9. 无意外 secrets；
10. git diff 已审查；
11. Runbook / documentation 已同步；
12. production rollout / rollback path 明确；
13. AEE 相关未知项已经解决，或者明确登记为不阻塞当前 Milestone 的
    `AEE VERIFICATION REQUIRED`；
14. 最终形成 Milestone Completion Report。

M3 当前额外 Done Criteria：

* 至少 1 个 AEE-native 正常设备完成 AEE/CHA 同设备对照 PASS。
* 当前生产 release 的 1 路 Production Canary PASS。
* 当前生产 release 的 4 路 Production Canary PASS，四路首帧均正常。
* authenticated non-Canary 页面/API/WebSocket 拒绝通过。
* 首帧、分辨率、track live 和截图均有实际证据。
* Fullscreen 代码路径已有生产触发证据；普通用户 enter/exit/playback-continuity
  证据保持 `COMPLETED / UNVERIFIED`，由批准的 evidence waiver 非阻塞关账。
* selective close、survivor 和 reopen 通过。
* Session/Stream/Gateway/Media active counters 全部回到 0。
* `realtime_release_failure_total` 在本轮 Canary 中无新增。
* Legacy 与 V2 服务健康，无 release 引入的 5xx/restart。
* Realtime 仍受 Canary 用户限制；Audio、Control、AccountPool 保持关闭。
* AEE 长期凭据继续只保留在服务端生产配置。
* 生产启用或继续关闭的决定有明确记录。
* `WXB358` 明确登记为非阻塞的已知 upstream/device media availability
  exception。
* 若不足 6 台 AEE-native 健康媒体设备，6 路生产验证可以 evidence waiver：
  `NOT EXECUTED — INSUFFICIENT HEALTHY MEDIA DEVICES`，不阻塞 M3。

未满足以上条件：

不得宣布 Active Milestone 完成。

M3 Closure Exception：

* 项目负责人已明确批准 Fullscreen evidence waiver。
* 该 waiver 仅豁免真实普通用户 Chrome 的
  `enter fullscreen → exit fullscreen → playback continues` 人工证据；
  不把 Fullscreen 标记为 PASS，不豁免其它安全、媒体生命周期、资源释放或回归要求。
* 其它 M3 Done Criteria 已由现有自动化、真实 AEE、Production Canary 和生产安全
  证据满足，因此 M3 最终状态为
  `CLOSED / ACCEPTED WITH EVIDENCE WAIVER`。

M4 Done Criteria：

1. 完成 AEE 能获得的数据能力清单，并记录合法取证证据。
2. 完成 CHA 当前数据能力清单和 Legacy 依赖审计。
3. 所有目标字段均被分类为
   `AVAILABLE`、`DERIVABLE`、`RESTRICTED`、`NOT_AVAILABLE` 或 `UNKNOWN`。
4. 明确哪些数据开始形成历史沉淀及其来源、时间语义和保留策略。
5. 每一个 Dashboard 指标都有明确数据来源、刷新频率、数据新鲜度和异常处理。
6. 建立并验证必要的历史模型；不持久化 WebRTC runtime 临时状态。
7. PostgreSQL migration 在隔离环境完成 rehearsal、backup 和 rollback；
   未经授权不修改 production database。
8. 第一版多页面 Dashboard 至少包含：
   监察总览、设备运行、视频数据、实时监察运营。
9. Drill-down 至少支持：
   总览 → 部门/城市 → 设备 → 时间线，并能进入已有实时或历史业务入口。
10. 自动化测试、前端 build、后端 health、数据质量和回归检查通过。
11. Remaining Data Gaps 和 `AEE VERIFICATION REQUIRED` 明确登记。
12. 没有 secrets、虚假指标、无来源字段或未经批准的媒体架构升级。
13. 形成 M4 Completion Report，但不得自动进入 M5。

---

# 13. Current Execution Plan

## Completed

* M0、M1、M2 已发布并验证。
* M3.1、M3.2A、M3.2B、M3.2C 和 M3 Final 当前首发范围代码已完成。
* Release-fix、2026-08-15 生产备份、独立 release 部署和 health 已完成。
* 两次失败 Canary 的 Session/Gateway/Media 资源均已释放。
* 项目治理文件和 AEE Reference 原则已接入。
* 已使用具备有效 `VIDEOMONITOR` 权限的合法 AEE 登录完成 `WXB353` 控制播放：
  H.264 `42e01f`、1920 × 1080、约 1.825 秒首帧、close/reopen 成功。
* 已完成当前时段 `WXB358` AEE 目标测试：DevTree online，但 Media
  `mediaMonitor` 返回 `devices is offline`，失败 tile 可正常关闭并清理。
* 已完成 `20:59–21:00 CST` 第二次授权可用性复测：同一错误持续约 58 秒，
  正常 Close all 后上下游监看请求和页面元素均完成清理。
* 已完成 Class A 设备树时效对照：`WXB353` GPS 时间持续更新，而
  `WXB358` 的可见 GPS 时间停留在 `20:22:14`，与 Media offline 一致但不构成
  因果证明。
* 已完成最小 Class C 修复：`DEVICE_MEDIA_OFFLINE` 错误归一化和
  open-rejection 补偿性 close；Node runtime test 与全量 `73 tests` 通过。
* 已完成 `WXB309/WXB312/WXB353/WXB364` AEE-native precheck。
* 已完成生产 1 路和 4 路 Canary、截图、selective close、survivor、reopen、
  session close 和资源计数归零。
* 已完成 authenticated non-Canary 页面、API 和三个 WebSocket 生产拒绝验证。
* Canary 结束后 Realtime 已恢复关闭；Legacy/V2 health PASS，
  `NRestarts=0`。
* M3 已按项目负责人决策
  `CLOSED / ACCEPTED WITH EVIDENCE WAIVER`。
* Fullscreen 保持 `COMPLETED / UNVERIFIED`，移动到
  `POST-M3 OPERATIONAL FOLLOW-UP`。
* 已创建 M4 独立 Git branch：
  `codex/m4-inspection-data-center-20260815`。
* 已完成初始 CHA 数据能力代码审计。
* 已创建：
  * `docs/data/CURRENT_CHA_DATA_CAPABILITIES.md`；
  * `docs/data/DATA_AVAILABILITY_MATRIX.md`；
  * `docs/data/HISTORICAL_DATA_MODEL.md`；
  * `docs/data/DASHBOARD_INFORMATION_ARCHITECTURE.md`；
  * `docs/aee/AEE_CAPABILITY_MATRIX.md`；
  * `docs/aee/AEE_INTERFACE_CATALOG.md`；
  * `docs/aee/AEE_FIELD_CATALOG.md`。
* 已完成 AEE DevTree、Server Files 和 Alarm 页的第一轮合法只读接口取证。
* 已完成 `/api/v1/DevOnlineList` 和三个文件统计页面的 live/static 对照：
  online transition 与 `RecordFileList` 客户端聚合算法、单位和 10,000 行上限已
  记录。
* 已实现并测试确定性设备在线时长和文件统计聚合基础：
  `mature-modernization/v2/app/data/metrics.py`；
* 已实现并测试只读 AEE HTTP transport foundation：
  `mature-modernization/v2/app/data/aee_http.py`；
* 已实现并测试 endpoint-specific read-only Adapter contracts：
  `mature-modernization/v2/app/data/aee_adapter.py`；
* 已实现并测试 deterministic pagination/completeness collector：
  `mature-modernization/v2/app/data/pagination.py`；
* 已实现并测试 `DeviceStatusEvent` / `MediaFile` normalization：
  `mature-modernization/v2/app/data/normalization.py`；
* 已实现并测试 Legacy GPS-history `DeviceLocationEvent` normalization：
  明确 per-device scope、坐标校验、UTC 生命周期、nullable measurements、
  source raw codes 和 restricted/unknown quality flags；
* 已实现并测试 `RealtimeViewEvent` contract 和 Realtime lifecycle sink：
  `mature-modernization/v2/app/data/realtime_views.py`；
* 已实现并测试 AlarmList Adapter contract 和 `AlarmEvent` normalization；
* 已实现并测试 Realtime/Alarm deterministic event metrics；
* 已实现并测试 DeviceLocation threshold-free deterministic metrics；
* 已实现并测试 `InspectionStore` repository 抽象与内存实现
  （`app/data/store/`），并编写 PostgreSQL migration 草稿
  （`mature-modernization/v2/migrations/0001_inspection_history.sql`）；
* 已实现并测试 `StoreViewEventSink` 及 session manager 集成
  （`app/data/store/sinks.py`）；
* 已实现并测试只读 `InspectionDataService` 页面数据服务层
  （`app/services/inspection.py`）；
* 已实现并测试只读 inspection API
  （`app/api/inspection.py`，feature flag 默认关闭）；
* 已实现并测试第一批专题页（`/api/v2/dashboard/{devices,media,realtime}`，
  `app/templates/inspection.html`）；
* 已实现并测试设备时间线下钻（`device_timeline` service + API + 页面交互）；
* 已实现并测试 realtime 运行态快照（API 可选 realtime manager + 页面展示）；
* 已完成 Legacy media/business-reference heuristic code audit，并将 active
  routine-task candidate 与 dormant flight code 明确区分；
* 当前全量 V2 回归 `177 tests PASS`。

## In Progress

* `ACTIVE MILESTONE: M4`。
* 正在把已验证的 AEE/CHA 字段语义固化为窄 contracts、normalized historical
  records、page completeness、data-quality evidence 和确定性统计边界。
* 正在为已完成的 DeviceStatus、DeviceLocation、MediaFile、RealtimeView 和
  Alarm 应用层 contracts 编写 PostgreSQL schema/migration files 和
  driver-agnostic repository 抽象及单元测试；当前不启用生产 sink，也不以
  SQLite 或未执行 SQL 代替 PostgreSQL 验收。
* 正在补齐 AEE HTTP Token-only sufficiency/lifecycle、device online status
  map、alarm lifecycle/code maps/retention、media code maps 和用户活动数据证据。
* 正在准备 PostgreSQL repository/migration 的隔离运行条件；当前尚未开始
  production 或本地假替代 migration。
* `P2`：Legacy media→flight/task 自动匹配已降级，仅在获得 AMRO 脱敏样例、
  stable identity、时区证据、correction lifecycle 和人工确认正负样本后恢复。

## Next

1. `P0`：固化 `DeviceStatusEvent` / `MediaFile` 标准 contract（已实现并测试；
   保持窄 scope 和 raw code/quality flag 语义）。
2. `P0`：在合法、安全条件允许时捕获 `/api/v1/DevOnlineList` 和
   `/api/v1/RecordFileList` 脱敏 raw response，验证字段、时间语义、分页、
   retention 和 stable identity；不记录 Cookie/Token/密码。
3. `P0`：在合法、安全条件允许时验证 AEE 数据接口 token-only sufficiency、
   Cookie 依赖、失效与刷新行为；只记录脱敏结论。
4. `P1`：继续 Alarm 只读取证 alarm/status/deal code map、生命周期、删除语义和
   retention；不能标记语义 VERIFIED 的保持 `UNKNOWN`。
5. `PostgreSQL`：编写 5 张历史表的 schema/migration files 和
   driver-agnostic repository 抽象 + 单元测试；获得隔离 PostgreSQL 后再执行
   forward、rollback、backup、restore rehearsal。
6. 保持 Production Realtime、Audio、Control、AccountPool 关闭。

## Blocked

* 当前无 M4 项目级 blocker。
* 无法从合法 AEE 会话确认的接口和字段必须标记
  `AEE VERIFICATION REQUIRED` 或 `UNKNOWN`，但不阻塞无依赖的 CHA 审计和模型设计。
* production DB migration 在没有 rehearsal、backup、rollback 和明确授权前
  `BLOCKED`。
* 当前开发机缺少 Docker/PostgreSQL、`psql`、`pg_dump` 和 `pg_restore`；
  因此隔离 PostgreSQL migration/backup/restore rehearsal 在该环境
  `BLOCKED`。这不阻塞纯 contracts、normalizer、fixture 和无数据库单元测试。
* 正式 AEE 数据 Adapter 的登录所有权、Token-only live sufficiency、生命周期
  和刷新策略在形成合法证据前 `BLOCKED`。只读 HTTP transport 和无网络
  normalizer 不受此阻塞；不得猜测 Bearer header 或让浏览器长期持有 AEE 凭据。
* media-to-flight/task 自动关系和 coverage rate 在缺少 AMRO 脱敏字段样例、
  stable identity/time code map、分页完整性和已确认正负样本前 `BLOCKED`。
  该方向已降级为 `P2`，不阻塞 P0/P1 和 PostgreSQL contract 工作。

## AEE Verification Required

* AEE 设备运行字段：
  `last_online`、`last_offline`、`last_seen`、login/startup time、network state、
  battery、media availability、device model。
* `/api/v1/DevOnlineList`：
  raw response、完整 status map、ordering、duplicate、时间精度、分页、
  retention 和 query-boundary 行为。
* AEE 文件剩余语义：
  stable ID scope、完整 upload status/source code map、storage/channel，
  以及按用户/组织查询的权限边界。
* AEE 用户使用数据：
  login/logout、session、last active、访问设备、Realtime 监察记录和观看时长。
* AEE `/api/v1/*` 数据 API 认证边界：
  custom `token` header 已静态确认；仍需确认 token-only live sufficiency、
  是否还依赖 Cookie、是否与 Realtime access token 完全同源、有效期、刷新方式、
  服务端最小暴露方案，以及失败时的状态码/错误模型。只记录脱敏结论，不记录
  Cookie、Authorization、密码或可复用 Token。
* AEE 告警剩余语义：
  alarm/status/deal code map、level、lifecycle、删除语义、retention、pagination、
  handler/description 权限边界。
* 对每个未知项必须记录所需页面、用户权限、HTTP/WebSocket/SDK 证据、刷新频率和
  敏感等级；不得猜测。
* `WXB358` compatibility 调查仍为 `NON-BLOCKING / PAUSED`，不属于 M4 数据主线。
