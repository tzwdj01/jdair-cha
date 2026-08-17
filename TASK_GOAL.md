# CHA Video Record System Optimization — Active Task Goal

Last updated: 2026-08-16

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
  `GET /api/v2/dashboard/{devices,media,realtime,alarms}` 渲染四标签页面
  （`app/templates/inspection.html`），只消费已接线的 inspection API；
  store 未接入/为空时页面诚实显示“数据源未接入/待验证”，不伪造指标；
  告警标签展示 raw alarm/status/deal code 分布与每设备计数，并明确标注
  code map 尚未验证、不映射业务标签。
* 已增加设备时间线下钻：
  `GET /api/v2/inspection/devices/{device_id}/timeline` 返回单设备的
  status/media/location 时间线；坐标 restricted 且不输出；设备页内联渲染，
  形成 总览 → 设备 → 时间线 下钻路径。
* 设备/媒体概览增加 group 维度：按 `group_id` 聚合（部门/分组），提供
  部门/分组 → 设备 drill-down 层；city 仍为推导值，在受治理的
  geocoding/坐标策略前不产出。
* 增加非生产 dev store 接线：`CHA_V2_INSPECTION_STORE_MODE=memory` 仅限非生产
  环境，接通 realtime view sink → store → service → API → 页面 的端到端链路；
  生产始终无 store，页面保持诚实空态。
* 已增加 `InspectionIngestor` 写入侧摄入接缝：DevOnlineList/RecordFileList/
  AlarmList rows 经 normalize 后持久化进 store，并报告 accepted/invalid 数量
  与 quality flags；不依赖 AEE 认证（live token/session 仍为独立未验证前提）。
* 已增加数据质量诊断：按窗口统计各历史表行数、含质量 flag 行数、最新时间、
  设备数与来源系统分布，接入 `/api/v2/inspection/data-quality` 与
  “数据质量”标签；只报告 store 中真实存在的行，不推断缺失数据。
* 已增加摄入调度编排 `InspectionIngestionScheduler`：显式窗口 +
  source-agnostic `RowCollector` 协议，fake collector 可测，不假设 AEE 认证。
* 已提供 AEE 数据取证 Runbook（`docs/aee/AEE_DATA_VERIFICATION_RUNBOOK.md`）：
  DevOnlineList / RecordFileList / token-cookie 依赖 / AlarmList 的脱敏取证
  步骤与证据模板。
* 已增加受治理阈值机制：`CHA_V2_INSPECTION_THRESHOLDS`（JSON 正数）配置后，
  `long_no_upload_hours`（媒体）与 `stale_location_hours`（位置）才产出
  per-device 分类，`as_of` 可注入保证确定性；未配置不产出任何标签。
  “长时间离线”在非 1 status map 验证前仍不产出。
* 已增加 `AEEInspectionCollector`：组合已验证 adapter 契约 + `collect_aee_pages`
  收集 DevOnlineList/RecordFileList（AlarmList 需显式 selector），以
  `CollectedSource` 保留完整性元数据；alarm selector 未配置时不猜测、直接跳过。
  collector → scheduler → ingestor → store 全链代码就绪，待 live 取证后接线。
* realtime 概览增加运行态快照：接入 realtime manager 时返回当前 active
  sessions/streams、Gateway/Media 连接；无 manager 时 `runtime=null`，
  运行态与 store 历史严格分开。
* 已完成 Legacy media-to-flight/task reference helper 的代码取证：
  当前 active batch path 只加载 routine tasks，普通 flight matcher 为未接线
  reference code；现有 city/time/score/certainty 只能作为 unverified candidate，
  不得用于 confirmed relation 或 coverage rate。
* 当前全量 V2 自动化回归为 `201 tests PASS`。
* 当前开发机没有 Docker、PostgreSQL client/server、`pg_dump` 或
  `pg_restore`。因此不能在此环境宣称 PostgreSQL migration、backup 或 restore
  rehearsal 已完成。
* `2026-08-16` 已使用合法授权测试账号（具备
  `VIDEOMONITOR` 权限）在真实 Chrome 中按
  `docs/aee/AEE_DATA_VERIFICATION_RUNBOOK.md` 完成 P0 数据能力取证，全部只读，
  未写入任何生产数据。密码/Token/Cookie 未进入任何文件、日志或 Git。
* `DevOnlineList` LIVE VERIFIED：
  `error=200` envelope，3 天窗口 `recordsTotal=1696, pageCount=1,
  length=10000`；行字段 `id, enterId, enterName, groupId, groupName, devId,
  devType, devName, status, time, lat, lng, addr, remarks, storeType,
  network, battery, totalSize, useSize, version, hardware`；`id` 1696 行唯一，
  `time` 为非空业务本地时间；`status=1`（849）与 `status=0`（847）；
  同设备可见 transition 行（如 `WXB301` `1 → 0 → 1`）。
* `RecordFileList` LIVE VERIFIED：
  `error=200` envelope，3 天窗口 `recordsTotal=711, pageCount=1,
  length=1000`；55 字段行 schema；`fType` 1/2/3=image/audio/video
  （16/6/689）；`fileLen` 为字节、`duration` 为秒；`id` 711 行全局唯一；
  capture/end/file/upload 时间全部非空；窗口内未观察到跨页截断。
* `AlarmList` LIVE VERIFIED：
  `error=200` envelope，`recordsTotal=41, length=1000`；行 schema 含
  `id, enterId, groupId, devId, alarmTime, alarmType, status, alarmDesc,
  dealType, dealStatus, dealUser, dealTime, dealDesc, gpsModel, code, ex,
  keywords, peopleNo, workNo`；`alarmType` 205/206；**行内无
  `alarmStatus` 字段，告警状态由 `status` 字段承载**（已由
  `AlarmEvent` normalizer 以别名接受）。
* 认证依赖 LIVE VERIFIED：同源 `fetch` 不带页面注入的 `token` header 时返回
  `error=333`（HTTP 200 无数据）——数据 API 为 **TOKEN_REQUIRED**，仅 Cookie
  不足；长期 Token 生命周期/刷新仍待服务端集成验证。
* 页面“在线时长”`Hour/Min` 列与朴素区间截断求和不一致（如 `WXB310`
  ~32h vs 12Hour），记录为未验证的展示投影；CHA 必须自己计算确定性的
  区间截断在线时长。
* 已将脱敏 live 样本固化为确定性 fixture 与回归测试，并完成 ONE SHOT
  INGESTION 一致性验证（source rows 5/3/4 = accepted = stored rows，
  invalid=0，重复摄入幂等）。
* `2026-08-16` P0 认证收尾 LIVE VERIFIED（TOKEN-ONLY）：
  在授权 AEE 页面上下文中执行 `fetch`，只带自定义 `token` header 且
  `credentials:'omit'`（不发送 Cookie）：
  * `/api/v1/DevOnlineList` → HTTP 200、`error=200`、`recordsTotal=716`；
  * `/api/v1/RecordFileList` → HTTP 200、`error=200`、`recordsTotal=347`；
  * 不带 `token` header → `error=333`（HTTP 200 空数据）。
  * 结论：AEE 数据 API 仅凭自定义 `token` header 即可返回数据，不依赖
    Cookie；Token 值仅在页面上下文内引用，未读取、未记录、未提交。
