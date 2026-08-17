# M4 P3.2 — Multi-Page Operational Dashboard Consolidation

Date: `2026-08-18`

Status: `PASS — MULTI-PAGE OPERATIONAL DASHBOARD CONSOLIDATED`

## Goal

将生产数据（MCS8 → PostgreSQL 持续积累）与监察业务工作流整合为一个
多页面操作 Dashboard，围绕设备 / 媒体 / 实时监察 / 监察记录 / 航班与
维修任务 / 告警 / 数据质量，全部连接生产 PostgreSQL。

## 8 域 Dashboard（生产 200）

`/api/v2/dashboard/`：

| tab | 域 | 数据 API |
| --- | --- | --- |
| devices | 设备运行 | `/api/v2/inspection/devices` |
| media | 视频上传与文件 | `/api/v2/inspection/media` |
| realtime | 监察使用 | `/api/v2/inspection/realtime` |
| inspections | 监察记录 | `/api/v2/inspections`（authorized） |
| flights_tasks | 航班与维修任务 | `/api/v2/inspection/flights-tasks` |
| locations | 设备定位 | `/api/v2/inspection/locations` |
| alarms | 告警异常 | `/api/v2/inspection/alarms` |
| data_quality | 数据质量 | `/api/v2/inspection/data-quality` |

生产验证：8 个页面全部 200，8 个数据 API 全部 200。

## 新增 flights-tasks 域

* `GET /api/v2/inspection/flights-tasks?date=YYYY-MM-DD`（只读）
* `InspectionDataService.flights_tasks_overview` →
  `LegacyBusinessDataClient`（`LegacyClient` + `records` 载荷归一化）→
  Legacy `/api/flights` 与 `/api/routine-tasks`
* 非自动 matcher：仅参考视图，无自动关联到 InspectionRecord。
* 生产实测：**34 航班**（JG2745/B-32Q8/重庆→孟买 等，中文航段/状态）、
  **41 维修任务**（过站/停场/待派工，中文类型/机位/状态）。

## inspections 标签

复用 `/api/v2/inspections`（真实生产监察记录，需 authorized cookie），
展示记录 ID / 监察人 / 设备 / 飞机 / 航班 / 站点 / 维修任务 / 问题 / 状态 /
开始时间。

## Tests

* `tests/test_flights_tasks_dashboard.py`：not wired / wired / cookie
  forward / upstream fail / `records` key
* `test_inspection_api.py`：flights-tasks endpoint（client / not wired /
  invalid date）
* locations 标签：`renderLocations`（设备/事件/坐标数/最新定位/类型数，
  坐标明细受保护不展示）
* 全量回归 **271 tests PASS**（2 PG skip）

## Production deployment

* release：`20260818030705-m4-dashboard-consolidated`（active）
* v2 venv：psycopg2 + openpyxl 就绪
* 生产数据（03:01）：device 146 / media 47 / alarm 14 / rtview 2 /
  inspection 4；PG 9.9MB
* CHA：Mem 724Mi/1.9Gi、load 0.12；scheduler 持续正常（RSS ~36MB）

## Non-goals（未做）

未做 Dashboard 视觉大改版 / 全用户 rollout / M4 closure / M5；未扩展
媒体基础设施 / matcher / scheduler。
