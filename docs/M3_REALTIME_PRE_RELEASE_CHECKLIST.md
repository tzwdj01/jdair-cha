# M3 Realtime Pre-release Checklist

## 代码与边界

- [ ] `VERSION`、`BUILD` 与 RC 计划一致
- [ ] Model A 未改变
- [ ] 最大 streams 仍为 4
- [ ] 没有 6/9 路入口
- [ ] `realtime_audio=false`
- [ ] `realtime_control=false`
- [ ] `account_pool=false`

## 测试

- [ ] 完整 backend tests PASS
- [ ] Python compileall PASS
- [ ] 所有 JavaScript syntax PASS
- [ ] M3.2B 浏览器验收 PASS
- [ ] M3.2C browser churn PASS
- [ ] session churn/timeout/shutdown PASS
- [ ] package 解压后完整测试 PASS

## 安全

- [ ] 未登录 API 被拒绝
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
- [ ] 生产 env 已另行备份（真正发布时）
- [ ] 生产数据/当前 release 已备份（真正发布时）
- [ ] rollback target 已记录
- [ ] rollback dry-run PASS
- [ ] isolated rollback rehearsal PASS
- [ ] 未在生产 current 上执行演练

## 健康与真实验证

- [ ] liveness PASS
- [ ] application readiness PASS
- [ ] realtime health PASS
- [ ] M3.2B 真实 4 路 × 600 秒证据仍有效
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
