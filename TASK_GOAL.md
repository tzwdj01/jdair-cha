# CHA Video Record System Optimization — Active Task Goal

Last updated: 2026-08-14

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
* 当前治理基线提交：`e6355f3`，工作树在本文件修改前为 clean。
* 当前生产 V2 release：
  `/opt/jdair-cha/v2/releases/0.8.0-m3-final-rc-release-fix`。
* 当前生产 Realtime、Audio、Control、AccountPool feature flag 均为
  `false`。
* 当前生产 AEE 和 Canary 配置存在于受保护的生产环境中，不进入 Git。
* 最新生产回滚备份：
  `/opt/jdair-cha/backups/jdair-cha-before-m3-realtime-20260814-173601.tar.gz`。
* 最新 Production Canary 因 `WXB358` 首帧失败中止；生产 Realtime 已关闭。

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

整体状态：`BLOCKED`

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

已实现但当前生产未完成验收：

* `COMPLETED / UNVERIFIED`：当前生产 release 的完整 1 → 4 → 6 Canary。
* `COMPLETED / UNVERIFIED`：生产环境 authenticated non-Canary 的页面、API 和三个
  WebSocket 负向验证。

未实现或未进入当前已批准 release 范围：

* `TODO`：9 路产品能力和真实容量验证。
* `TODO`：多账号池和完整账号健康管理。
* `TODO`：将 receive-only Audio 对生产 Canary 开放。

以上 `TODO` 不得因本文件更新而自动开始。此前 M3 release 已明确将 9 路、
AccountPool 和生产 Audio 开放排除在当前首发范围之外。重新进入这些能力必须由后续
明确任务授权，并更新本文件中的 M3 执行计划。

当前 blocker：

* `BLOCKED`：生产 Canary 设备 `WXB358` 两次无法产生首帧。
* `AEE VERIFICATION REQUIRED`：需要确认同设备、同场景在 AEE Reference
  Implementation 中的实际表现，以及 `openvideo is not defined` 的来源。

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

## M4 — Integration and High Concurrency

状态：`TODO`

目标能力：

* 16 / 32 路；
* 自适应码流；
* 地图联动；
* 调度状态联动；
* 异常选播；
* 实时与历史视频联动。

不得自动开始，除非：

`ACTIVE MILESTONE = M4`

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

`ACTIVE MILESTONE: M3`

当前状态：`BLOCKED / AEE VERIFICATION REQUIRED`

当前只执行 M3 Production Canary 的证据恢复、最小必要修复、回归和受控验收。

不得在该 blocker 未解决时自动开发 M4，不得顺手扩展 9 路、AccountPool、Audio
生产开放、PTZ、对讲或录像。

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

当前 `WXB358` 项必须记录：

* Question；
* Device；
* Scenario；
* Expected Observation；
* Required Network Evidence；
* Required WebSocket Evidence；
* Required SDK Evidence；
* Required Media Evidence。

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

* 保持 `CHA_V2_FEATURE_REALTIME_READONLY=false`，直至新 Canary 获得批准。
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

M3 当前剩余关键验收：

* AEE 与 CHA 在 `WXB358` 上的同设备、同场景证据。
* `openvideo is not defined` 的来源和影响。
* 当前生产 release 的单路、四路、六路首帧和 live track。
* 四路和六路 selective close、survivor、reopen。
* 现有截图、全屏和重连行为。
* authenticated non-Canary 生产拒绝。
* Session/Stream/Gateway/Media active counters 最终全部回到 0。
* Legacy/V2 health、Nginx、restart count、5xx 和结构化错误日志。

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
* 当前治理提交尚未推送远端。
* 任何 `WXB358` 修复应建立独立、最小范围的修复提交或分支。
* 未通过验证前不更新生产 `current`，不创建 release tag，不自动 merge。

---

# 11. Evidence / Decision Log

## Issue

Production Canary 中 `WXB358` 无法产生首帧；首次测试中 `WXB353` 成功播放后，
增加 `WXB358` 失败；第二次将 `WXB358` 作为第一路单独打开仍失败。

状态：`BLOCKED / AEE VERIFICATION REQUIRED`

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

