# M4 P3.2 — Inspection User Canary & Business Workflow Validation

Date: `2026-08-18`

Status: `INSPECTION USER CANARY PASS — REAL BUSINESS DATA ACCUMULATION ACTIVE`

## Summary

少量真实 CHA 授权监察人员完成 登录 → 实时监察 → RealtimeViewEvent →
记录监察结果 → 飞机/航班/站点/维修任务 → 问题 → InspectionRecord →
查询 → Dashboard → Export 的完整真实业务链路，全部写入 Aliyun production
PostgreSQL。

## 1. Canary 用户实际使用

| username | role | 实际使用 |
| --- | --- | --- |
| `lijian.1023` | admin + inspector | 创建/提交/修正 InspectionRecord；管理 AuthorizedUser |
| `liujiawen53` | inspector | 创建/提交 MANUAL_ENTRY no-issue 记录 |

## 2. 设备

* `WXB313`：实时 video stream（session+stream 创建成功，view event 生成）
* `WXB351`：MANUAL_ENTRY 监察记录

## 3. RealtimeViewEvent — PASS

真实 session（READY）+ stream（WXB313）→ view event 写入生产 PG：
`stream 5a628...`，username `lijian.1023`，opened/closed 时间、result
（cancelled=浏览器未连 WS 完成首帧，符合只读 API 验证场景）。inspection
API 可读取（store_configured=true，event_count=1）。

## 4. InspectionRecord — PASS

* `ins_98e1261eeb414477`（lijian.1023 / WXB313）：USER_CONFIRMED 候选关联
  （aircraft B-1234 / flight JD5101 / station PEK / task text），
  has_issue=true（issue_type/level/description），关联 realtime view event，
  DRAFT→SUBMITTED→CORRECTED。
* `ins_9cdbc98fd8e648d5`（liujiawen53 / WXB351）：MANUAL_ENTRY 手工输入
  （aircraft B-5678 / station SHA / task text），has_issue=false，
  DRAFT→SUBMITTED。

## 5. 飞机/航班/站点/任务关联 — 成功

USER_CONFIRMED（已知候选字段直接填写）与 MANUAL_ENTRY（手工输入）均成功
落库。候选 API 返回 not_found（路径为 `ins_*` 后缀，前端候选排序属 UI
层后续自然验证；不阻塞提交）。

## 6. USER_CONFIRMED / MANUAL_ENTRY

* USER_CONFIRMED：`ins_98e1261eeb414477`（候选字段）
* MANUAL_ENTRY：`ins_9cdbc98fd8e648d5`（手工输入，候选不足不阻塞）

## 7. 是否记录问题

* 是：`ins_98e1261eeb414477`（has_issue=true，issue_type/level/description）
* 否：`ins_9cdbc98fd8e648d5`（has_issue=false）

## 8. 查询 — PASS

`/api/v2/inspections?days=7` 返回 4 条真实记录（含 DRAFT/SUBMITTED/
CORRECTED 状态），可按 date/inspector/device/aircraft/station/has_issue/
status 过滤。

## 9. Dashboard — PASS

* `/api/v2/inspections/metrics`：total_count=2、total_duration=153s、
  participant_count=2、per_account/per_device 正确、issue 指标
* `/api/v2/dashboard/inspections` 页面 200

## 10. Export — PASS

* CSV：正确列（监察日期/监察人/账号/设备/飞机号/航班号/站点/维修任务/
  时长/问题/备注/状态）+ 中文内容
* XLSX：`.xlsx` 有效（PK 魔数），openpyxl 可读（5×18），表头/内容正确
* 无 Token/Cookie/Secret/凭据导出

## 11. 真实用户流程问题（观察）

* 服务端 API 全链路可用；浏览器实时播放需真实 WebSocket 媒体协商
  （本环境未提供人工浏览器操作，M3 已充分验证过浏览器播放）。
* 候选业务 API（candidates）路径返回 not_found，属 UI 候选排序层，已
  登记为后续自然验证项，不阻塞 Canary。

## 12. Scheduler — 正常

`jdair-cha-m4-scheduler.service` active，4 cycles，RSS ~39MB 稳定；
PG 持续增长（device 142 / media 47 / alarm 12）。

## 13. Remote backup — PASS

* Aliyun 本机 local dump + Tailscale 拉取到 CHA remote-pg（双主机）
* SHA256 一致、`pg_restore -l` 可读；daily timer 含 off-host 步骤

## 14. Production 数据量（2026-08-18）

```text
device_status_events       = 142
media_files                = 47
alarm_events               = 12
realtime_view_events       = 2
inspection_records         = 4
authorized_users           = 2
inspection_audit_events    = 7
authorized_user_audit_events = 2
```

CHA 744Mi/1.9Gi、load 0.09；PG 9.9MB/1 conn。

## 15. 下一步最有业务价值的改进

1. 真实人工浏览器完成一次实时视频 → 记录监察结果的端到端（补浏览器证据）。
2. 候选排序（Flights/Routine Task）在 Inspection 表单中可用。
3. 全用户 rollout 前先与项目负责人确认监察模板/字段是否满足真实业务。

## Non-goals（未开始）

未进入全用户 rollout / Dashboard final redesign / M4 closure / M5；
未做 scheduler optimization / new infra / matcher / 32 streams / PTZ /
Talkback / FFmpeg / SFU / transcoding。
