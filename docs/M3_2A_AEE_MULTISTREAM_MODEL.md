# M3.2A AEE 多路实时视频模型验证

> 历史实验文档（experimental / archived）。最终容量结论以
> `M3_FINAL_VALIDATION_REPORT.md` 为准。

验证日期：2026-08-14
结论：采用 **Model A**

## 1. 已验证的原生链路

M3.2A 没有新增转码、拉流中转或媒体服务器，继续复用：

`AEE Token → Gateway WebSocket → mcs8_admin → openVideo → newConsumer → MediaStream`

隔离 PoC 使用一个服务端 AEE 登录、一个 Gateway WebSocket、一个 Media
WebSocket、一个 `mcs8_admin` 客户端和一个浏览器接收 transport，逐步打开
1、2、4 路视频。

## 2. 实测结果

| 项目 | 结果 |
| --- | --- |
| 验证设备 | WXB320、WXB337、WXB342、WXB345 |
| 1 路 | PASS |
| 2 路 | PASS |
| 4 路 | PASS |
| Gateway 连接 | 1 个 |
| Media 连接 | 1 个 |
| 浏览器接收 transport | 1 个 |
| 活跃 video consumer | 4 个，consumer ID 独立 |
| track 状态 | 全部 `live` |
| 首帧 | 全部成功 |
| 单路关闭 | 其余视频继续 `PLAYING/live` |
| 已关闭设备重新打开 | PASS |
| 最终关闭 | Gateway/Media 当前连接数均回到 0 |

| 设备 | 分辨率 | 首次首帧 |
| --- | --- | --- |
| WXB320 | 1280×720 | 1259 ms |
| WXB337 | 1920×1080 | 1083 ms |
| WXB342 | 1920×1080 | 1489 ms |
| WXB345 | 1920×1080 | 1550 ms |

首次首帧约 1.08–1.55 秒；WXB320 重新打开约 0.48–0.49 秒。
四路稳定观察约 60 秒，没有出现页面错误或 track 中断。为避免长时间占用在线
业务设备，本轮没有执行十分钟压力测试，因此 **4 路是已验证值，不代表 AEE
账号的绝对上限**。

浏览器观测到的 JavaScript heap 约 3.9–5.5 MB，CDP `TaskDuration`
在约 59 秒观察窗口内增加约 0.195 秒。该指标仅作为浏览器任务负载代理，不等同
于整棵 Chrome 进程的操作系统 CPU/内存占用。

本地隔离 PoC 服务进程采样 working set 约 5.1 MB、private memory 约 1.0 MB；
短观察窗口内 `Get-Process` 的 CPU 增量低于采样分辨率。该数值只代表本地 PoC
编排进程，不代表未来生产部署容量。

## 3. 模型选择

采用：

**Model A：1 CHA session → 1 AEE login → 1 Gateway → 1 Media room /
receive transport → N video consumers**

暂不采用每路独立登录/连接，也不引入 AccountPool。默认每个 CHA session 最大
4 路，由 `CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION` 配置；代码设置硬上限 16，
但任何超过 4 路的配置都必须先完成独立验证。

后续如真实负载证明单账号存在更低并发上限，AccountPool 只需向 SessionManager
提供“租用账号、归还账号、标记故障”接口，不改变 AEE 媒体层和现有业务接口。

## 4. 正式会话模型

- session 保存共享 AEE Adapter、Gateway/Media relay、控制 WebSocket 和心跳。
- 每个 stream 独立保存 `stream_id`、`device_id`、状态、首帧、分辨率、
  `runtime_state`、错误、释放方式和 `closed_at`。
- 重复设备被拒绝；活动 stream 数达到配置上限后拒绝新增。
- 所有活动 stream 正常播放时 session 为 `PLAYING`。
- 任一 stream 为 `FAILED/DEGRADED` 时 session 为 `DEGRADED`。
- 所有 stream 关闭后 session 回到 `READY`。
- 已关闭 stream 作为有界生命周期记录保留，便于查询释放结果。

## 5. 独立释放规则

删除单路视频时，SessionManager 向浏览器发送包含 `stream_id/device_id` 的
`close_stream` 命令。浏览器必须对目标设备执行真实 `closeVideo` 并返回 ACK。

- ACK 成功：只撤销目标设备授权并标记该 stream `CLOSED`。
- 多路会话中 ACK 失败/超时：目标 stream 标记
  `STREAM_RELEASE_UNCONFIRMED`，session 进入 `DEGRADED`，不关闭其他视频。
- 单路会话中 ACK 失败：允许回退为整个 AEE 连接断开，以保证不留僵尸资源。
- 关闭 session：关闭浏览器 SDK、断开 Media/Gateway、关闭全部 stream；操作幂等。
- 控制或媒体 WebSocket 异常断开：全部活动 stream 降级并强制释放共享 AEE
  连接。

AEE SDK 在关闭单路后可能暂时保留已结束 consumer 的内部对象，但对应 track
已经 `ended`、页面视频映射已删除；关闭整个 SDK 后内部 consumer 和 WebSocket
一并清理。

## 6. 前后端职责

- 后端：凭据、AEE 登录、同源 relay、设备授权、session/stream 状态、心跳和
  释放确认。
- 浏览器：使用固化 AEE SDK 创建一个接收连接，为每个 stream 绑定独立 video
  元素，执行 `openVideo/closeVideo`，上报首帧和 track 状态。
- `multistream_runtime.js` 提供无 UI 的多流运行时；M3.1 单路验证页面保持不变。
  1/4/6/9 正式布局属于 M3.2B。

## 7. 安全与功能开关

- AEE 用户名、密码、登录 Token、媒体 Token 均不返回浏览器。
- 浏览器只看到 CHA `session_id`、HttpOnly lease Cookie、同源 WebSocket 路径
  和无效占位 Token。
- 日志禁止记录密码、完整 Token、Authorization 和 Cookie。
- PoC 从环境变量读取凭据，结果文件与日志分离；结果、日志、压缩包均不进入 Git。
- `realtime_readonly=false`、`realtime_audio=false`、
  `realtime_control=false`、`account_pool_v2=false` 保持不变。
- 本阶段没有修改或重启生产服务，没有修改生产数据库、Nginx、systemd 或 env。

隔离验证入口为 `ops/mature_m32a_multistream_probe.py`，本地应用和浏览器脚本分别
为 `ops/mature_m32a_probe_app.py`、`ops/mature_m32a_probe_app.js`。运行时只通过
`CHA_V2_AEE_*` 和 `CHA_M32A_DEVICES` 环境变量注入配置；stdout/stderr 日志与
JSON 结果使用不同文件。

## 8. 已知限制

- 已验证并发上限为 4，不声明支持 6/9 路。
- 本轮没有正式多画面产品 UI、拖拽、批量选设备、音频、对讲、云台、截图或录像。
- session 仍为进程内状态，服务重启后失效。
- 60 秒真实观察不能替代后续更长时间、更多设备和弱网条件下的容量测试。