`AEE VERIFICATION REQUIRED`

必须使用合法授权的 AEE 用户，在相同设备和尽可能相同的浏览器、网络、时间窗口中
验证：

* AEE 是否可以打开 `WXB358`；
* AEE 实际 SDK 方法名称、大小写、参数和返回值；
* Gateway/Media/room/openVideo/consumer/track/first-frame 顺序；
* RTP、codec、fmtp/profile-level-id、stream profile 和 capability；
* close、leave、disconnect 和资源释放。

使用 `WXB353` 作为当前已知成功对照设备。若在线并获批准，可增加历史验证设备
`WXB301`、`WXB342`、`WXB345`、`WXB367`、`WXB368`。

## Classification

当前：`AEE VERIFICATION REQUIRED`

完成 AEE vs CHA Evidence 后必须分类为：

* Class A
* Class B
* Class C
* Class D

从现有现象推测媒体问题可能落入 Class B，但在 AEE 证据完成前不得将该推测当作结论。

## Decision

* 保持生产 Realtime 关闭。
* 在 AEE 证据形成前不修改 CHA 媒体协议或 SDK Adapter。
* 先完成相同设备、相同场景的 AEE vs CHA 对照。
* 只有确认 CHA 与 AEE 的最小差异后，才允许提出最小修复。
* 修复后必须重新执行自动化回归和受控 1 → 4 → 6 Production Canary。

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

* `WXB358` 已形成完整 AEE vs CHA Evidence 并完成 Class A/B/C/D 分类。
* 当前生产 release 的 1 → 4 → 6 Canary 通过。
* authenticated non-Canary 页面/API/WebSocket 拒绝通过。
* 首帧、分辨率、track live、截图、全屏、重连均有实际证据。
* selective close、survivor 和 reopen 通过。
* Session/Stream/Gateway/Media active counters 全部回到 0。
* Legacy 与 V2 服务健康，无 release 引入的 5xx/restart。
* AEE 长期凭据继续只保留在服务端生产配置。
* 生产启用或继续关闭的决定有明确记录。

未满足以上条件：

不得宣布 Active Milestone 完成。

---

# 13. Current Execution Plan

## Completed

* M0、M1、M2 已发布并验证。
* M3.1、M3.2A、M3.2B、M3.2C 和 M3 Final 当前首发范围代码已完成。
* Release-fix、生产备份、独立 release 部署和关闭状态 health 已完成。
* 两次失败 Canary 的 Session/Gateway/Media 资源均已释放。
* 项目治理文件和 AEE Reference 原则已接入。

## In Progress

* 当前没有正在编写的业务代码。
* Active Milestone 保持 M3，等待 AEE 对照证据。

## Next

1. 在合法授权环境中对 `WXB358` 和 `WXB353` 执行 AEE vs CHA 对照。
2. 形成 Test Context、AEE Behaviour、CHA Behaviour、Difference、Conclusion。
3. 完成 Class A/B/C/D 分类。
4. 如确认 CHA gap，创建最小修复并运行现有 M3 测试。
5. 申请新的受控 Production Canary 窗口并执行完整验收。

## Blocked

* `WXB358` 首帧失败原因未确认。
* 当前 Production Canary 未完成 1 → 4 → 6。
* 在 blocker 解决前，生产 Realtime 保持关闭。

## AEE Verification Required

* Question：AEE 原生页面是否能在相同条件下播放 `WXB358`，其调用与 CHA
  的第一个差异是什么？
* Device：`WXB358`，控制设备 `WXB353`。
* Scenario：AEE 单路播放后执行 CHA 单路播放。
* Expected Observation：定位 Gateway、Media、room、SDK、consumer、track 或
  first-frame 流程中的首个已确认差异。
* Required Network Evidence：HTTP 状态、时序、设备 capability 和媒体服务解析。
* Required WebSocket Evidence：Gateway/Media 生命周期、消息和关闭顺序。
* Required SDK Evidence：方法名/大小写、参数、返回值、callback 和错误来源。
* Required Media Evidence：SDP/ICE/DTLS、RTP、codec/profile、stream profile、
  resolution、track 和 first-frame。