* M4 P1 已开始：第一批历史数据资产（DeviceStatusEvent / MediaFile /
  RealtimeViewEvent / AlarmEvent）contract、repository、确定性指标、
  Dashboard API/页面均已具备；本轮补充：
  * `MediaFile` 增加 live 验证的 `end_at_source`（`endTime`）字段：
    contract + normalizer + migration + 测试；
  * inspection API 增加显式顶层 `meta` 信封
    （`generated_at` / `freshness` / `quality`），不再返回裸 KPI；
  * one-shot ingestion 改为按 source 独立持久化：单 source 失败以
    `error_code=SOURCE_INGEST_FAILED` 记录在报告内，不中断其它 source，
    不产生半成品状态；重试幂等（新增回归测试）；
  * 修复 `test_store_sinks.py` 中一个固定窗口 vs “now” 的时间炸弹测试。
* `M4 P2 — STAGING PERSISTENCE, LIVE INGESTION & METRIC VALIDATION` 已启动。
* `2026-08-16` P2 真实 ONE SHOT vertical slice（授权 AEE 会话，浏览器内
  脱敏抓取，不接触 Token）：
  * `DevOnlineList` 3 天窗口 `error=200`，1857 行；
  * `RecordFileList` 3 天窗口 `error=200`，805 行；
  * `AlarmList` 3 天窗口 `error=200`，46 行；
  * 管道（normalizer → memory repository → ingestor → metrics）一次摄入：
    device_status accepted=1857 invalid=0、media accepted=805 invalid=0、
    alarms accepted=46 invalid=0；completed=True；
  * 同窗口二次摄入 stored 行数不膨胀（1857/803/46 保持一致；
    media 805→803 为 source-record-id 幂等合并，2 条同源重复 id）；
  * 设备指标对账：54 台设备，真实 `1→0→1` 案例（如 `WXB301`：
    offline_transitions=14、`conflicting_status_same_time` 同秒冲突被显式
    标记）、`WXB305`（offline_transitions=17）；结果 deterministic；
  * 媒体对账：43 台设备、image=17/audio=6/video=782、
    video_duration=251306 秒（raw seconds）、size=147,809,843,624 字节
    （raw bytes）、partial=False；
  * 告警对账：46 条全部保留（alarmType=2×1 / 205×44 / 206×1），
    205/206 之外按 UNKNOWN 保留 raw value 不丢弃；
  * 覆盖语义：requested=4 days → available=4 days → FULL。
* 历史覆盖语义已接入 service + API + Dashboard：
  每个 overview 返回 `coverage{requested_window_days,
  available_coverage_days, completeness(FULL/PARTIAL/EMPTY),
  coverage_start_date, coverage_end_date}`；7d/30d 只有少量数据时按
  PARTIAL 展示，不伪装完整统计；Dashboard 新增 meta 条显示数据更新时间
  （Asia/Shanghai）、数据覆盖、源数据新鲜度与质量标记。
* 数据源隔离已实现：collector 按 source 独立收集（fail-closed /
  fail-isolated），单源失败以 `status="error"` + `error_code` 记录，不阻塞
  其它源；scheduler 报告显式暴露 source status / error code /
  last_successful_at / completeness。
* 当前全量 V2 自动化回归为 `213 tests PASS`。
* `POSTGRESQL_REHEARSAL_BLOCKED`：当前开发环境无 Docker/PostgreSQL、
  `psql`/`pg_dump`/`pg_restore`，无法执行真实 PostgreSQL rehearsal。
  该 blocker 只阻塞 PostgreSQL PASS，不阻塞其它 P2 代码与验证。
* `M4 P2.5 — PERSISTENCE & COLLECTION READINESS` 已启动：
  * MediaFile identity 审计（805 行）：`(source_record_id, device_id)` 全
    唯一，无 TRUE_DUPLICATE / 无 IDENTITY_COLLISION；**修正 P2 结论**——
    “stored 803 vs accepted 805” 不是幂等合并，而是 2 行 `startTime` 为
    `1970-01-01 08:00:00`（epoch-zero 缺失拍摄时间哨兵）导致窗口过滤；
    已修复 normalizer：该哨兵 → `None` + `epoch_zero_source_time_ignored`，
    修复后 stored=805=fetched；
  * DeviceStatusEvent duplicate 审计（1857 行）：1857 个唯一 source id、
    metrics 层按 (device,time,status) 去重 303 条且与保留行内容完全一致
    （仅 id 不同 → source-level redundancy，非真实 transition 丢失）；
    storage 保留全部 1857 行；同秒 0/1 冲突 173/173 全部保留为
    `conflicting_status_same_time`；新增显式标记
    `same_time_status_multi_source_dedup`；
  * PostgreSQL 环境探测：无 psql/pg_dump/pg_restore/docker/podman、
    无 Python PG 驱动、5432 无监听；WSL Ubuntu 无 PG 二进制；安装需
    root/admin → 按规则不自行安装，标记
    `POSTGRESQL ENVIRONMENT REQUIRED`（详见
    `docs/aee/M4_P2_5_POSTGRESQL_REHEARSAL.md`）；
  * LOW-RATE SCHEDULER SOAK 仅完成设计（`docs/aee/M4_P2_5_SCHEDULER_SOAK.md`），
    前置条件（media identity、device dedup、PG migration/backup-restore、
    ONE SHOT PG ingest、metric reconciliation）全部 PASS 前不启动；
    生产 scheduler 保持关闭。
* 当前全量 V2 自动化回归为 `215 tests PASS`。
* `2026-08-16` 项目负责人授权在开发机 WSL Ubuntu 建立隔离、可删除、
  NON-PRODUCTION PostgreSQL rehearsal 环境（Ubuntu 22.04.5 + PostgreSQL
  14.23，disposable `cha_m4_rehearsal` DB + `inspection_rehearsal` schema；
  密码仅存 `/root/.pgpass` 0600，未进入 Git/文档/日志）。
* M4 P2.5 PostgreSQL rehearsal 全部 PASS：
  * migration `0001` 应用 + schema/index/constraint 检查通过；
  * ONE SHOT ingest（`PostgresInspectionStore` + 现有 normalizer/ingestor）：
    device_status 1857/1857、media_files 805/805、alarms 46/46、
    realtime_view 1/1，report completed=True；
  * 同窗口二次摄入不膨胀（idempotency PASS）；
  * metrics reconciliation（memory == PG）四域全一致（含 coverage），
    PG-backed Dashboard API（5 端点）均 200 + coverage 语义正确 → PASS；
  * backup/restore：pg_dump+SHA256 → disposable target → pg_restore →
    行数/指标一致 → PASS；
  * rollback（forward-only 模型：fresh migration → restore backup）：
    行/指标与参考一致，RTO ≈ 0.9s → PASS；
  * NON-PRODUCTION LOW-RATE SCHEDULER SOAK（3 次重叠窗口 + 注入单源失败）：
    无增长、source isolation、恢复、请求量有界 → PASS；
  * rehearsal 过程中修复的失败点：`ON CONFLICT ON CONSTRAINT` 对 unique
    index 无效（改为列推断）、`pg_restore` 因 PGHOST/pgpass 匹配问题挂起
    （改为 PGHOST+PGPASSWORD 注入）。
* 新增 `PostgresInspectionStore`（`app/data/store/postgres.py`）实现
  `InspectionStore` 协议，连接配置仅来自 `CHA_PG_*`/`PGPASSWORD` 环境变量；
  新增 `tests/test_postgres_store.py`（无 PG 时自动 skip，有 rehearsal PG
  时执行真机往返测试）。
