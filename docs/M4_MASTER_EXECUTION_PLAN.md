# M4 Master Execution Plan — CHA Inspection Data Center

Date: `2026-08-18`

Current governance correction: `2026-08-26` (reviewed `2026-08-28`)

Status: `ACTIVE — PHASE 6 DASHBOARD CONSOLIDATION & CANARY HARDENING / CANARY NO-GO`

本文件是 **M4 剩余阶段的单一执行路线图**。它保存详细执行顺序、验收标准、
stop gates、deferred scope 与最终 M4 closure criteria。

`TASK_GOAL.md` 只保留 milestone / current phase / governance status；
详细执行计划以本文件为准，避免把 TASK_GOAL.md 变成巨大执行日志。

> 「统一计划」不等于「一次性无门禁执行全部任务」。生产授权、真实用户
> rollout、最终 M4 closure 仍必须遵守明确 stop gate。

> **Current-status correction (2026-08-26):** M4 is not closed. Phase 6 is
> local Dashboard/Canary hardening only; an AuthorizedUser Dashboard Canary
> remains NO-GO until access control, connection pooling, readiness, package and
> security-history gates pass. `docs/aee/M4_COMPLETION_REPORT_20260818.md` is
> preserved as historical evidence, not current closure authority.

---

## 1. 已完成基线（不得重复建设，除非真实故障）

以下能力已经完成并验证，后续除真实故障外不要重复建设：

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| M0 | baseline / security governance | PASS |
| M1 | V2 engineering foundation | PASS |
| M2 | initial situation / data dashboard | PASS |
| M3 | realtime foundation | CLOSED |
| M4 P0/P1 | data discovery, normalization, historical contracts | PASS |
| M4 P2/P2.5 | live data validation, PostgreSQL rehearsal, idempotency, backup/restore rehearsal | PASS |
| M4 P3/P3.1 | AuthorizedUser model, InspectionRecord, Realtime linkage, Flights/Routine live evidence, candidate/manual confirmation, audit, query, Inspection Dashboard, CSV/XLSX, PG rehearsal | PASS |
| M4 P3.2 | Aliyun production PostgreSQL, migration 0001/0002, MCS8 native production data path, production ONE SHOT, LOW-RATE scheduler, systemd operationalization | PASS / ACTIVE |

当前生产数据路径：

```text
MCS8 native
  → CHA scheduler (systemd, active)
  → Aliyun PostgreSQL (cha_m4 / inspection, active)
```

生产数据积累：`ACTIVE`（2026-08-18：device 214 / media 133 / alarm 28 /
realtime_view_events 2 / inspection_records 4 / authorized_users 2）。

---

## 2. 剩余业务主线

后续只能围绕业务对象形成完整链路，不得重新把 M4 做成媒体平台或基础设施
项目：

```text
人员 + 设备 + 视频 + 飞机 + 航班 + 地点/站点 + 维修任务 + 问题 + 时间
  → 数据采集
  → 监察行为 (RealtimeViewEvent)
  → InspectionRecord
  → 查询
  → Dashboard
  → Export
  → Audit
  → 业务分析
```

---

## 3. PHASE 1 — Production Backup Closure

目标：解除 `REMOTE BACKUP OWNER ACTION REQUIRED`。

方案（低成本）：Aliyun PostgreSQL → daily pg_dump → Tailscale →
JDCloud CHA off-host backup。

要求：

* Aliyun local backup：14 天 retention
* JDCloud off-host copy：7–14 天 retention
* SHA256 一致、`pg_restore -l` 可读、权限受控、不含 secret、防无限增长
* 不引入复杂 PITR / backup platform

停止条件（空间/权限不适合时）：`OWNER ACTION REQUIRED — REMOTE BACKUP DESTINATION`，
不自行购买云资源。

完成标志：`REMOTE BACKUP PASS`。

**当前状态：`PASS`（已实现 Tailscale off-host copy；Aliyun local + JDCloud
remote-pg 双主机、SHA256 一致、可读、retention 14 天）。**

---

## 4. PHASE 2 — Production Dashboard Data Wiring

目标：将运行中的 production V2 正式接入 Aliyun production PostgreSQL。

数据 API：

* `/api/v2/inspection/devices`
* `/api/v2/inspection/media`
* `/api/v2/inspection/realtime`
* `/api/v2/inspection/alarms`
* `/api/v2/inspection/data-quality`
* `/api/v2/inspections`
* `/api/v2/inspections/metrics`

