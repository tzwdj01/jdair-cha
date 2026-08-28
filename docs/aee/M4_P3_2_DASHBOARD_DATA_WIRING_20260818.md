# M4 P3.2 — Production Dashboard Data Wiring Verification

Date: `2026-08-18`

Status: `Production Dashboard Data Wiring = PASS`

## Purpose

验证生产 V2 inspection/data-center API 已正式接入 Aliyun production
PostgreSQL，且 `PostgreSQL row → service → API → Dashboard` 逐项对账一致，
向 AuthorizedUser Canary 展示真实 production 数据。本轮仅数据接线/必要
修复，无 Dashboard 视觉大改。

## 接线配置（生产）

* v2 release：`20260818030705-m4-dashboard-consolidated`（active）
* `CHA_V2_FEATURE_INSPECTION_V2=true`
* `CHA_V2_INSPECTION_STORE_PG_ENABLED=true`（接线 Aliyun `cha_m4` /
  `inspection`，PostgresInspectionStore + PostgresInspectionRecordStore）
* v2 venv：psycopg2 + openpyxl

## 逐域对账（2026-08-18 生产实测）

### devices

| 层 | 值 |
| --- | --- |
| PG | total=188（114 initial + 74 cha_observed_transition），在线 14 / 离线 100 |
| API | current_online=14 / offline=100 / unknown=0；uptime.devices=114；coverage=PARTIAL（30 请求/2 可用，2026-08-17~18） |
| Dashboard | /dashboard/devices 200；模板 renderDevices 读取 current_online/offline/latest_by_device/uptime.devices |

### media

| 层 | 值 |
| --- | --- |
| PG | 74 条（video 71）；duration 合计 25817s；size 合计 16056890614 bytes |
| API | fetched=74、13 devices、coverage=PARTIAL；WXB301 total=18 video=18 dur=9482 bytes=5094682354 |
| Dashboard | /dashboard/media 200；renderMedia 读取 media.devices / long_no_upload |

### alarms

| 层 | 值 |
| --- | --- |
| PG | 27 条（alarm_type 205×25、206×2） |
| API | alarm_count=27、type_counts=[[205,25],[206,2]]、coverage=PARTIAL |
| Dashboard | /dashboard/alarms 200；renderAlarms 读取 aggregation |

### realtime（RealtimeViewEvent）

| 层 | 值 |
| --- | --- |
| PG | 2 条（stream 5a628… 等，username lijian.1023，result=cancelled） |
| API | aggregation.event_count=2、devices=[WXB313 view_count=2 played=0]、coverage=PARTIAL |
| Dashboard | /dashboard/realtime 200；renderRealtime 读取 aggregation + runtime |

### data-quality

| 层 | 值 |
| --- | --- |
| PG | device_status 188 / device_location 0 / media 74 / rtview 2 / alarm 27 = 291 |
| API | total_rows=291；各表 row_count 一致 |
| Dashboard | /dashboard/data-quality 200；renderDataQuality 读取 tables |

### inspections（InspectionRecord）

| 层 | 值 |
| --- | --- |
| PG | 4 条（has_issue 2 / no_issue 2 / SUBMITTED 1 / CORRECTED 1） |
| API | list total=4、items=4（aircraft/status/issue 一致）；metrics total=2（SUBMITTED+CORRECTED）、duration=153s、participants=2、issue_found=1/no_issue=1/rate=0.5、coverage=PARTIAL |
| Dashboard | /dashboard/inspections 200；CSV 5 行（header+4）；XLSX 可读 |

### flights_tasks / locations

* flights-tasks：34 航班 / 42 维修任务（Legacy 参考，非自动 matcher）
* locations：0 事件（当前无 GPS，诚实空），/dashboard/locations 200

## Coverage 语义

所有域在 requested=30 天时返回 `completeness=PARTIAL`
（available=2 天，2026-08-17~18），不显示虚假 30-day FULL。
Dashboard meta 条显示 generated_at / coverage / freshness / quality。

## 结论

`Production Dashboard Data Wiring = PASS`：

* 8 域 Dashboard 页面与 8 个数据 API 全部 200；
* PostgreSQL row → service → API → Dashboard 抽样逐项对账一致；
* 设备在线/离线、设备 transition、媒体数量/时长/大小、告警、
  RealtimeViewEvent、InspectionRecord、问题数量均来自真实 production PG；
* 历史覆盖不足显示 PARTIAL。

最终 Dashboard consolidation（视觉/大屏/指标丰富）留待 M4 P4。