* 当前全量 V2 自动化回归为 `217 tests PASS`。
* `M4 P3 — INSPECTION WORKFLOW & PRODUCTION DATA ACTIVATION READINESS` 已启动
  （产品能力允许非生产实现；生产数据激活未授权）。
* P3 数据层：`AuthorizedUser` / `InspectionRecord` / `InspectionRecordViewLink`
  / `InspectionAuditEvent` dataclass（`app/data/inspection_records.py`）；
  migration `0002_inspection_workflow.sql`（authorized_users /
  inspection_records / inspection_record_views / inspection_audit_events）；
  `InspectionRecordStore` 抽象 + Memory + Postgres 实现。
* P3 业务层：`InspectionRecordService`（create_draft / update_draft / submit /
  correct / list(分页过滤) / dashboard_metrics），强制服务端身份、
  DRAFT→SUBMITTED→CORRECTED 生命周期、审计事件、修正保留原提交信息。
* P3 API：`/api/v2/inspections`（列表分页/详情/创建/更新/提交/修正）、
  `/api/v2/inspections/export`（CSV/XLSX，受 CHA 授权控制，无 Token/Cookie/
  Secret/凭据字段）、`/api/v2/inspections/metrics`、`/api/v2/dashboard/
  inspections` 页面（`app/templates/inspections.html`）。
* P3 授权边界：所有 inspections 端点校验当前登录账号是否在
  `AuthorizedUser`（enabled=true + 有效期）；`inspector_username` 由服务端
  会话确定，客户端不可自填。
* P3 Flights/Routine Tasks 取证：`docs/aee/M4_P3_FLIGHTS_ROUTINE_TASKS_
  EVIDENCE.md`（Legacy `/api/flights`、`/api/routine-tasks` 代码/静态证据；
  `taskid`/`inFlight`/`outFlight`/`outDate`/`inDate`/`startPlanDate` 已代码
  确认；`aircraft_no`/`flight_no`/`station`/任务类型等结构化字段待真实
  样本，保持 UNKNOWN/DERIVABLE，不猜测）。
* P3 Production Data Activation Plan：`docs/aee/M4_P3_PRODUCTION_DATA_
  ACTIVATION_PLAN.md`（生产 PG 部署建议、secret 注入、备份/迁移/回滚、
  AEE token provisioning/rotation、scheduler cadence 提案、Token 风险：
  TOKEN-ONLY VERIFIED / LONG-LIVED SERVER TOKEN LIFECYCLE NOT YET
  LIVE-SOAK VERIFIED）。
* 当前全量 V2 自动化回归为 `225 tests PASS`。
* P3.1（2026-08-16）：CHA live `/api/flights`（total=39）与
  `/api/routine-tasks`（total=48）字段取证完成；`taskid`/`flightId`/`acno`/
  `flightNo`/`std`/`sta`/`atd`/`ata`/`taskTypeName`/`taskstsName`/`bay`/
  `startPlanDate`/`outFlightNo`/`outDate`/`dep3code`/`arr3code` 等定级
  AVAILABLE；`fxWorker`/`wxWorker`/`*Emp` RESTRICTED（值未持久化）。
* P3.1：`InspectionBusinessCandidateService`（SOURCE_DIRECT 候选 + DERIVED
  辅助）+ `AuthorizedUser` admin 管理（list/add/enable/disable + 审计）+
  Realtime“记录监察结果”入口 + PG-backed 全链路 rehearsal 全部 PASS。
* 当前全量 V2 回归 `231 tests PASS`。
* `M4 P3.1 — INSPECTION WORKFLOW INTEGRATION & BUSINESS DATA VERIFICATION`
  已启动（P2.5 PASS / P3 product foundation PASS / Production activation
  NOT AUTHORIZED；PRODUCTION ACTIVATION READINESS: CONDITIONAL）。
* P3.1 live 业务字段取证（授权 CHA 会话，cha.jdair.top，只读）：
  `/api/flights`（2026-08-16 total=39）与 `/api/routine-tasks`
  （total=48）真实字段已捕获；`flightId/acno/flightNo/std/sta/etd/atd/
  eta/ata/dep3code/arr3code` 与 `taskid/acno/taskTypeName/taskstsName/
  bay/startPlanDate/outFlightNo/outDate` 等定级 AVAILABLE；
  `fxWorker/wxWorker/fxWorkerEmp/wxWorkerEmp` 定级 RESTRICTED（值未持久化）；
  `dorI/dd/fc/oxygen*` 等 UNKNOWN/PARTIAL。详见
  `docs/aee/M4_P3_FLIGHTS_ROUTINE_TASKS_EVIDENCE.md` 与
  `DATA_AVAILABILITY_MATRIX.md` §8.1/8.2。
* P3.1 `InspectionBusinessCandidateService` 已实现：按监察时间/设备/可选
  飞机/站点返回 Routine Task / Flight 候选（SOURCE_DIRECT；DERIVED 仅辅助，
  不自动确认）；`sanitize_task_raw` 剔除人员字段；已测试。
* P3.1 `AuthorizedUser` 管理最小闭环：admin-only
  list/add/enable/disable + `authorized_user_audit_events` 审计
  （operator/timestamp/target/action），普通用户 403；已测试。
* P3.1 Realtime 页面“记录监察结果”入口：m3_realtime tile 新增按钮，点击
  以当前流 device/session/stream/timestamps 创建监察草稿并跳转
  `/dashboard/inspections`。
* P3.1 PG-backed Inspection 全链路 rehearsal（WSL PG）：auth →
  realtime view → create（含 view linkage）→ submit → correct（原提交信息
  保留，audit=CREATED/SUBMITTED/CORRECTED）→ query → metrics → CSV/XLSX
  导出（无敏感字段）→ DB 行数对账 全部 PASS。
* Production Activation Plan 已按 P3.1 结果修订（A–K 检查清单）。
* 当前全量 V2 自动化回归为 `232 tests PASS`。

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

状态：`M4 ACTIVE / P2.5 PASS / P3 FOUNDATION PASS / P3.1 PASS / P3.2 PRODUCTION MCS8 ONE SHOT PASS — READY FOR LOW-RATE SCHEDULER CANARY`

（不得宣布 M4 COMPLETE。P0 数据能力获取已在授权 AEE 会话下完成 live 验证，
AEE 数据 API 已确认 TOKEN-ONLY / 无 Cookie 可用；P1 历史数据 contract /
repository / 指标 / Dashboard API 已具备；P2 真实 ONE SHOT 数据链路已
验证（DATA PATH VALIDATED）。M4 P2.5 — PERSISTENCE & COLLECTION READINESS
已全部 PASS：PostgreSQL rehearsal（migration/ingest/idempotency/metrics/
backup-restore/rollback）、PG-backed Dashboard API、non-production
LOW-RATE scheduler soak 均通过；P3 product foundation PASS；P3.1
INSPECTION WORKFLOW INTEGRATION & BUSINESS DATA VERIFICATION PASS（live
业务字段取证、候选服务、authorized-user 管理、realtime 联动、PG-backed
全链路 rehearsal、导出/审计 rehearsal）。

