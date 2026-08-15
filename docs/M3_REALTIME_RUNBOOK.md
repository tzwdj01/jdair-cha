# M3 实时视频监察运维 Runbook

适用版本：`0.8.0 / m3-final-rc`

## 1. 判断服务是否健康

1. `GET /api/v2/health/live`：确认 CHA v2 进程存活。
2. `GET /api/v2/health/ready`：确认主应用依赖和 realtime 配置状态。
3. `GET /api/v2/realtime/health`：确认 SessionManager cleanup task 正在运行。
4. 登录 CHA 后访问 `GET /api/v2/realtime/diagnostics`，查看 gauges、counters
   和 durations。

Realtime health 不主动登录 AEE，避免健康探针造成频繁 AEE 登录。返回值中的：

- `enabled` 表示全局 realtime 功能开关；
- `aee_configured` 只表示所需 AEE 环境变量均存在；
- `canary_configured` 表示至少配置了一个受控 CHA 登录用户；
- `configured` 只有在 AEE 和 Canary 用户配置都完整时才为 true。

这些字段只返回布尔状态，不返回用户名、密码、Token、内部地址或 allowlist
内容。

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
- `realtime_audio_open_total`
- `realtime_audio_close_total`
- `realtime_audio_failure_total`
- `realtime_screenshot_total`
- `realtime_screenshot_failure_total`

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
| `stream_limit_reached` | 单 session 已达 6 路 | 关闭一路后再添加 |
| `owner_session_limit_reached` | 单登录 active session 过多 | 关闭旧页面/session |
| `session_create_rate_limited` | 短时间创建 session 过多 | 排查页面循环重建 |
| `FIRST_FRAME_TIMEOUT` | 20 秒未收到首帧 | 单路重试并检查设备网络 |
| `AEE_GATEWAY_CONNECT_FAILED` | Gateway 不可用 | 检查 AEE 与网络 |
| `AEE_MEDIA_CONNECT_FAILED` | Media 不可用 | 检查媒体服务 |
| `STREAM_RELEASE_UNCONFIRMED` | 单路释放 ACK 未确认 | 保留 survivor，检查客户端日志 |
| `AEE_DISCONNECT_FAILED` | 上游释放未确认 | 禁用 realtime 并检查残留连接 |
| `audio_open_failed` | 接收音频未建立 | 保持视频，关闭音频后重试 |
| `audio_release_failed` | 音频释放未确认 | 结束 session 并确认连接回落 |
| `screenshot_failed` | 浏览器本地截图失败 | 确认画面 PLAYING 后重试 |

## 5. AEE 不可用时

主 CHA liveness 不应失败。Realtime 页面会返回可理解的 upstream 错误，
session 进入 `FAILED` 或 `DEGRADED`。不要通过高频刷新 health 主动探测 AEE。

## 6. 安全禁用 realtime

1. 将部署配置中的 `CHA_V2_FEATURE_REALTIME_READONLY=false`。
2. 按正式变更流程重启/重新部署 v2 服务。
3. 确认 `/api/v2/system/features` 返回 realtime 为 false。
4. 确认 `/api/v2/realtime` 返回 feature disabled。

本仓库 RC 默认即为关闭状态。

Audio 即使已验证也保持 `CHA_V2_FEATURE_REALTIME_AUDIO=false`，只有在独立
发布审批后才允许对 Canary 用户开启。

## 7. Canary 用户隔离

Realtime 开启前必须在生产 Secret/env 中设置：

```text
CHA_V2_REALTIME_CANARY_USERS=user.one,user.two
```

用户名直接复用现有 CHA `/api/auth/session` 返回的登录用户名，比较时忽略大小写
并去除首尾空格。默认未配置或配置为空时，没有任何已登录用户可以访问 realtime。

非 Canary 用户会被以下入口拒绝：

- Realtime 页面和所有产品 API；
- Control WebSocket；
- Gateway WebSocket；
- Media WebSocket。

健康接口仍可用于运维检查，但不会返回 allowlist 内容。不要使用全局开关替代
Canary allowlist，也不要为本阶段引入新的 RBAC。

## 8. AEE Secret 配置

AEE 长期凭据只允许通过生产环境变量注入：

```text
CHA_V2_AEE_API_BASE_URL
CHA_V2_AEE_ORIGIN
CHA_V2_AEE_GATEWAY_HOST
CHA_V2_AEE_GATEWAY_PORT
CHA_V2_AEE_GATEWAY_SSL
CHA_V2_AEE_GATEWAY_HTTP_PROXY
CHA_V2_AEE_USERNAME
CHA_V2_AEE_PASSWORD
```

要求：

