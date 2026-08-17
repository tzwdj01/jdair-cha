# M4 Completion Report — CHA Inspection Data Center

Date: `2026-08-18`

Status: `M4 COMPLETE / VERIFIED — INSPECTION DATA CENTER & REAL BUSINESS DATA ACCUMULATION ACTIVE`

## Summary

M4（CHA Inspection Data Center & AEE Data Capability Integration）已达到全部
Done Criteria。生产环境已从 MCS8 → PostgreSQL 数据管道转为真实监察业务
工作流：受控授权用户监察、RealtimeViewEvent / InspectionRecord 持久化、
生产 PostgreSQL 驱动的多页面操作 Dashboard 与导出、真实业务数据持续积累。

## M4 Done Criteria 1–14 — 逐项证据

1. **AEE 数据能力清单 + 合法取证**：
   `docs/aee/AEE_CAPABILITY_MATRIX.md`、`AEE_INTERFACE_CATALOG.md`、
   `AEE_FIELD_CATALOG.md`；P0 授权 AEE 会话 live 取证（DevOnlineList /
   RecordFileList / AlarmList，`error=200`）。
2. **CHA 数据能力清单 + Legacy 依赖审计**：
   `docs/data/CURRENT_CHA_DATA_CAPABILITIES.md`、
   `LEGACY_MEDIA_BUSINESS_REFERENCE_AUDIT.md`。
3. **字段分类**：`docs/data/DATA_AVAILABILITY_MATRIX.md`
   （AVAILABLE / DERIVABLE / RESTRICTED / NOT_AVAILABLE / UNKNOWN）。
4. **历史沉淀来源/时间/保留**：`docs/data/HISTORICAL_DATA_MODEL.md`。
5. **Dashboard 指标来源/刷新/新鲜度/异常**：
   `docs/data/DASHBOARD_INFORMATION_ARCHITECTURE.md`；所有 Dashboard API
   携带 meta 信封（generated_at / coverage / freshness / quality）。
6. **历史模型建立并验证**：5 张历史表（device_status / device_location /
   media_files / realtime_view_events / alarm_events）；不持久化 WebRTC
   runtime 临时状态。
7. **PostgreSQL migration rehearsal/backup/rollback**：隔离 rehearsal PASS
   （migration/ingest/idempotency/metrics/backup-restore/rollback）+ 生产
   迁移（cha_m4/inspection）+ 异地备份（Tailscale off-host copy，SHA256
   一致、双主机）。
8. **第一版多页面 Dashboard**：8 域生产 200
   （devices/media/realtime/inspections/flights_tasks/locations/alarms/
   data_quality）。
9. **Drill-down**：总览 → 设备 → timeline（生产验证：WXB313 timeline
   status_event_count=1 / media_file_count=3）。
10. **自动化/health/数据质量/回归**：271 tests PASS；后端 health 200；
    data-quality 域展示真实覆盖/新鲜度/质量 flag。
11. **Remaining Data Gaps / AEE VERIFICATION REQUIRED**：明确登记（服务端
    AEE token 生命周期、alarm/status code map 等）。
12. **无 secrets / 虚假指标 / 无来源字段 / 未批准媒体架构升级**：敏感扫描
    clean；未引入 FFmpeg/SFU/transcoding/自建媒体。
13. **M4 Completion Report**：本文档。
14. **CHA 独有监察业务数据模型与记录工作流**：InspectionRecord（含
    association_method=SOURCE_DIRECT/USER_CONFIRMED/MANUAL_ENTRY）、
    Flights/Routine Tasks 业务字段、人员/设备/飞机/地点/维修任务/问题/
    时间关系模型（HISTORICAL_DATA_MODEL 第 9/12 节）、CHA 授权边界
    （enabled/disabled/admin）、审计（inspection_audit_events /
    authorized_user_audit_events）；DERIVED 不显示为 CONFIRMED、无自动
    matcher。

## 生产交付与证据（2026-08-18）

* **数据管道**：MCS8 native adapter（auth/http/adapter/collector）→
  生产 scheduler（systemd `jdair-cha-m4-scheduler.service`，RSS ~36MB，
  持续正常，kill switch PASS）。
* **PostgreSQL**：Aliyun `cha_m4` / `inspection`，migration 0001+0002；
  device 146 / media 50 / alarm 15 / realtime_view_events 2 /
  inspection_records 4 / authorized_users 2；DB ~9.9MB。
* **授权**：AuthorizedUser 边界验证（enabled→进入；disabled→403；
  inspector 访问 admin API→403；admin 管理 + audit）。
* **监察业务**：RealtimeViewEvent 生产写入；InspectionRecord
  DRAFT→SUBMITTED→CORRECTED + audit；USER_CONFIRMED / MANUAL_ENTRY；
  has_issue true/false；飞机/航班/站点/任务上下文。
* **Dashboard / Export**：8 域 Dashboard 与数据 API 全 200；CSV/XLSX 导出
  （表头/中文正确，无敏感信息）。
* **备份**：本地 + 异地（Tailscale off-host copy）SHA256 一致、可读。

## Git

* branch：`codex/m4-inspection-data-center-20260815`
* HEAD：`ae62b3a`（local == remote，working tree clean）
* 关键提交：MCS8 adapter / scheduler / operationalization / remote backup /
  Inspection User Canary / Dashboard consolidation（8 域）。

## 非目标（未做，等授权）

M5（Device Control / 全用户 Inspection rollout / PTZ / Talkback /
录像 / 抓拍）不得自动开始。Production Realtime / Audio / Control /
AccountPool 保持关闭。远端备份已落实（Tailscale off-host）。
