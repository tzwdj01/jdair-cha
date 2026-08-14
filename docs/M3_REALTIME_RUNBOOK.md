# M3 实时视频监察运维 Runbook

适用版本：`0.7.0 / m3-realtime-rc`

## 1. 判断服务是否健康

1. `GET /api/v2/health/live`：确认 CHA v2 进程存活。
2. `GET /api/v2/health/ready`：确认主应用依赖和 realtime 配置状态。
3. `GET /api/v2/realtime/health`：确认 SessionManager cleanup task 正在运行。
4. 登录 CHA 后访问 `GET /api/v2/realtime/diagnostics`，查看 gauges、counters
   和 durations。

Realtime health 不主动登录 AEE，避免健康探针造成频繁 AEE 登录。

## 2. 关键运行指标

- `realtime_active_sessions`
- `realtime_active_streams`
- `realtime_sessions_playing`
- `realtime_sessions_degraded`
- `realtime_streams_playing`
- `realtime_streams_failed`
- `realtime_gateway_connections`
- `realtime_media_connections`
- `realtime_first_frame_timeout_total`
- `realtime_release_failure_total`
- `realtime_session_timeout_cleanup_total`

正常关闭后 active session、stream、Gateway 和 Media 数应回落。

## 3. 定位失败 stream

使用用户反馈的 `session_id` 搜索结构化日志：

```text
realtime_event {"session_id":"..."}
```

然后按 `stream_id`、`device_id`、`event`、`error_code` 和 `release_mode`
还原生命周期。API 响应 `meta.request_id` 与 `X-Request-ID` 可关联同一次 HTTP
请求。

## 4. 常见 error_code

| error_code | 含义 | 建议 |
| --- | --- | --- |
| `device_offline` | 设备离线 | 检查终端在线状态 |
| `duplicate_device` | 同设备重复添加 | 关闭原 tile 或停止重复操作 |
| `stream_limit_reached` | 单 session 已达 4 路 | 关闭一路后再添加 |
| `owner_session_limit_reached` | 单登录 active session 过多 | 关闭旧页面/session |
| `session_create_rate_limited` | 短时间创建 session 过多 | 排查页面循环重建 |
| `FIRST_FRAME_TIMEOUT` | 20 秒未收到首帧 | 单路重试并检查设备网络 |
| `AEE_GATEWAY_CONNECT_FAILED` | Gateway 不可用 | 检查 AEE 与网络 |
| `AEE_MEDIA_CONNECT_FAILED` | Media 不可用 | 检查媒体服务 |
| `STREAM_RELEASE_UNCONFIRMED` | 单路释放 ACK 未确认 | 保留 survivor，检查客户端日志 |
| `AEE_DISCONNECT_FAILED` | 上游释放未确认 | 禁用 realtime 并检查残留连接 |

## 5. AEE 不可用时

主 CHA liveness 不应失败。Realtime 页面会返回可理解的 upstream 错误，
session 进入 `FAILED` 或 `DEGRADED`。不要通过高频刷新 health 主动探测 AEE。

## 6. 安全禁用 realtime

1. 将部署配置中的 `CHA_V2_FEATURE_REALTIME_READONLY=false`。
2. 按正式变更流程重启/重新部署 v2 服务。
3. 确认 `/api/v2/system/features` 返回 realtime 为 false。
4. 确认 `/api/v2/realtime` 返回 feature disabled。

本仓库 RC 默认即为关闭状态。

## 7. 确认资源释放

结束会话后确认：

- `realtime_active_sessions=0`
- `realtime_active_streams=0`
- `realtime_gateway_connections=0`
- `realtime_media_connections=0`
- stream 日志最终出现 `stream_released` 或 session 出现 `session_closed`
- `runtime_state=RELEASED`

## 8. 回滚 M3

发布前必须记录上一版本 release 路径并备份环境文件。使用
`ops/rollback-v2.sh` 时必须提供：

- `CHA_V2_ROOT`
- `CHA_V2_CURRENT`
- `CHA_V2_ROLLBACK_TARGET`
- `CHA_V2_ENV_FILE`
- `CHA_V2_ENV_BACKUP`

先设置 `CHA_V2_ROLLBACK_DRY_RUN=true` 检查目标，再按变更审批执行。脚本拒绝
回滚到 release root 之外的路径。

## 9. 禁止发送给普通用户的日志

不得发送：

- AEE password 或其派生登录参数；
- 真实 Token、Authorization、Cookie；
- 完整 ConnecteInfo；
- Gateway/Media 内部地址；
- FTP/OSS credential；
- 原始服务器环境文件。

对外只提供 CHA `request_id`、内部 `error_code` 和脱敏后的处理结论。