- 真实值不得写入 Git、RC、命令输出、Runbook、截图或日志；
- 生产 env 权限保持 `0600`，并纳入发布前备份；
- 变更后先保持 `CHA_V2_FEATURE_REALTIME_READONLY=false` 启动并检查 health；
- health 只做配置完整性判断，不主动登录 AEE；
- 只有受控 Canary 开始创建 session 时才允许执行 AEE login；
- 不通过浏览器、API、diagnostics 或 support bundle 返回 Secret。

## 9. 确认资源释放

结束会话后确认：

- `realtime_active_sessions=0`
- `realtime_active_streams=0`
- `realtime_gateway_connections=0`
- `realtime_media_connections=0`
- stream 日志最终出现 `stream_released` 或 session 出现 `session_closed`
- `runtime_state=RELEASED`

## 10. 回滚 M3

发布前必须记录上一版本 release 路径并备份环境文件。使用
`ops/rollback-v2.sh` 时必须提供：

- `CHA_V2_ROOT`
- `CHA_V2_CURRENT`
- `CHA_V2_ROLLBACK_TARGET`
- `CHA_V2_ENV_FILE`
- `CHA_V2_ENV_BACKUP`

先设置 `CHA_V2_ROLLBACK_DRY_RUN=true` 检查目标，再按变更审批执行。脚本拒绝
回滚到 release root 之外的路径。

## 11. 禁止发送给普通用户的日志

不得发送：

- AEE password 或其派生登录参数；
- 真实 Token、Authorization、Cookie；
- 完整 ConnecteInfo；
- Gateway/Media 内部地址；
- FTP/OSS credential；
- 原始服务器环境文件。

对外只提供 CHA `request_id`、内部 `error_code` 和脱敏后的处理结论。

## 12. Canary 方案

1. 只选择极少量内部测试用户，将其现有 CHA 用户名写入
   `CHA_V2_REALTIME_CANARY_USERS`，保留旧系统入口。
2. 先部署候选 release，但保持 realtime/audio 开关关闭。
3. 确认 health 中 `aee_configured=true`、`canary_configured=true`、
   `configured=true`，此检查不得主动登录 AEE。
4. 使用非 Canary 登录验证页面、API 和三个 WebSocket 均被拒绝。
5. 验证 liveness、readiness、realtime health 和 diagnostics。
6. 对每个候选设备先在 AEE 原生页面执行最小媒体 precheck：
   `mediaMonitor=opened → newConsumer → track/Canvas → first frame`。
   `online=1` 只表示设备树状态，不等于媒体可用。
7. AEE 原生 `mediaMonitor` 失败的设备标记为 `MEDIA_UNAVAILABLE` 并跳过；
   不计为 CHA failure，也不得围绕它增加 workaround。
8. 经审批后只开启 realtime，先执行 1 路，再执行 4 路；不测试 9 路。
9. 四路验证必须覆盖首帧、分辨率、track live、selective close、survivor、
   reopen、fullscreen、screenshot、session close 和完整资源释放。
10. 只有至少 6 台设备通过 AEE-native precheck 时才顺带执行 6 路生产验证。
    否则记录：
    `6-stream production verification: NOT EXECUTED — INSUFFICIENT HEALTHY MEDIA DEVICES`，
    该 evidence waiver 不阻塞 M3 首发。
11. 若 1 路和 4 路均 PASS、但 6 路未执行，则生产首发最大路数建议为 4；
    保留开发环境已验证的 6 路代码能力，未来单独完成 6 路生产容量验证后再提升。
12. 视频稳定后再单独审批 audio Canary。
13. 观察 session/stream、Gateway/Media、first-frame、release、login latency。

以下任一情况立即中止：资源不能释放；Gateway/Media 持续增长；首帧超时或
AEE 登录异常明显增长；页面持续错误；明确内存泄漏；owner 隔离失败；Token
泄漏；旧系统受影响；业务设备异常。中止时先关闭 feature flag，再执行既定
回滚。

单个设备在 AEE 原生页面同样返回 `devices is offline` 不构成平台级中止条件；
应关闭该设备 tile、确认资源释放、标记 `MEDIA_UNAVAILABLE` 后选择下一个已通过
AEE precheck 的设备。

## 13. 发布脚本

`ops/mature_m3_final_release.sh` 必须使用
`CHA_V2_VENV_PYTHON`，默认值为：

```text
/opt/jdair-cha/v2/venv/bin/python
```

候选包测试在切换 `current` 前执行。测试失败必须直接退出且不得重启服务。只有
切换完成后的启动或 health 失败才执行一次回切和一次恢复重启。每次正式发布前
必须运行：

```text
ops/mature_m3_final_release_rehearsal.sh
```

该演练只能使用临时隔离目录和 fake systemctl/curl，不得访问生产 current。
生产重试必须使用新的独立 release 目录；本 release-fix 脚本默认目录名为
`0.8.0-m3-final-rc-release-fix`，不得覆盖当前
`0.8.0-m3-final-rc`。
