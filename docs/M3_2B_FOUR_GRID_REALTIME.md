# M3.2B 正式 1/4 路实时视频监察

> 历史阶段文档（archived）。M3 Final 已将真实验证上限提升为 6 路。

版本：0.6.0

构建：`m3-four-grid-realtime`

功能开关：生产默认关闭

## 产品能力

正式页面位于 `/api/v2/realtime`，复用 V2/M2 的导航、卡片、状态色、日间/夜间
主题和紧凑布局。维修质量人员可以：

1. 查看在线和离线终端；
2. 单击添加设备，或勾选多个设备后开始监控；
3. 在同一 CHA session 中打开最多 4 路视频；
4. 查看每路连接、首帧、分辨率和 track 状态；
5. 独立关闭任意一路，不影响其他画面；
6. 保留 FAILED tile 并对目标设备执行安全重试；
7. 对单个 tile 使用浏览器 Fullscreen API；
8. 明确结束完整会话并释放 AEE 资源。

一个 stream 时使用单画面；2–4 个 stream 时自动使用 2×2。布局变化只改变
CSS，不重新登录 AEE，不重建 Gateway、Media WebSocket、receive transport 或
consumer。

## Model A

```text
1 CHA session
→ 1 AEE login
→ 1 Gateway WebSocket
→ 1 Media WebSocket
→ 1 mcs8_admin room
→ 1 browser receive transport
→ 1–4 video consumers
```

`multistream_runtime.js` 是正式页面唯一的 AEE 浏览器运行时。产品页面只负责设备
选择、tile 状态、控制 WebSocket、首帧超时、错误翻译、重试、布局和页面退出清理。

## 生命周期与故障隔离

- 新增设备：创建 stream → 控制通道 → 复用/建立 runtime → `openVideo` →
  等待首帧 → `PLAYING`。
- 首帧超过 20 秒：目标 tile 为 `FAILED`，session 为 `DEGRADED`，其他视频继续。
- 重试：删除 FAILED stream，确认 `closeVideo` 后重新添加同一设备；没有新增 retry
  API。
- 单路关闭：DELETE stream → `close_stream` → `closeVideo(device)` → ACK →
  删除 tile。
- 单路关闭 ACK 失败：保留 FAILED tile，不误杀 survivor。
- Control、Gateway 或 Media 共享连接异常：所有活动 tile 显示 `DEGRADED`，页面提供
  一次明确的“重新建立监控”操作，不执行无限自动重连。
- 结束监控：DELETE session → `close_session` → runtime close → tracks、Media、
  Gateway 和 session 清理。
- 刷新、关闭 tab 或离开页面：`pagehide` 执行 best-effort keepalive DELETE，同时
  关闭 runtime/control；服务端 WebSocket disconnect 和 session timeout 是最终兜底。

## 安全边界

- 浏览器不接收 AEE password、真实登录 Token、真实 Media Token、
  Authorization header 或内部媒体地址。
- `ConnecteInfo` 继续过滤并改写为同源路径。
- Gateway/Media relay 继续执行 receive-only 命令白名单。
- video 默认 `muted`，没有调用 `openAudio`。
- 不存在透明 WebSocket tunnel、FFmpeg、中转、重编码或自建 SFU。

## 明确限制

- `4 streams = validated`
- `6 streams = unvalidated`
- `9 streams = unvalidated`
- `CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION=4`
- 未实现音频、对讲、云台、截图管理、录像、告警、账号池和生产发布。
- session 仍为进程内状态。

## 2026-08-14 验证结果

正式产品页面使用真实 AEE 设备完成了 4 路 × 10 分钟只读 soak test：

| device_id | 分辨率 | 首帧 | 10 分钟 track | 单路关闭 | 重新打开 |
| --- | --- | ---: | --- | --- | --- |
| WXB320 | 1280 × 720 | 2512 ms | live | 成功，其他三路继续 | 成功，1593 ms |
| WXB337 | 1920 × 1080 | 1206 ms | live | 会话关闭时释放 | 不适用 |
| WXB342 | 1920 × 1080 | 2281 ms | live | 会话关闭时释放 | 不适用 |
| WXB345 | 1920 × 1080 | 1906 ms | live | 会话关闭时释放 | 不适用 |

观察期间没有页面异常或 Gateway/Media 重连。浏览器 JS heap 在约
5.01–7.18 MiB 间随 GC 波动，结束采样为 6.13 MiB，没有持续单向增长；
600 秒内 CDP `TaskDuration` 增量约 1.413 秒。用于本地验证的 CHA 进程工作集
约 4.83–4.89 MiB。完整关闭后服务端 session 为 `CLOSED`，
`connection_reusable=false`，所有 stream 均为 `CLOSED/RELEASED`。

自动化浏览器流程另行覆盖：20 秒首帧超时不影响其他画面、FAILED tile 安全重试、
单 tile Fullscreen API、Control 断开后四路 `DEGRADED`、用户显式重建 session
后恢复四路 `PLAYING`，以及 `pagehide` best-effort cleanup。