项目负责人已明确授权：`M4 P3.2 — CONTROLLED PRODUCTION DATA ACTIVATION &
CANARY`（有限、可回滚、分阶段生产授权）。仅授权：production PostgreSQL、
rehearsal 过的 migration、AEE data secret provider、低频只读 ingestion
scheduler、小规模 AuthorizedUser allowlist、Canary 用户 Inspection
workflow、inspection Dashboard/API、RealtimeViewEvent 采集、
InspectionRecord 保存、backup/health/audit。不授权全用户开放/32 路/PTZ/
自动 matcher/Legacy 替换/破坏性操作。M4 NOT COMPLETE。

`2026-08-16` 生产只读容量审计（jdair.top）结论：主机仅
`2 vCPU / 1.9 GiB RAM`，已用 1.7 GiB、可用约 244 MiB、swap 已用 752 MiB；
容量不足以安全同机承载 PostgreSQL + CHA + scheduler + backup。

项目负责人已提供新的独立 PostgreSQL 候选服务器：`PRODUCTION POSTGRESQL
CANDIDATE = ALIYUN SILICON VALLEY SERVER`（47.251.105.9）。
Preflight 已 PASS（干净专用节点；网络 ACCEPTABLE FOR CANARY）。
SERVER PREPARATION PASS；PG MIGRATION & CHA CONNECTIVITY gate PASS
（migration 0001+0002 → cha_m4；CHA→Aliyun PG 真连接；secret 0600；DML
smoke；pg_dump+restore）。生产 ONE SHOT 尝试被阻塞：JD Cloud WAF (JFE)
对 CHA 生产服务器 → aee.jdcloud.com 的服务端请求返回 HTTP 493。
**AEE ACCESS PATH DIAGNOSTIC（只读）确认**：493 是 **JFE source-IP WAF
策略**（CHA 出口 IP `111.228.15.31` 未命中 skip 规则、命中 `deny:uri`），
与浏览器 challenge 无关（本机纯 HTTP client 三接口均 200）。
**受支持服务器端通道已识别**：Legacy 生产已使用 MCS8 原生服务器
`116.198.18.19`（WS 登录 :7711 → REST :7712，token+SessionId），
`/api/v1/RecordFileList`（recordsTotal=202）与 `/api/v1/AlarmList`
（recordsTotal=7）实测可用；`GetDevListByGroupId` 返回 114 设备
（含 nOnline）可替代 DevOnlineList。M4 adapter 复用该通道即可，无需
WAF 变更。详见
`docs/aee/M4_P3_2_ACCESS_PATH_DIAGNOSTIC_20260816.md`。

`2026-08-17` **MCS8 NATIVE ADAPTER 已实现并真机验证**：MCS8ServerAuthProvider
（WS :7711 → token）+ MCS8DataHTTPClient（REST :7712，token+SessionId）+
MCS8ReadOnlyDataAdapter（DEVICE snapshot / MEDIA / ALARM）+ 诚实 polling
语义（INITIAL_OBSERVATION / CHA_OBSERVED_TRANSITION，同状态不新增）。
CHA scratch 只读验证 PASS：MCS8 auth → DEVICE 114（14 online/100 offline）
→ MEDIA 8 → ALARM 2。**Browser/AEE 前端 vs MCS8 native 对账一致**
（media recordsTotal=6=6、alarm=2=2、devs 相同）。**生产 ONE SHOT
PASS**：DEVICE 114 / MEDIA 8 / ALARM 2 写入 cha_m4/inspection，幂等重跑
无膨胀（device 二次 stored=0），PG 行数对账一致，metrics 对账一致。
未启用 scheduler；未激活 AuthorizedUser / Inspection workflow；生产
app/current/nginx/systemd 未改动。

`2026-08-18` **PRODUCTION LOW-RATE SCHEDULER CANARY — SHORT CANARY PASS /
DATA SEMANTICS PASS / PROCESS LIFECYCLE FIXED-VERIFIED**。生产 scheduler
（`app/services/mcs8_scheduler.py` + `scripts/m4_mcs8_scheduler.py`，cadence
600s / lookback 1h / overlap 5m，kill switch `CHA_V2_INSPECTION_SCHEDULER_ENABLED`）
已实现并测试（259 tests PASS）。第一轮 production canary 完成 **5 个连续
10 分钟 cycle** 的有效证据：Device same-state 无行膨胀、真实状态变化仅产生
observed transition、Media/Alarm identity 幂等、PG 持续写入、scheduler 内存
~39MB 稳定、MCS8 production data path 正常。原 canary 在 cycle 5 后等待
cycle 6 时因 **SSH/nohup session lifecycle**（非数据逻辑）提前退出；根因
归类为后台进程生命周期，正式 deployment 需 systemd 进程模型（setsid
独立会话已复验稳定）。restart verification PASS：重启后单 cycle 从 PG
latest state 继续，不重新生成 INITIAL_OBSERVATION（114 基线保持），仅真实
transition 入库。kill switch PASS：ENABLED=false 立即退出、不采集、不影响
历史 PG / realtime / Legacy / Dashboard。生产 PG 保留全部真实采集数据
（不清空）：device 137 = 114 initial + 23 cha_transitions、media 40、alarm 10。
LONGER OBSERVATION 将在以后 scheduler 正式运行中自然获得。**未进入
Inspection User Canary；未扩大 production rollout。

`2026-08-18` **PRODUCTION SCHEDULER OPERATIONALIZATION & REMOTE BACKUP**：

* **正式 systemd 部署**：`jdair-cha-m4-scheduler.service`（Type=simple,
  User=jdair-demo, EnvironmentFile=/etc/jdair-cha/m4-scheduler.env,
  Restart=on-failure, enabled+active）运行 `m4_mcs8_scheduler.py`
  （max_cycles=0 无限运行，period 600s，kill switch
  `CHA_V2_INSPECTION_SCHEDULER_ENABLED`）。正式 runtime：
  `/opt/jdair-cha/m4-scheduler`（独立 venv + app + scripts，jdair-demo 所有）。
  journald 日志有界、脱敏（无 password/token/SessionId/PG 密码）。
* **managed cycle PASS**：service 启动后首个 cycle 正常（DEVICE 114 /
  MEDIA 10 / ALARM 5，0 invalid），PG 持续写入；restart 后从 PG latest
  继续、不重新生成 INITIAL_OBSERVATION（114 基线保持，仅真实 transition
  入库）；kill switch ENABLED=false 立即退出不采集、历史 PG/realtime/
  Legacy/Dashboard 不受影响。
* **PostgreSQL 本地备份**：`ops/cha_m4_pg_backup.sh` + systemd timer
  `jdair-cha-m4-pg-backup.timer`（daily, Persistent=true）→ custom-format
  pg_dump + SHA256 + pg_restore -l 可读验证 + 14 天 retention，写入
  `/opt/jdair-cha/backups/pg/`。手动执行验证 PASS（46KB dump、SHA256、
  TOC 110 项可读）。
* **REMOTE BACKUP PASS — OFF-HOST COPY VERIFIED（2026-08-18）**：采用
  Aliyun PG 本机 local pg_dump（`/opt/jdair-cha/backups/pg-local/`）+ 通过
  **Tailscale 私密通道**拉取到 CHA `/opt/jdair-cha/backups/remote-pg/`
  （key-based scp，密码不写入脚本）。双主机备份（Aliyun `iZrj...` ≠ CHA
  `lavm...`），SHA256 一致，remote dump `pg_restore -l` 可读。daily timer
  已含 off-host 步骤；retention 配置化（local/remote 14 天）。
  `REMOTE BACKUP OWNER ACTION REQUIRED` 关闭。