对应页面：`/dashboard/devices|media|realtime|alarms|data-quality|inspections`。

原则：接真实数据、验证业务正确性；不做最终视觉重构 / 新前端框架 /
虚构 KPI / 大量新图表 / 总览大屏重新设计。

逐项验证 `PG → repository → service → API → Dashboard`，至少对账：

* device count / online / offline / observed transitions
* media count / duration / size
* alarm count / types
* RealtimeViewEvent / InspectionRecord / issue count

coverage 不足显示 `PARTIAL`，不得伪造 FULL。

完成标志：`PRODUCTION DASHBOARD DATA WIRING PASS`。

**当前状态：`PASS`（8 域 Dashboard + 7 inspection API + CSV/XLSX 全 200；
PG row→API→Dashboard 逐项对账一致；coverage 诚实 PARTIAL）。**

---

## 5. PHASE 3 — Inspection User Canary

目标：让少量真实监察用户产生真实业务记录（初始 1–3 个明确指定 CHA Canary
账号）。

停止条件（owner 未提供账号）：`OWNER ACTION REQUIRED — PROVIDE INITIAL CHA
CANARY ACCOUNTS`；不得自动把全部 AEE 用户加入 CHA。

CHA Authorization 边界：

* enabled AuthorizedUser → PASS
* valid AEE account not in allowlist → 403
* disabled user → 403
* admin：list / add / enable / disable（全部 audit）
* 只需 admin + inspector，不扩展复杂 RBAC

真实监察流程（Canary 用户完成）：

```text
CHA login → select device → open realtime → RealtimeViewEvent
  → 点击“记录监察结果” → InspectionRecord draft
  → Aircraft → Flight → Station → Routine Task → Issue
  → Submit → Query → Dashboard → Export
```

完成标志：出现至少少量真实 RealtimeViewEvent + InspectionRecord，并证明
人员/设备/视频/飞机/航班/站点/维修任务/问题/时间业务关系真实形成。

状态：`INSPECTION USER CANARY PASS — REAL BUSINESS DATA ACCUMULATION ACTIVE`。

**当前状态：`PASS`（指定 Canary 账号见 TASK_GOAL 授权记录；rtview 2、
inspection 4；USER_CONFIRMED / MANUAL_ENTRY；DRAFT→SUBMITTED→CORRECTED +
audit；query/dashboard/export 全部验证）。**

---

## 6. PHASE 4 — Real Business Observation

自然观察阶段。不允许 Codex 人工等待数小时/数天、反复 sleep/poll cycle。
生产 scheduler 与真实业务正常运行即可；之后通过已有 logs、scheduler
state、PostgreSQL、Inspection records 读取自然积累的数据。

重点回答业务问题：

* 设备：哪些长期离线？哪些频繁上下线？
* Media：哪些设备无上传？上传数量/时长/大小趋势？
* Realtime：哪些账号实际监察？次数/时长？
* Inspection：真实记录数、涉及设备/飞机/航班/站点/维修任务；
  USER_CONFIRMED 比例 vs MANUAL_ENTRY 比例
* Issue：问题数、类型、等级、集中设备/飞机/站点/任务
* Data Quality：哪些字段仍 UNKNOWN / PARTIAL

**当前状态：`OBSERVATION ACTIVE`（生产 scheduler 与业务自然运行；数据持续
积累，无需人工等待）。**

观察快照（2026-08-18 12:34，读取自然积累，未人工等待）：

* scheduler：active，62 cycles，RSS ~26MB，运行 10.5h，无异常退出。
* PG：device 216 / media 137 / alarm 28 / realtime_view_events 2 /
  inspection_records 4；DB ~10MB，1 连接。
* CHA：Mem 748Mi/1.9Gi、load 0.06。
* off-host backup：今日 12:33 手动触发一次（timer 今日启用、首次 daily
  触发顺延至明日 00:00）；local + remote-pg 双份，SHA256 与 Aliyun 源一致
  （`bfe0…ed6`），`pg_restore -l` 可读。异地备份链路持续有效。
* 本轮观察无新增真实产品问题需修复（candidates API 已于上轮修复）。

补充（2026-08-18 12:40）：真实工作流冒烟通过——realtime 页
「记录监察结果」→ 创建 draft（自动带 device/streamId/timing）→
填写 aircraft/flight/station/task → candidates 参考可用 →
submit/correct 全链路在生产可用。测试记录已清理，生产保留 4 条真实
Canary 记录，未污染业务数据。备份链路今日 12:33 验证有效。

