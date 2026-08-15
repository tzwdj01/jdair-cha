# M3 Final Validation Report

验证日期：`2026-08-14`

候选版本：`0.8.0 / m3-final-rc`

## 最终产品范围

| 能力 | 结论 |
| --- | --- |
| Video 1/2/4/6 | SUPPORTED |
| Video 9 | NOT TESTED / NOT ADVERTISED |
| Receive-only audio | SUPPORTED，生产开关默认关闭 |
| Local screenshot | SUPPORTED |
| Fullscreen | COMPLETED / UNVERIFIED，已获非阻塞 evidence waiver |
| AccountPool | NOT REQUIRED |
| Control / PTZ / talkback / recording | OUT OF SCOPE |

`validated_stream_limit=6`

近期 Realtime Video 产品最大范围为 16 路，但不代表已批准立即开发或已完成容量
验证。32 路及更高并发为 `DEFERRED`。Realtime Video 后续作为监察数据平台的基础
下钻能力，不再作为主要研发方向。

## 真实 AEE 容量

最终六路设备：`WXB301`、`WXB342`、`WXB345`、`WXB353`、`WXB367`、
`WXB368`。

- 六路均为 1920×1080 H.264，track 为 `live`。
- 首帧时间分别约为 2858、2330、1983、2277、2219、2210 ms。
- Gateway current=1，Media current=1。
- 关闭一路后其余 5 路保持 PLAYING；重新打开成功。
- 30 秒短时观察完成，最终 Gateway=0、Media=0、monitor=0。
- 七路尝试在第七台设备首帧超时，不能据此认定为账号容量失败。
- 九路没有足够安全、稳定的在线设备，未执行真实容量测试。

## Audio

真实设备 `WXB301` 完成 video + receive-only audio：

- `openAudio=200`，codec=`audio/opus`，audio track=`live`。
- 默认 muted，用户操作后可 unmute。
- `closeAudio=200`，audio track 进入 ended，video track 保持 live。
- session 关闭后 Gateway=0、Media=0、monitor=0。
- 未请求麦克风，无 send transport、talkback 或设备控制。

结论：Audio GO，但 `realtime_audio=false` 保持默认关闭，等待发布审批。

## Screenshot 和恢复

- 六路浏览器产品流程完成本地 PNG 截图，包含设备编号和本地时间。
- 图片不经过 API、不写服务器日志、不上传第三方。
- Control 断开后所有 active streams 进入 DEGRADED。
- 1.5 秒 backoff 后只自动重建一次；成功后恢复六路 PLAYING。
- 自动恢复失败时显示手动“重新建立监控”，不存在无限 reconnect loop。

## 稳定性

- 后端：200 个 mixed session lifecycle PASS，覆盖 1/4/6 路、
  FIRST_FRAME_TIMEOUT 后恢复、browser disconnect、normal cleanup。
- 最终：active_sessions=0、active_streams=0，retained sessions ≤ 16。
- 浏览器：20 轮完整六路 create → selective close → reopen → close PASS。
- 140 次 mock stream open/close 后 tracksActive=0、clientsActive=0、
  socketsActive=0、handlers=0、consumer records=0。
- JS heap 首末约 2.24 MB → 2.42 MB；复用的六路 tile pool 使 live DOM
  nodes 固定为 296，CDP node count 在预热后固定为 2522，未发现明确无界增长。
- AEE SDK 在单 session 内可能保留 ended consumer object；它不形成 active
  track/listener，并在完整 session close 时随 SDK client 回收，记录为 known
  SDK behavior，不修改第三方 SDK。

## 安全和生产状态

- 未登录、owner 隔离、cross-user、lease、expired/closed replay、Origin、
  Cookie、rate/session/stream limit、diagnostics redaction 测试通过。
- Git 和 RC 不包含密码、长期 Token、Authorization、Cookie、生产 `.env`、
  server backup 或媒体内容。
- 生产 realtime、audio、control、AccountPool 开关均保持 false。
- 未修改生产 current、Nginx、systemd、数据库、env，未重启或发布生产服务。

## Staging / Canary

仓库和现有资料未证明存在与生产端口、current、env、systemd 完全隔离的真实
staging，因此本轮没有部署 staging。只完成本地/隔离 release tree 验证和
Canary runbook。正式 Canary 必须另行审批。

## Production Canary 与 M3 Closure

`2026-08-15` 当前 production release 已完成：

- 1 路 `WXB353` 首帧、1920×1080、track live、heartbeat、close/reopen 和
  session cleanup；
- 4 路同时播放、selective close、survivor、reopen、screenshot 和完整资源释放；
- 非 Canary 用户页面、API 和 Control/Gateway/Media WebSocket 拒绝；
- Session/Stream/Gateway/Media active counters 归零；
- Legacy/V2 health 和 restart 回归检查。

`WXB358` 已确认在同一观察窗口内由 AEE 原生 `mediaMonitor` 返回
`devices is offline`，属于 upstream/device media availability exception，
不再是 M3 blocker，也不围绕该设备开发 H.265 或其它 workaround。

Fullscreen 最终状态：

`COMPLETED / UNVERIFIED`

生产自动化和 Computer Use 环境无法可靠提供并验证浏览器 Fullscreen API 所需的
瞬时 real-user activation。没有确认的 CHA Fullscreen 产品代码缺陷。项目负责人已
批准 evidence waiver，将普通用户
`enter fullscreen → exit fullscreen → playback continues`
证据移动到 `POST-M3 OPERATIONAL FOLLOW-UP`。不得将该项标记为 PASS。

M3 最终状态：

`CLOSED / ACCEPTED WITH EVIDENCE WAIVER`

M3 关账后冻结以下近期方向：

- 32 路及更高并发；
- 为并发引入复杂 AccountPool；
- H.265 workaround；
- FFmpeg、自建 SFU、自建 transcoding；
- 无真实业务需求和 Architecture Escalation Evidence 的媒体架构升级。

`2026-08-15 23:24 CST` 生产关账复核确认：

- Realtime、Audio、Control、AccountPool 均为 `false`；
- V2 active，`NRestarts=0`；
- liveness、readiness 和 Legacy dependency PASS；
- production current、Nginx、database 和 AEE Secret 未修改。

不得自动进入 M4。