`2026-08-18` **INSPECTION USER CANARY & BUSINESS WORKFLOW VALIDATION — PASS /
REAL BUSINESS DATA ACCUMULATION ACTIVE**：

* **Inspection-enabled v2 上线**：新 release `20260818022828-m4-inspection-canary`
  （含 inspection workflow + PG store gate），`inspection_v2=true`；
  `CHA_V2_INSPECTION_STORE_PG_ENABLED=true` 接线 Aliyun PG；v2 venv 增装
  psycopg2 + openpyxl。realtime_readonly 为 Canary 打开（audio/control 关）。
* **AuthorizedUser 边界 PASS**：enabled→进入；disabled→403
  `cha_access_forbidden`；inspector 访问 admin API→403 `admin_forbidden`；
  admin 管理（add/enable/disable）均写 audit（USER_DISABLED/USER_ENABLED）。
  Canary 账号：`lijian.1023`(admin) + `liujiawen53`(inspector)。
* **RealtimeViewEvent 生产链路 PASS**：真实 session+stream（WXB313）→
  view event 写入 PG（username/device/opened/closed/result）。
* **InspectionRecord 生产验证 PASS**：2 条真实记录（USER_CONFIRMED 候选
  关联 + MANUAL_ENTRY fallback），DRAFT→SUBMITTED→CORRECTED 生命周期，
  submitted_by/at 不被覆盖；audit trail（CREATED/SUBMITTED/CORRECTED）
  完整。has_issue=true/false 均验证。
* **查询/导出/Dashboard PASS**：`/api/v2/inspections` 列表、metrics
  （total=2、153s、per_account/per_device）、CSV 与 XLSX 导出（表头/中文
  内容正确，无敏感信息）、dashboard/inspections 页面 200。
* **生产数据（2026-08-18）**：device 142 / media 47 / alarm 12 /
  realtime_view_events 2 / inspection_records 4 / authorized_users 2 /
  audit 9。CHA 744Mi/1.9Gi、load 0.09；PG 9.9MB/1 conn。scheduler 持续
  正常（4 cycles，RSS 39MB）。）

`2026-08-18` **MULTI-PAGE OPERATIONAL DASHBOARD CONSOLIDATION — PASS**：

* 监察数据中心 Dashboard 整合为 **7 个操作域标签页**（`/api/v2/dashboard/`
  `devices` 设备运行 / `media` 视频上传 / `realtime` 监察使用 /
  `inspections` 监察记录 / `flights_tasks` 航班与维修任务 / `alarms`
  告警异常 / `data_quality` 数据质量），全部页面与数据 API 生产 200。
* 新增只读 `GET /api/v2/inspection/flights-tasks`（date 可选）：
  `InspectionDataService.flights_tasks_overview` 经
  `LegacyBusinessDataClient`（LegacyClient + `records` 载荷归一化）读取
  `/api/flights` 与 `/api/routine-tasks`，返回航班/维修任务参考视图
  （非自动 matcher，无自动关联）。生产实测：34 航班（JG2745/B-32Q8/
  重庆→孟买 等）、41 维修任务（过站/停场/待派工），中文航段/状态正确。
* `inspections` 标签复用 `/api/v2/inspections`（真实生产监察记录，
  authorized cookie），展示记录/监察人/设备/飞机/航班/站点/任务/问题/状态。
* 单测：`tests/test_flights_tasks_dashboard.py`（not wired / wired /
  cookie / upstream fail / `records` key）+ `test_inspection_api` 端点测试
  （client / not wired / invalid date）。全量回归 **271 tests PASS**。
* 生产部署：`20260818030117-m4-dashboard-consolidated` release active。
  生产数据（03:01）：device 146 / media 47 / alarm 14 / rtview 2 /
  inspection 4；CHA 724Mi/1.9Gi、load 0.12；PG 9.9MB；scheduler 持续
  正常（RSS ~36MB，55min）。）

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

### M4 核心业务目标补充：CHA 独有监察业务数据模型与监察记录工作流（2026-08-16 更新）

CHA 不只是复制 AEE 的设备/视频/告警能力。CHA 要在 AEE/MCS8/Legacy 数据能力
之上，形成自己的监察业务数据关系：

人员 + 设备 + 视频 + 飞机 + 地点 + 维修任务 + 问题 + 时间

最终形成可长期沉淀、查询、统计、审计和导出的监察业务数据资产。该关系模型是
M4 后半段（P3）的重要核心目标。

长期关系模型：

```text
Inspector / User
    ↓ Inspection
    ↓ Device
    ↓ Realtime / Historical Video
```

同时关联：Aircraft、Location / Station、Flight、Maintenance Task、Issue、
Time。业务上允许形成：人员 → 监察某设备/视频 → 对应某架飞机 → 某个站点/
地点 → 某个航班 → 某项维修任务 → 是否发现问题 → 问题内容 → 发生/监察时间。

飞机 / 航班 / 站点 / 维修任务数据来源：

* 优先从已存在的 Flights / Routine Tasks 接口获取结构化业务信息；
* 重点调查并标准化：`aircraft_no`、`flight_no`、`station`、`city/airport`、
  `task_id`、`task_type`、`task_name`、`task_status`、`planned_start`、
  `planned_end`、`actual_start`、`actual_end`、`department`、`team`、
  `related_device`（如上游真实存在）、其它稳定业务 identity；
* 所有字段必须基于真实接口证据，状态标记
  `AVAILABLE` / `DERIVABLE` / `RESTRICTED` / `NOT_AVAILABLE` / `UNKNOWN`；
* 不得根据页面显示、文件名、时间接近程度或猜测自动生成飞机/维修任务关系。

Routine Task 作为主要业务关联来源：

* 优先验证 Routine Task 是否存在稳定：任务 ID、飞机号、站点、航班号、
  维修任务类型、任务名称、计划时间、实际时间、任务状态、执行部门/班组；
* 字段真实存在 → 通过标准 Adapter 接入；字段不存在 → 不得自动推导并冒充
  source truth。

InspectionRecord（P3 规划正式建立）：

一次由 CHA 授权监察人员确认并提交的业务监察记录。建议字段：
`inspection_id`、`inspector_user_id`、`inspector_username`、`device_id`、
`realtime_session_id`、`realtime_view_event_id`、`media_file_id`（可选）、
`aircraft_no`、`routine_task_id`（可选）、`routine_task_source_id`（可选）、
`maintenance_task_text`、`flight_no`（可选）、`station`、`location_text`、
`inspection_started_at`、`inspection_ended_at`、`inspection_duration_seconds`、
`has_issue`、`issue_type`、`issue_level`、`issue_description`、`remark`、
`status`、`created_at`、`created_by`、`updated_at`、`updated_by`、
`submitted_at`。

字段来源原则（三类）：

* `A 系统自动生成`：监察账号、设备、session、stream、开始/结束时间、
  监察时长、首帧结果——不得由普通用户手工伪造；
* `B 上游业务接口带入`：飞机号、航班号、站点、Routine Task、维修任务——
  优先从 Flights / Routine Tasks 搜索、选择和关联，必须保留 `source`、
  `source_id`、`source_updated_at`、`association_method`；
* `C 监察人员填写`：是否发现问题、问题类型、问题描述、备注——允许业务人员
  填写。

人工选择优先于未验证自动匹配：

