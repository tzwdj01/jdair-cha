# M4 PHASE 6 — AEE Dashboard Reference Matrix

Date: `2026-08-18`

Status: `REFERENCE IMPLEMENTATION STUDY`（只读研究，不做 CHA 运行时依赖）

依据：

* `docs/codex/AEE_REFERENCE_IMPLEMENTATION.md`
* `docs/aee/AEE_CAPABILITY_MATRIX.md`
* `docs/aee/AEE_INTERFACE_CATALOG.md`
* `docs/aee/AEE_FIELD_CATALOG.md`
* `docs/aee/AEE_VS_CHA_WXB358_20260814.md`

证据等级沿用 AEE_CAPABILITY_MATRIX：

* `LIVE VERIFIED` = 授权 AEE 会话实测
* `STATIC VERIFIED` = 静态资源/SDK 实测
* `CHA LEGACY VERIFIED` = CHA Legacy 已调用
* `AEE VERIFICATION REQUIRED` = 尚无合法证据

## 1. 结论摘要

* AEE 的「Dashboard」大量指标是**页面在前端用原始行聚合计算**的
  （在线时长、文件统计、告警统计），不是独立聚合 API。CHA 不应复制
  该前端计算逻辑，而应在后端用已采集的规范化行独立、确定性地计算。
* AEE 页面布局/路由/私有 glue 属 Class D，**不复制**。
* CHA 独有业务关系（RealtimeViewEvent / InspectionRecord / Issue /
  AuthorizedUser）在 AEE 中不存在，是 CHA Dashboard 的差异化价值。

## 2. 参考矩阵

| AEE_FEATURE | SOURCE FIELD/API | CHA CURRENT EQUIVALENT | CAN REUSE DATA | NEEDS CHA CALCULATION | NOT AVAILABLE | DO NOT COPY |
| --- | --- | --- | --- | --- | --- | --- |
| 设备树/在线状态 | `/api/v1/ext/DevTree`；`online/status`（LIVE VERIFIED） | `device_status_events`（MCS8 `GetDevListByGroupId` 快照，114 台） | 是（同一设备域） | 状态快照→初始观测/轮询变化（CHA 已实现） | — | 不把管理在线状态当作历史时长 |
| 在线/离线统计 | 设备树 `online` 计数（LIVE VERIFIED） | Overview `devices.current_online/offline`（PG） | 是 | 快照最新态计数（CHA 已实现） | — | 不把快照当在线历史 |
| 在线时长/上下线历史 | `/api/v1/DevOnlineList` transition rows；页面 `Hour/Min` 计算 | `device_status_events` + `aggregate_device_uptime`（range-clipped） | 是 | CHA 自算 range-clipped 区间（已验证页面 32h vs 12h 不一致，不复制页面算法） | — | 页面边界算法（扩展到浏览器当前时间） |
| 设备在线率 | 页面由 transition 行计算 | Overview uptime `online_seconds/window` | 是 | CHA 自算 | — | 不复制 `Hour/Min` 列 |
| GPS 新鲜度 | 设备树 `gpsTime`（LIVE VERIFIED） | `device_location_events.gps_occurred_at`（部署后真实） | 是 | 用 gpsTime 作新鲜度信号，不作在线证明 | — | 不把 gpsTime 当 transition 时间 |
| 当前定位/地图 | `gpsLng/gpsLat`（PARTIAL）+ Legacy `GetGpsModelList` | `device_location_events` + `/dashboard/locations`（92 台有效） | 是 | 坐标校验/哨兵剔除（CHA 已实现） | — | 不自动判定 location anomaly（无正式规则） |
| 文件统计（数量/时长/大小） | `/api/v1/RecordFileList`；页面按设备/分组聚合 | `media_files` + `aggregate_media_files` + Overview `media` | 是 | 后端规范化行聚合（CHA 已实现；检测截断不静默呈现部分合计） | — | 前端 10,000 行聚合逻辑 |
| 文件趋势 | RecordFileList 时间窗口 | `media.daily_counts` / 按日趋势（CHA 已实现） | 是 | 按日聚合 | — | — |
| 未上传/无记录设备 | 页面对比设备树 vs 文件列表 | `long_no_upload_devices`（阈值未配置时诚实不生成） | 是 | 阈值治理后才生成（CHA 已实现 governed 语义） | — | 无阈值不臆造异常 |
| 告警统计 | `/api/v1/AlarmList`；页面按类型/设备统计 | `alarm_events` + `aggregate_alarm_events` + Overview `alarms` | 是 | code map 未完整前标记 PARTIAL/UNKNOWN（CHA 已实现） | — | 未验证的 alarmType 语义不猜测 |
| 告警处理状态 | `AlarmList.dealStatus/dealUser/dealTime`（LIVE VERIFIED） | `alarm_events` handled 字段；map PARTIAL | 部分 | map 未验证 → `handled_state_unknown` 旗标 | — | — |
| 实时播放 | `mediaMonitor streamType=2` / `openVideo`（LIVE VERIFIED） | M3 realtime（支撑下钻，16 路上限） | 是（Class B） | — | — | — |
| 用户观看历史 | AEE 无合法历史接口（AEE VERIFICATION REQUIRED） | `realtime_view_events`（CHA 自建） | 否（AEE 不提供） | CHA 自建历史（已实现；played 为观察期缺口，诚实显示） | 在 CHA 用 RealtimeViewEvent 补齐 | 不假装 AEE 提供 |
| 监察记录 | AEE 无此业务 | `inspection_records` + Issue + audit | 否 | CHA 独有 | CHA 独有 | 不复制（AEE 无对应） |
| 授权用户 | AEE 权限为账号级 `VIDEOMONITOR` | `authorized_users`（CHA Canary 边界） | 否 | CHA 独有 | CHA 独有 | 不复制（CHA 业务权限） |
| 航班/例行任务 | AEE `TaskList` 等（STATIC/未启用） | Legacy `/api/flights` + `/api/routine-tasks` + candidates（SOURCE_DIRECT 参考） | 部分 | 已存在受支持 Legacy 路径；不自动匹配 | — | 不复制 AEE 隐藏页面/私有路由 |
| Dashboard 布局 | AEE 页面（Class D） | CHA 自建 overview + 8 专题页 | 否 | — | — | 页面私有布局/路由/glue 一律不复制 |

