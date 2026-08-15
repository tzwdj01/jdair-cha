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

整体状态：`IN PROGRESS / PRODUCTION CANARY VALIDATION`

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
  受控 Chrome 自动化环境拒绝进入全屏并显示“浏览器未允许进入全屏”；仍需一次普通
  用户操作的生产浏览器手工验证。
* `NOT EXECUTED — INSUFFICIENT HEALTHY MEDIA DEVICES`：生产 6 路验证；
  当前观察窗口仅有 4 台 AEE-native media available 视频设备，按已批准 evidence
  waiver 不阻塞 4 路首发容量结论。

未实现或未进入当前已批准 release 范围：

* `TODO`：9 路产品能力和真实容量验证。
* `TODO`：多账号池和完整账号健康管理。
* `TODO`：将 receive-only Audio 对生产 Canary 开放。

以上 `TODO` 不得因本文件更新而自动开始。此前 M3 release 已明确将 9 路、
AccountPool 和生产 Audio 开放排除在当前首发范围之外。重新进入这些能力必须由后续
明确任务授权，并更新本文件中的 M3 执行计划。

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

当前状态：
`IN PROGRESS / PRODUCTION CANARY VALIDATION`

当前只执行 M3 Production Canary 的最终证据收口、普通用户操作的生产全屏验证、
文档/Git 结论和首发容量配置建议。

不得自动开发 M4，不得顺手扩展 9 路、AccountPool、Audio 生产开放、PTZ、对讲
或录像。

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

M3 当前剩余关键验收：

* 在普通用户操作的生产 Chrome 中点击任一正在播放 tile 的全屏按钮，确认：
  * tile 实际进入全屏；
  * 退出全屏后其它 stream 继续 `PLAYING`；
  * session close 后资源计数仍回到 0。
* 更新最终 Production Canary report、Runbook/TASK_GOAL 结论并完成 Git
  commit/push。

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
* 首帧、分辨率、track live、截图和全屏均有实际证据。
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

## In Progress

* Active Milestone 保持 M3。
* 当前仍为 `PRODUCTION CANARY VALIDATION`，但只剩全屏的普通用户操作验证和
  最终证据/Git 收口。

## Next

1. 在普通用户操作的 Chrome 中，以 Canary 用户打开 1 台已确认健康设备，手工点击
   tile 全屏按钮并退出全屏。
2. 复核其它 stream/session 不受影响并再次确认资源计数归零。
3. 将全屏结果更新到 Production Canary report 和本文件。
4. 若手工全屏 PASS，形成 M3 Milestone Completion Report；生产首发建议
   `max_streams=4`，Realtime 保持关闭等待下一次明确激活授权。

## Blocked

* 当前没有由单个媒体不可用设备造成的项目级 blocker。
* 当前唯一验收缺口是自动化浏览器不提供 Fullscreen API 用户激活，导致生产全屏
  只能标记为 `COMPLETED / UNVERIFIED`；这不是已确认的产品代码故障。
* 只有以下情况阻塞本轮：
  * 没有任何 AEE-native 可实时播放设备；
  * AEE 正常而 CHA 对同设备失败；
  * Production Realtime 出现资源泄漏；
  * 安全边界或 Canary 隔离失败；
  * Legacy/V2 回归。

## AEE Verification Required

* `WXB358` compatibility 调查：`NON-BLOCKING / PAUSED`。
* 未来触发条件：AEE 原生 `mediaMonitor=opened` 且产生 `newConsumer`。
* 在触发条件出现前，禁止轮询、反复 `mediaMonitor`、猜 codec/streamType、
  实现 H.265 workaround、复制 WASM/`/mediaStream` 或引入 decoder/FFmpeg/SFU。