* 在 Flight/Routine Task 自动关联规则充分验证前，禁止自动替用户确定飞机/
  航班/维修任务；
* P3 第一版推荐：系统提供候选项 + 用户人工确认（输入/选择飞机号 → 查询
  对应时间范围 Routine Task → 显示候选 → 由监察人员选择）；
* 允许手工填写飞机号 / 维修任务文本作为 fallback；
* 不得用 Legacy 未验证 score 直接自动确认关联关系。

关联证据（association_method）：

* `USER_CONFIRMED`（用户选择）；
* `SOURCE_DIRECT`（接口直接返回且具有稳定 ID）；
* `MANUAL_ENTRY`（手工填写）；
* `DERIVED` / `UNKNOWN`；
* 不得把 `DERIVED` 显示成 `CONFIRMED`。

地点模型：

* 业务地点（station / airport / city）与设备地点（GPS / device location）
  不得混为同一字段；
* 未来允许展示“维修任务站点 + 设备实际 GPS”以判断设备是否出现在预期业务
  区域，但无业务规则和坐标系验证前不得自动判定“地点异常”。

问题记录：

* `has_issue = true/false`；为 `true` 时必须可记录 `issue_type` /
  `issue_level` / `issue_description`；
* `issue_occurred_at`、`video_offset_seconds`、`snapshot_reference` 等后续
  扩展不在当前 P2.5 提前实现。

用户身份与 CHA 授权：

* AEE 登录成功 ≠ 允许访问 CHA；
* P3 必须建立 CHA 自己的授权边界：只有存在于 CHA `authorized user list`
  且 `enabled=true` 的 AEE account 才允许进入 CHA；
* `inspector_user_id` / `inspector_username` 必须由 CHA 当前登录会话服务端
  确定，不得允许普通用户自行填写“监察人”。

RealtimeViewEvent 与 InspectionRecord 分离：

* 两个独立模型，不合并成一个大表；
* `RealtimeViewEvent` 回答“谁看了哪个设备、什么时候、多久、是否成功”；
* `InspectionRecord` 回答“为什么看、对应哪架飞机/站点/航班/维修工作、
  有没有问题、问题是什么”；
* 关系允许 `InspectionRecord` → one or more `RealtimeViewEvent`。

监察记录查询（P3 / Dashboard 后续）：

时间范围、监察人员、账号、设备、飞机号、航班号、站点、维修任务、
是否发现问题、问题类型、问题等级。

监察记录 Dashboard（后续新增 `/dashboard/inspections`）：

今日监察次数、监察总时长、参与监察人数、每账号监察次数/时长、
每设备被监察次数/时长、涉及飞机/航班/维修任务数量、发现问题次数/无问题
次数/问题发现率、问题类型分布、问题设备/飞机/站点排行、问题趋势。
所有指标必须由真实 `InspectionRecord` / `RealtimeViewEvent` 计算，不得生成
模拟 KPI。

监察记录导出（后续）：

第一阶段 CSV / XLSX；导出字段至少：`inspection_id`、监察日期、监察人、
账号、设备、飞机号、航班号、站点、维修任务、开始/结束时间、监察时长、
是否发现问题、问题类型、问题等级、问题描述、备注。所有导出受 CHA 权限
控制，不得输出 Token / Cookie / Secret / 内部 media credential。

审计与修改：

* 监察记录属于正式业务记录，禁止普通用户提交后无痕覆盖历史；
* 至少保存 `created_by` / `created_at` / `updated_by` / `updated_at`；
* 推荐状态 `DRAFT` / `SUBMITTED` / `CORRECTED`；
* 已提交记录被修改必须留下 correction/audit 信息。

### M4 后续路线（2026-08-16 更新）

当前阶段（不变）：`M4 P2.5 — Persistence & Collection Readiness`
（PostgreSQL rehearsal、identity/dedup 审计、non-production low-rate
scheduler soak）。继续执行，不改变。

P2.5 PASS 后：`M4 P3 — Production Data Activation & Inspection Workflow`

P3 重点（规划，未启动）：

1. 生产只读数据采集灰度；
2. CHA authorized user access control；
3. RealtimeViewEvent 长期积累；
4. InspectionRecord；
5. Routine Task / Flight 候选选择；
6. 人工确认飞机/航班/维修任务关系；
7. 问题记录；
8. Inspection Dashboard（`/dashboard/inspections`）；
9. 查询；
10. 导出（CSV/XLSX）；
11. Audit。

P3 明确暂不实现（本次仅更新规划，不提前实现）：

* InspectionRecord UI；
* CHA user ACL；
* Routine Task automatic matcher；
* Inspection Dashboard；
* export；
* issue workflow。

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
14. 将“CHA 独有监察业务数据模型与监察记录工作流”纳入 M4 正式范围：
    * 形成并维护 人员/设备/视频/飞机/地点/维修任务/问题/时间 的关系模型文档；
    * Flights / Routine Tasks 业务字段基于真实接口证据完成
      `AVAILABLE`/`DERIVABLE`/`RESTRICTED`/`NOT_AVAILABLE`/`UNKNOWN` 标注；
    * P3 的 `InspectionRecord` 模型、字段来源三分类、
      `association_method`、业务地点/设备地点分离、问题记录、CHA 授权
      边界、审计状态已作为正式验收方向登记；
    * 不得把 `DERIVED` 显示为 `CONFIRMED`，不得无证据自动生成业务关系。

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
* 已实现并测试告警专题标签（`/api/v2/dashboard/alarms` + raw code 分布）；
* 已实现并测试设备/媒体按 group_id 的分组维度（service + 页面）；
* 已实现并测试非生产 dev store 工厂与 main 接线
  （`app/services/store_factory.py` + `StoreViewEventSink`）；
* 已实现并测试 `InspectionIngestor` 摄入接缝
  （`app/services/ingestion.py`，设备/媒体/告警三类）；
* 已实现并测试数据质量诊断（service + API + “数据质量”标签）；
* 已实现并测试摄入调度编排（`app/services/ingestion_scheduler.py`）；
* 已实现并测试受治理阈值判定（config 解析 + media long_no_upload +
  location stale，`as_of` 可注入）；
* 已实现并测试 AEE 采集器（`app/data/aee_collector.py`，fake adapter 可测）
  与调度协议升级（`CollectedSource` + `ScheduledIngestion`）；
* 已完成 Legacy media/business-reference heuristic code audit，并将 active
  routine-task candidate 与 dormant flight code 明确区分；
* `2026-08-16` 已在授权 AEE 会话下完成 P0 数据能力 live 取证：
  * `DevOnlineList`：`error=200`、1696 行、status 0/1 双值、transition 行、
    `id` 唯一、`time` 非空业务本地时间；
  * `RecordFileList`：`error=200`、711 行、55 字段 schema、`fType`
    1/2/3=image/audio/video、`fileLen`=字节、`duration`=秒、`id` 全局唯一；
  * `AlarmList`：`error=200`、41 行、`alarmType` 205/206、行内无
    `alarmStatus` 字段、`status` 承载告警状态；
  * 认证：数据 API 为 `TOKEN_REQUIRED`（无 token header 时 `error=333`）。
* 已将 live 脱敏样本固化为确定性 fixture（`tests/fixtures/aee_*.json`）与
  `tests/test_aee_live_fixtures.py` 回归测试，覆盖 normalize、error 200/333
  envelope、ONE SHOT INGESTION（source/accepted/invalid/stored 一致 + 幂等）。