观察快照（2026-08-18 12:45，读取自然积累，未人工等待）：

* scheduler：active，63 cycles，**63/63 all_successful=True，0 失败**，
  NRestarts=0，PID 12273 运行 10.7h，RSS ~25MB（稳定，无持续增长）。
  节奏验证：每 ~10 分钟一个 cycle（61→04:15Z、62→04:25Z、63→04:35Z）。
  每 cycle 数据行为：DEVICE fetch 114 → stored 0-1（幂等，仅真实状态变化
  才入库）；MEDIA fetch 6-9 → stored（新上传文件）；ALARM fetch 0 → stored 0。
* PG：device 217（+1 真实 transition）/ media 137 / alarm 28 /
  realtime_view_events 2 / inspection_records 4 / authorized_users 2；
  DB ~10MB，1 连接。
* Media 按日累计：2026-08-18 = 119 文件 / ~23.5GB；2026-08-17 = 18 文件 /
  ~3.0GB。最新 3 条（12:36）：WXB312 18.6MB/36s、WXB316 322.9MB/600s、
  WXB364 3.1MB/7s。
* Alarm：最新 10:33（WXB301 type=2）；WXB356 type=205 于 05:50/06:00。
* 设备最新快照：1 台设备真实掉线（transition 入库）。
* CHA 资源：Mem 745Mi/1.9Gi、disk 25G/39G（68%）、swap 4G。
* Aliyun PG：Mem 306Mi/1.6Gi、disk 5.7G/40G（16%）、load 0.00；
  listener 仅 127.0.0.1:5432 + Aliyun Tailscale 内网 IP:5432，**公网 5432
  未监听**（加固保持）。
* V2 health：`/api/v2/health`、`/live`、`/ready` 均 200；v2 于 12:13 本地
  时间重启（uptime ~31min），重启后全部健康检查 200，无回归。
* 日志说明：scheduler 的 cycle 记录写入 state JSON（63 cycles 全量可查），
  journald 仅记录 service 启停（02:06 启动后无逐 cycle 日志）；进程存活、
  state 持续更新、PG 持续写入，非缺陷。
* 本轮观察无新增真实产品问题需修复。

---

## 7. PHASE 5 — Workflow Refinement

只能根据真实 Canary / production 使用发现的问题修改，例如：

* 候选难选 → 优化 candidate UI
* 表单太长 → 简化
* 字段名称难理解 → 改展示
* 查询不好找 → 改筛选
* 真实数据缺字段 → 调整 adapter

没有真实证据的问题：不开发。禁止 speculative feature development。

**当前状态（2026-08-18）：`ACTIVE — 按真实使用问题修复`。**

真实使用发现并已修复：

* **候选参考 API 缺失**：Canary 时 `/api/v2/inspections/candidates` 返回
  404（监察表单缺候选供 USER_CONFIRMED 选择）。已将
  `InspectionBusinessCandidateService`（已有、非 matcher）接线到
  `GET /api/v2/inspections/candidates`：按 inspection 时间 / 可选 aircraft /
  station 返回有界参考候选（aircraft/flight/station/routine task/time），
  `association_method=SOURCE_DIRECT`（仅参考，不自动确认）。生产验证：
  200，43 条真实候选（航班/任务），8 域 Dashboard 无回归。测试 +3。