## 3. 对 CHA Overview 的借鉴（只借鉴概念，不复制实现）

* **信息架构**：总览回答「今天哪里值得关注」，专题页回答「为什么」——CHA
  已按此划分（`overview` tab + 8 专题）。
* **指标命名**：使用业务可读中文（设备在线/离线、视频上传、监察、告警），
  与 AEE 概念对齐但为 CHA 自有。
* **图表组织**：metric 卡片 + 明细表 + 覆盖标记；不引入 3D/炫技动画。
* **drill-down**：专题页可下钻设备时间线 / 监察详情（已实现部分）。

## 4. 明确不复制（及原因）

| 项 | 原因 |
| --- | --- |
| AEE 页面私有 token/Cookie/session | 安全边界；CHA 只用受支持的 MCS8 服务端通道 |
| 浏览器端 10,000 行聚合 | 体积大、边界语义未验证；CHA 后端确定性聚合 |
| 在线时长 `Hour/Min` 显示算法 | 与 range-clipped 区间不一致（WXB310 32h vs 12h） |
| 页面私有路由/布局 glue | Class D；CHA 自有 UI |
| 隐藏 Dashboard | 不是 CHA 运行时依赖 |

## 5. 记录结论

* AEE 设备/媒体/告警的**原始数据字段**大多可复用（Class A），但**聚合计算**
  必须在 CHA 后端独立实现（Class C）。
* RealtimeViewEvent / InspectionRecord / Issue / AuthorizedUser 是 CHA 独有
  业务关系，AEE 无对应能力，构成 CHA Dashboard 的差异化价值。
* 未验证的 alarmType/dealStatus/gpsType 等 code map 继续标记 PARTIAL/
  UNKNOWN，不猜测。