* 已按 live 证据修正 Adapter/Collector/Normalizer：
  `_parse_page_result` 使用 `error==200`；`list_record_files` 使用 live
  请求 shape（无 `enterId/keywords`，新增 `timeType/groupWithChild/isDeleted/
  timeSelector`）；`list_alarms` 未选过滤器用 `-1` sentinel 并加 `s5`；
  `AEEInspectionCollector` 强制 `time_type/group_with_child`、`include_alarms`
  显式开关；`status=0 → online=False`（DevOnlineList 最新状态与 status
  event 均已 live 确认）。
* 当前全量 V2 回归 `210 tests PASS`。
* P0 认证收尾：AEE 数据 API **TOKEN-ONLY / 无 Cookie** live 验证通过
  （DevOnlineList 716 行、RecordFileList 347 行均 `error=200`）。
* P1：`MediaFile` 增加 live 验证的 `end_at_source`（`endTime`）字段
  （contract + normalizer + migration + 测试）。
* P1：inspection API 增加显式顶层 `meta` 信封
  （`generated_at` / `freshness` / `quality` / completeness）。
* P1：one-shot ingestion 改为 per-source 独立持久化，单 source 失败以
  `error_code=SOURCE_INGEST_FAILED` 报告、不中断其它 source、重试幂等；
  新增失败安全回归测试。
* 修复 `tests/test_store_sinks.py` 固定窗口 vs “now” 的时间炸弹测试。
* P2：真实 ONE SHOT vertical slice 已执行并通过
  （DevOnlineList 1857 / RecordFileList 805 / AlarmList 46，`error=200`；
  二次摄入不膨胀；设备 1→0→1 与同秒冲突显式标记；媒体 raw 秒/字节对账；
  告警 raw code 保留不丢弃）。
* P2：数据源隔离（collector per-source fail-closed + scheduler 报告
  source status/error_code/completeness）已实现并测试。
* P2：历史覆盖语义（requested/available/completeness）已接入
  service + API + Dashboard（Asia/Shanghai 展示、meta 条显示更新时间/
  覆盖/新鲜度/质量标记）。
* `POSTGRESQL_REHEARSAL_BLOCKED` 已登记（无隔离 PostgreSQL runtime）。
* P2.5：MediaFile identity 审计完成——805 行 `(source_record_id, device_id)`
  全唯一，无 TRUE_DUPLICATE/IDENTITY_COLLISION；修正 P2“803 stored”结论为
  epoch-zero 哨兵窗口过滤；normalizer 已修复
  （`epoch_zero_source_time_ignored`），stored=805=fetched。
* P2.5：DeviceStatusEvent duplicate 审计完成——303 条 metrics 去重均为
  content-identical source redundancy（非真实 transition）；同秒 0/1 冲突
  173/173 保留；新增 `same_time_status_multi_source_dedup` 显式标记。
* P2.5：PostgreSQL 环境探测 → `POSTGRESQL ENVIRONMENT REQUIRED`（BLOCKED），
  最小环境与 rehearsal 流程已写入
  `docs/aee/M4_P2_5_POSTGRESQL_REHEARSAL.md`。
* P2.5：LOW-RATE SCHEDULER SOAK 设计文档
  `docs/aee/M4_P2_5_SCHEDULER_SOAK.md`（未启动，前置条件未全 PASS）。
* P2.5（2026-08-16 授权后执行）：PostgreSQL 真机 rehearsal 全部 PASS——
  migration/schema/index/constraint 检查、ONE SHOT ingest（1857/805/46/1）、
  二次摄入幂等、metrics reconciliation（memory==PG）、backup/restore
  （pg_dump+SHA256+restore 行/指标一致）、rollback（RTO≈0.9s）、
  PG-backed Dashboard API（5 端点 200 + coverage 语义）。
* P2.5：NON-PRODUCTION LOW-RATE SCHEDULER SOAK 执行 PASS（3 次重叠窗口 +
  单源失败注入：无增长、source isolation、恢复、请求量有界）。
* P2.5：新增 `PostgresInspectionStore`
  （`app/data/store/postgres.py`，`InspectionStore` 实现，连接仅来自
  `CHA_PG_*`/`PGPASSWORD` 环境变量）+ `tests/test_postgres_store.py`
  （无 PG 自动 skip，有 rehearsal PG 时真机往返测试）。
* 当前全量 V2 回归 `217 tests PASS`。

## In Progress

* `ACTIVE MILESTONE: M4`。
* 状态：`M4 ACTIVE / P2.5 PASS / P3 FOUNDATION PASS / P3.1 PASS /
  P3.2 INSPECTION USER CANARY PASS — MULTI-PAGE OPERATIONAL DASHBOARD
  CONSOLIDATED — REAL BUSINESS DATA ACCUMULATION ACTIVE`
  （不宣布 M4 COMPLETE）。
* `M4 P3.2 — CONTROLLED PRODUCTION DATA ACTIVATION & CANARY`：
  * SERVER PREPARATION + PG MIGRATION & CONNECTIVITY PASS（migration 到
    cha_m4、CHA→Aliyun PG 真连接、secret、DML smoke、pg_dump/restore）；
  * **ACCESS PATH DIAGNOSTIC PASS**：识别受支持服务器端候选——MCS8 原生
    服务器 `116.198.18.19`（WS 登录 :7711 → REST :7712，token+SessionId），
    RecordFileList / AlarmList 实测 200，设备在线以 GetDevListByGroupId
    替代。
  * **MCS8 NATIVE ADAPTER IMPLEMENTED**：`MCS8ServerAuthProvider` /
    `MCS8DataHTTPClient` / `MCS8ReadOnlyDataAdapter` /
    `MCS8DeviceSnapshotProcessor`（honest polling semantics）/
    `MCS8InspectionCollector` / `scripts/m4_mcs8_oneshot.py`；normalizer
    `source_system` 参数（media/alarm 默认 "aee"，MCS8 用 "mcs8"）；
    store `fetch_latest_device_statuses`。
  * **PRODUCTION MCS8 ONE SHOT PASS（2026-08-17）**：CHA scratch 只读
    live 验证 PASS；Browser/AEE vs MCS8 native 对账一致；生产写入
    cha_m4/inspection：DEVICE 114 / MEDIA 8 / ALARM 2；幂等重跑无膨胀；
    PG 行数与 metrics 对账一致。生产 app/current/nginx/systemd 未改动。
    AEE 前端数据 API 服务端（aee.jdcloud.com）仍受 JFE 493 限制，但
    MCS8 native 通道不受影响。
  * **PRODUCTION LOW-RATE SCHEDULER CANARY（2026-08-18）**：
    * 实现：`MCS8ProductionScheduler`（顺序 DEVICE→MEDIA→ALARM、单 cycle
      in flight、bounded lookback+overlap、server-side MCS8 auth with bounded
      re-login、cycle/state JSON 记录）；`scripts/m4_mcs8_scheduler.py`
      （kill switch + 可配置 cadence/max_cycles）；config 新增 scheduler 项。
    * 第一轮 production canary：**5 个连续 10-min cycles** 有效证据
      （Device same-state no inflation；真实 transition once；Media/Alarm
      idempotent；PG 持续写入；scheduler 内存 ~39MB 稳定；MCS8 auth 稳定）。
    * **PROCESS LIFECYCLE**：原 canary 在 cycle 5 后等待期因 SSH/nohup
      session lifecycle 提前退出（非数据逻辑）。setsid 独立会话复验稳定；
      正式部署需 systemd 进程模型（本轮未修改生产 systemd）。
    * **restart verification PASS**：重启单 cycle 从 PG latest 继续，
      不重新生成 INITIAL_OBSERVATION（114 基线保持），仅真实 transition。
    * **kill switch PASS**：ENABLED=false 立即退出、不采集；历史 PG /
      realtime / Legacy / Dashboard 不受影响。
    * 生产 PG 保留真实数据（device 137 / media 40 / alarm 10）。
    * 状态：`SHORT CANARY PASS`；`LONGER OBSERVATION REQUIRED`（后续
      scheduler 正式运行自然获得）。
  * **PRODUCTION SCHEDULER OPERATIONALIZED（systemd）**：
    `jdair-cha-m4-scheduler.service` enabled+active（Restart=on-failure，
    journald 日志有界脱敏）；managed cycle PASS；restart 从 PG latest 继续；
    kill switch PASS。正式 runtime `/opt/jdair-cha/m4-scheduler`。
  * **PostgreSQL LOCAL BACKUP READY**：daily systemd timer pg_dump +
    SHA256 + 可读验证 + retention。
  * **REMOTE BACKUP OWNER ACTION REQUIRED**：远端备份目标未提供（同盘
    dump 仅 short-term local）。
  * **REMOTE BACKUP PASS（2026-08-18）**：Aliyun local + Tailscale 拉取到
    CHA remote-pg，双主机、SHA256 一致、可读；daily timer 含 off-host。
  * **INSPECTION USER CANARY PASS（2026-08-18）**：inspection-enabled v2
    上线（PG store gate）；AuthorizedUser 边界（enabled/disabled/admin）
    验证；RealtimeViewEvent 生产写入；InspectionRecord
    DRAFT→SUBMITTED→CORRECTED + audit；USER_CONFIRMED/MANUAL_ENTRY；
    query/metrics/CSV/XLSX/Dashboard 均 PASS。真实业务数据积累中。
  * **MULTI-PAGE OPERATIONAL DASHBOARD CONSOLIDATION PASS**：7 标签
    Dashboard（devices/media/realtime/inspections/flights_tasks/alarms/
    data_quality）全部生产 200；新增 flights-tasks 只读域（34 航班/41
    任务真实数据）；inspections 标签复用真实监察记录。271 tests PASS。