* **设备定位（locations）数据持久化缺失**：`/dashboard/locations` 一直
  诚实为空（此前结论「当前无 GPS」）。只读探测证明该结论有误——
  MCS8 `GetDevListByGroupId` 设备快照**本身就携带当前定位投影**
  （`nJingDu`/`nWeiDu`/`gpsTime`/`ucMapType`，114 台设备全部有 GPS 字段），
  但 scheduler 只持久化了状态、丢弃了定位。已修复：
  - 新增 `normalize_mcs8_device_snapshot_locations`：从既有 DEVICE 快照行
    产出 `DeviceLocationEvent`（`location_source="mcs8_device_snapshot"`，
    坐标校验 + 0,0 哨兵剔除 + 无 gpsTime 剔除，旗标
    `coordinate_system_unverified`/`location_data_restricted`/...）。
  - collector `collect_device_snapshot` 内作为既有来源的**副作用**持久化
    定位（不新增上游调用、不新增 scheduler source、频率不变）；
    `device_status` 源 quality_flags 暴露
    `device_locations_stored=N` / `device_locations_invalid=N`。
  - 幂等：唯一键（source_system, location_source, device_id, gps_occurred_at,
    lat, lng），位置不变不增行。
  - 健壮性修复：`_optional_source_time` 捕获 `OverflowError`——
    真实 MCS8 有 **22/114 台设备 `gpsTime='0001-01-01 00:00:00'`** 哨兵值，
    原实现会崩整个 cycle。
  - 真实数据验证：92 台设备产出有效定位事件（22 台哨兵正确剔除），
    坐标合理、gpsTime 2023-07→2026-08（含陈旧，诚实保留）。
  - 测试 +6（normalization 4 + scheduler 2），全量 280 tests PASS
    （2 PG skip）。
  - **已部署（2026-08-18 13:26 CST，owner 授权）**：
    `LOCATION PRODUCTION DEPLOYMENT PASS`
    - backup：`/opt/jdair-cha/m4-scheduler/backups/location-20260818132552`
      （+ 首次尝试 20260818132110，可回滚）；
    - 3 文件上传 + chown + `py_compile` OK；scheduler 重启 active，
      NRestarts=0；
    - 新进程首个 cycle：`device_locations_stored=92` /
      `device_locations_invalid=22`（与 dry-run 完全一致）；
    - PG `device_location_events`：96 行 / 92 台设备；sentinel 过滤 0 行
      （无 year<2000）；gps 年份 2026=86 / 2025=6 / 2024=3 / 2023=1；
    - `/api/v2/inspection/locations?days=3`：50 事件 / 46 设备 / FULL；
      `/dashboard/locations` 200；
    - 资源：MemoryCurrent ~22MB，disk 69%，服务正常。

---

## 8. PHASE 6 — M4 P4 Dashboard Consolidation

**Current status (governance correction effective 2026-08-26):**
`IN PROGRESS / DASHBOARD CANARY NO-GO`. This phase is presently restricted to
local hardening: unified CHA-login + AuthorizedUser enforcement, bounded
PostgreSQL reuse, isolated concurrent overview aggregation, honest readiness,
zero-failure tests, package verification and address/history audit. No
production deployment or feature-flag change is implied.

真实生产数据积累后进入 `M4 P4 — DASHBOARD CONSOLIDATION & OPERATIONAL
ANALYTICS`（M4 最终核心产品阶段）。

最终页面：

* `/dashboard` 监察总览
* `/dashboard/devices` 设备运行
* `/dashboard/media` 视频上传
* `/dashboard/realtime` 实时监察使用
* `/dashboard/inspections` 监察记录
* `/dashboard/alarms` 告警异常
* `/dashboard/tasks` 飞机 / 航班 / Routine Tasks
* `/dashboard/map` 站点 / 设备位置
* `/dashboard/data-quality` 数据质量

Dashboard 产品原则：

* 总览页回答「今天哪里值得关注？」
* 专题页回答「为什么？」
* Inspection 页面回答「监察了什么，结论是什么？」
* 不做纯视觉大屏；所有 KPI 来自真实 production data，不模拟/猜测/虚构。

PHASE 6 就绪证据（2026-08-18，真实 production 数据，供 owner 决策）：

* Devices：218 events / 114 台设备；最新快照 9 在线 / 105 离线；有真实
  transition（WXB312 9 次、FXB102 7 次等）。
* Media：138 文件 / 19 台设备上传 / ~27GB（2 天）；08-18 = 120 文件 /
  ~24GB。
* Realtime：2 条 cancelled（空闲自动化会话）；**尚无 played 事件**——
  需一次真实浏览器播放会话才能产生首帧/时长证据（owner 操作）。
* Inspections：4 条真实 Canary 记录（2 DRAFT / 1 SUBMITTED / 1 CORRECTED），
  含 aircraft/flight/station/task/issue，审计链完整。
* Alarms：28 条（type 205/206/2），code map 仍 PARTIAL。
* Flights/Tasks：经 legacy 带 cookie 可取（candidates 曾返回 43 条真实
  候选）；未授权不自动匹配。
* Locations：**修复待部署**（见 PHASE 5 + deploy runbook），部署后预期
  ~92 台设备有效定位。
* Coverage：目前仅 ~2 天（08-17→08-18），30 天窗口 PARTIAL。

