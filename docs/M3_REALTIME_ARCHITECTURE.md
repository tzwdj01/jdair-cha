# M3 实时视频监察架构

适用版本：`0.8.0 / m3-final-rc`

## 产品边界

- 视频：正式支持 1～6 路，布局为单画面、2×2、3×2。
- 音频：只接收、默认关闭、用户点击后开启，同一时刻最多一路。
- 截图：浏览器本地 `video → canvas → PNG`，不上传服务器。
- 不包含：对讲、麦克风、send transport、PTZ、设备控制、录像、
  AccountPool、自建转码、FFmpeg、自建 SFU。

## 运行模型

```text
Browser
  → CHA Realtime HTTP / Control WebSocket
  → CHA Session Manager
  → AEE Adapter
  → 1 AEE login
  → 1 Gateway WebSocket
  → 1 Media WebSocket
  → 1 mcs8_admin room
  → 1 receive transport
  → N video consumers + at most 1 audio consumer
```

采用 Model A：一个 CHA session 绑定一个 AEE 登录和一组共享 Gateway/Media
连接。单路关闭只释放对应 monitor/consumer；共享连接异常时整个 session 进入
`DEGRADED`，浏览器最多自动重建一次，失败后必须由用户手动重建。

## Session 生命周期

`CREATING → READY → PLAYING/DEGRADED → CLOSING → CLOSED`

- 创建时只返回 CHA `session_id` 和 HttpOnly lease cookie。
- heartbeat 延长 session 活跃时间。
- 超时、浏览器异常离开和服务关闭都会触发上游断开与本地清理。
- CLOSED session 只短期保留诊断历史，不能重放 lease。

## Stream 生命周期

`CONNECTING → WAITING_FIRST_FRAME → PLAYING`

失败进入 `FAILED` 或 `DEGRADED`；关闭进入
`CLOSING → CLOSED`。关闭优先等待浏览器执行 `closeVideo/closeAudio` ACK；
无法确认且仍有 survivor 时不破坏共享连接，而是将目标标为失败；无 survivor
时允许断开整个 AEE adapter 完成兜底释放。

## 凭据和媒体安全边界

- AEE 用户名、密码、长期 Token 只存在于服务端配置和进程内存。
- 浏览器只获得同源 CHA HTTP/WebSocket 路径，不获得 AEE 登录凭据或真实
  `ConnecteInfo`。
- AEE Adapter 只允许已授权设备的 receive-only `mediaMonitor`：
  video `streamType=2`，audio `streamType=0`。
- 浏览器不请求 microphone，不创建 send transport，不具备 talkback。
- 截图只在本地生成和下载；服务端仅接收成功/失败计数，不接收图片内容。

## 容量结论

- 1、2、4、6 路：真实 AEE 链路通过。
- 6 路使用一个 account、一个 Gateway、一个 Media、一个 receive transport。
- 9 路：因没有足够数量可安全持续使用的在线设备，未测试、未显示、未配置。
- `CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION=6`，服务端同时硬限制最大值为 6。
- 单账号已满足 M3 首发范围，因此 AccountPool 不需要进入 M3。

## 运行依赖和兜底

实时视频依赖 CHA v2、网络、AEE 上游和在线设备。异常时可能加载慢、首帧超时
或画面中断。原 CHA 页面和旧业务接口不被替换，realtime 不可用时继续使用原
系统入口。