* 观察项：远端备份目的地未提供（Canary 完成前必须）。
* 生产数据激活：`AUTHORIZED — CONTROLLED CANARY ONLY`。

## Next

1. `P3.2`：等待项目负责人授权下一 gate：**Inspection 全用户 rollout /
   Dashboard final 使用反馈 / M4 closure**（不得自动进入）。
2. 后续：AuthorizedUser Canary → Inspection Canary → RealtimeViewEvent
   采集 → 备份/监控/kill switch → LONGER OBSERVATION。
3. `P3.2` 观察项：提供远端备份目的地（否则标记 `REMOTE BACKUP DESTINATION
   REQUIRED BEFORE CANARY COMPLETION`）。
3. `P3.2` 待办：服务端 AEE token provider 生命周期/刷新验证（不记录
   Token/Cookie/密码）；live token-expiry 观察。
4. 保持 Production Realtime、Audio、Control、AccountPool 关闭；不开启
   inspection/ingestion 生产开关；不执行生产数据激活。

## Blocked

* 当前无 M4 项目级 blocker（除生产容量决策）。
* 无法从合法 AEE 会话确认的接口和字段必须标记
  `AEE VERIFICATION REQUIRED` 或 `UNKNOWN`，但不阻塞无依赖的 CHA 审计和模型设计。
* production DB migration 在没有 rehearsal、backup、rollback 和明确授权前
  `BLOCKED`。
* `POSTGRESQL_REHEARSAL_BLOCKED` 已解除（2026-08-16 授权隔离 WSL PG 14.23
  rehearsal 全部 PASS）。剩余：
  * 生产 PostgreSQL 容量决策未定前 `BLOCKED`
    （`PRODUCTION POSTGRESQL CAPACITY DECISION REQUIRED`）；
  * 生产 DB migration / 生产 scheduler / 生产 ACL / 生产 InspectionRecord
    在容量决策与后续授权落实前 `BLOCKED`；
  * 服务端 AEE token provider 生命周期/刷新仍 `AEE VERIFICATION REQUIRED`
    （浏览器侧 TOKEN-ONLY 已 live 确认）；
* 正式 AEE 数据 Adapter 的**服务端** Token provider、生命周期和刷新策略在
  形成合法服务端证据前 `BLOCKED`。浏览器 live 证据已确认数据 API 为
  `TOKEN_REQUIRED` 且 **TOKEN-ONLY / 无 Cookie 可返回数据**（`error=200`）；
  只读 HTTP transport 和无网络 normalizer 不受此阻塞；不得猜测 Bearer
  header、不得让浏览器长期持有 AEE 凭据、不得记录 Token/Cookie/密码。
* media-to-flight/task 自动关系和 coverage rate 在缺少 AMRO 脱敏字段样例、
  stable identity/time code map、分页完整性和已确认正负样本前 `BLOCKED`。
  该方向已降级为 `P2`，不阻塞 P0/P1 和 PostgreSQL contract 工作。

## AEE Verification Required

* AEE 设备运行字段：
  `last_online`、`last_offline`、`last_seen`、login/startup time、network state、
  battery、media availability、device model。`DevOnlineList` 的 `status`
  0/1 已 live 确认（transition 行）；`last_online/last_offline` 仍需要
  ordering/retention 边界确认后才能导出。
* `/api/v1/DevOnlineList`：
  raw response（1696 行、`error=200`、status 0/1、`id` 唯一、业务本地时间）
  已 live 确认；剩余：完整非 0/1 status map、长窗口 ordering/duplicate、
  retention 边界和 query-boundary 行为。
* AEE 文件剩余语义：
  stable ID scope（711 行窗口内全局唯一已 live 确认）、完整
  `source`/`upLoadStatus`/`lType` code map、storage/channel，以及按用户/
  组织查询的权限边界。
* AEE 用户使用数据：
  login/logout、session、last active、访问设备、Realtime 监察记录和观看时长。
* AEE `/api/v1/*` 数据 API 认证边界：
  custom `token` header 已 live 确认（无 header → `error=333`，
  `TOKEN_REQUIRED`），且 **TOKEN-ONLY / 无 Cookie 已 live 验证**
  （DevOnlineList 716 行、RecordFileList 347 行均 `error=200`）；剩余：
  服务端 token provider、是否与 Realtime access token 完全同源、有效期、
  刷新方式、服务端最小暴露方案和 401/错误模型。只记录脱敏结论，不记录
  Cookie、Authorization、密码或可复用 Token。
* AEE 告警剩余语义：
  `alarmType` 205/206 与 `status` 字段承载已 live 确认；剩余：完整
  alarm/status/deal code map、level、lifecycle、删除语义、retention、
  pagination、handler/description 权限边界。
* 对每个未知项必须记录所需页面、用户权限、HTTP/WebSocket/SDK 证据、刷新频率和
  敏感等级；不得猜测。
* `WXB358` compatibility 调查仍为 `NON-BLOCKING / PAUSED`，不属于 M4 数据主线。
