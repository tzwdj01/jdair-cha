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
| AccountPool | NOT REQUIRED |
| Control / PTZ / talkback / recording | OUT OF SCOPE |

`validated_stream_limit=6`

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
