# M3 Realtime Pre-release Checklist

## 代码与边界

- [ ] `VERSION`、`BUILD` 与 RC 计划一致
- [ ] Model A 未改变
- [ ] 代码保留 development validated stream limit 6
- [ ] 本轮 Production Gate 为 1 路和 4 路
- [ ] 有 1/4/6 路入口且没有 9 路入口
- [ ] `realtime_audio=false`
- [ ] `realtime_control=false`
- [ ] `account_pool=false`

## 测试

- [ ] 完整 backend tests PASS
- [ ] Python compileall PASS
- [ ] 所有 JavaScript syntax PASS
- [ ] M3 Final 六路浏览器验收 PASS
- [ ] 20 轮 browser churn PASS
- [ ] 200 session lifecycle churn PASS
- [ ] audio receive-only 和 local screenshot PASS
- [ ] session churn/timeout/shutdown PASS
- [ ] package 解压后完整测试 PASS

## 安全

- [ ] 未登录 API 被拒绝
- [ ] `CHA_V2_REALTIME_CANARY_USERS` 已配置为获批测试用户
- [ ] allowlist 为空时所有已登录用户仍被拒绝
- [ ] 非 Canary 用户的 Realtime 页面/API 被拒绝
- [ ] 非 Canary 用户的 Control/Gateway/Media WebSocket 全部被拒绝
- [ ] session owner 隔离 PASS
- [ ] Control/Gateway/Media Origin 校验 PASS
- [ ] lease expiry 和 CLOSED replay PASS
- [ ] HTTPS Cookie 包含 Secure、HttpOnly、SameSite
- [ ] diagnostics 需要认证且无敏感字段
- [ ] Git diff、包、日志完成 secret scan

## 可观测性

- [ ] active session/stream gauges 可读
- [ ] Gateway/Media connection gauges 可读
- [ ] timeout/release/abnormal counters 可读
- [ ] latency duration summaries 可读
- [ ] session_id → stream_id → device_id 日志链完整
- [ ] `request_id` 可从 API 响应获取

## 配置、备份与回滚

- [ ] `.env.example` 已更新且无真实凭据
- [ ] AEE Secret 仅存在于生产 env/Secret 管理，不在 Git、RC 或日志中
- [ ] env 文件权限为 `0600`
- [ ] health 可区分 enabled、AEE configured、Canary configured
- [ ] health 检查不主动登录 AEE
- [ ] 生产 env 已另行备份（真正发布时）
- [ ] 生产数据/当前 release 已备份（真正发布时）
- [ ] rollback target 已记录
- [ ] rollback dry-run PASS
- [ ] isolated rollback rehearsal PASS
- [ ] isolated final release rehearsal PASS
- [ ] release 使用 production V2 venv Python
- [ ] candidate test failure 在切换 current 前 fail-fast
- [ ] health failure 只执行一次回切和一次恢复重启
- [ ] 未在生产 current 上执行演练

## 健康与真实验证

- [ ] liveness PASS
- [ ] application readiness PASS
- [ ] realtime health PASS
- [ ] Canary 候选设备先通过 AEE-native
      `mediaMonitor=opened/newConsumer/first frame` precheck
- [ ] 1 路 Production Canary PASS
- [ ] 4 路 Production Canary 首帧、survivor、reopen、截图和释放 PASS
- [ ] Fullscreen 若缺少真实用户激活证据，必须保持
      `COMPLETED / UNVERIFIED`；不得误标 PASS
- [ ] 若不足 6 台健康媒体设备，记录 6 路 evidence waiver，而不是使用异常设备
- [ ] 若 6 路未执行，生产首发最大路数建议为 4
- [ ] 9 路明确标记 NOT TESTED 且 UI 不显示
- [ ] 若 Adapter/relay 有行为修改，完成必要短回归

## 发布包与 Git

- [ ] RC archive 构建成功
- [ ] archive manifest 已生成
- [ ] SHA-256 已记录
- [ ] archive 不含 env/log/png/result/backup/pyc/venv
- [ ] 功能开关仍关闭
- [ ] Git 工作区 clean
- [ ] RC 分支已 push
- [ ] 未 merge
- [ ] 未打正式 release tag

只有全部勾选并完成正式变更审批后，才可进入 staging/canary；本清单不授权直接
发布 full production。

## M3 Closure Note — 2026-08-15

项目负责人已批准：

`M3 CLOSED / ACCEPTED WITH EVIDENCE WAIVER`

Fullscreen 保持：

`COMPLETED / UNVERIFIED`

该 waiver 仅覆盖普通用户 Chrome 的
`enter fullscreen → exit fullscreen → playback continues`
人工证据。原因是生产自动化/Computer Use 环境无法可靠提供并确认 Fullscreen API
所需的瞬时 real-user activation，且没有确认的 CHA 产品缺陷。

该项移动到 `POST-M3 OPERATIONAL FOLLOW-UP`，不再重复执行自动化 Canary，也不
阻塞 M4。此记录不把 Fullscreen 标记为 PASS。

M3 关账时 Production Realtime、Audio、Control、AccountPool 均为 `false`；
V2 active、`NRestarts=0`、liveness/readiness PASS。不得因本清单自动进入 M4。