进入 PHASE 6 的 stop gate 保持：**owner 明确批准**（含 locations 部署授权）
后执行。

核心指标：

* Devices：online / offline / transition / uptime / last seen
* Media：upload count / video count / duration / size / last upload /
  non-upload anomaly / trend
* Realtime：active/total inspection users / view count / view duration /
  device ranking
* Inspection：count / duration / inspectors / aircraft / flights / tasks /
  issue count / rate / type / level / rankings / trend
* Alarm：count / types / devices / trend
* Business：aircraft / flight / station / routine task
* Location：business station vs device GPS（保持分离，允许展示两者；
  无正式规则前不得自动判定 location anomaly）
* Data Quality：coverage / freshness / UNKNOWN / PARTIAL / source health

---

## 9. PHASE 7 — M4 Final Acceptance

**Current status:** `NOT APPROVED / NOT ALLOWED`. Phase 7 and any `M4 CLOSED`
claim remain blocked until Phase 6 is accepted and a separate owner authorization
opens final acceptance.

M4 只有同时满足以下条件才允许关闭（`M4 CLOSED`）：

1. MCS8 → PostgreSQL scheduler production ACTIVE
2. production PostgreSQL off-host backup PASS
3. production Dashboard 使用真实 PG 数据
4. AuthorizedUser enforcement 生产有效
5. 真实 RealtimeViewEvent 已产生
6. 真实 InspectionRecord 已产生
7. Aircraft / Flight / Station / Routine Task 关联实际可用
8. Issue workflow 实际可用
9. Query 实际可用
10. CSV / XLSX 实际可用
11. Audit 实际可用
12. 多页面 Dashboard 使用真实生产数据
13. 数据质量 / coverage 表达诚实
14. resource usage acceptable
15. no critical security blocker

完成后输出 `M4 CLOSED`，并形成 M4 Closure Report（见下）。

---

## 10. M4 Closure Report（业务价值重点）

* A. 当前有多少设备数据
* B. 自动积累了多少历史
* C. Media 上传数据情况
* D. 真实用户监察情况
* E. InspectionRecord 情况
* F. Aircraft / Flight / Station / Task 关联情况
* G. Issue 数据
* H. Dashboard 页面
* I. Query / Export
* J. Backup
* K. Data quality
* L. Security
* M. Production resource usage
* N. Remaining known limitations
* O. M5 recommendation

---

## 11. Deferred / 禁止偏航

以下不属于当前 M4 主线，除非真实生产业务数据或用户反馈证明其成为
blocker，否则一律 DEFER：

```text
32 streams
complex AccountPool
FFmpeg
transcoding
self-hosted SFU
video copy/storage
PTZ
Talkback
automatic Flight/Routine matcher
Kafka
Celery
new monitoring platform
complex IAM
speculative AI features
```

---

## 12. 长时间任务与自动推进规则

长时间任务：禁止 sleep 1 hour / 人工等待多个 scheduler cycle / 等待一天 /
持续轮询生产状态。需要时间积累的证据标记 `OBSERVATION ACTIVE`，让正式
production service 自然运行，下一次任务再读取历史结果。

自动推进：允许从普通开发任务 → 测试 → rehearsal → 非破坏性生产只读验证
自动推进。

以下必须 STOP：

* A. 需要项目负责人提供真实 CHA 用户账号
* B. 需要购买 / 新增云资源
* C. destructive production change
* D. full user rollout
* E. Legacy retirement
* F. M4 CLOSED
* G. M5 start

达到 STOP gate：输出 `OWNER ACTION REQUIRED`，不得继续。

---

## 13. 当前执行顺序

1. Remote Backup Closure ✅ PASS
2. Production Dashboard Data Wiring ✅ PASS (historical wiring evidence)
3. Inspection User Canary ✅ PASS (historical limited-canary evidence)
4. Real Business Observation remains active naturally; do not manufacture long
   polling runs.
5. **→ PHASE 6 Dashboard Consolidation & Canary Hardening — IN PROGRESS / NO-GO**
6. → AuthorizedUser Dashboard Canary only after Phase 6 local acceptance and a
   separate owner deployment authorization.
7. → M4 Final Acceptance / Closure only after a later owner authorization.

**Current phase: PHASE 6 — Dashboard Consolidation & Canary Hardening.**

**Current stop gate: no production deployment or M4 closure.**

**Current next action: complete local access, pool, overview, readiness,
package and security-history gates described in the 2026-08-26 governance
correction.**
