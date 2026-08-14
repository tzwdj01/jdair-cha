# M3 Realtime Release Candidate

版本：`0.7.0`

构建：`m3-realtime-rc`

## 发布边界

- Model A 保持不变；
- 仅支持 1 路和最多 4 路；
- 6/9 路、音频、控制、AccountPool 未启用；
- 仓库 `FEATURES.env` 中 realtime 生产开关保持关闭；
- 本 RC 仅具备进入 staging/canary 的条件，不授权 full production。

## 发布资产

- 构建：`python ops/mature_m3_build_package.py`
- 包：`mature-modernization/jdair-cha-v2-m3-rc.tar.gz`
- Manifest：`m3-rc-manifest.json`
- 包结果：`m3-rc-package-result.json`
- 生产前备份：`ops/mature_m3_incremental_backup.sh`
- 可配置回滚：`ops/rollback-v2.sh`
- 隔离回滚演练：`ops/mature_m3_rc_rollback_rehearsal.sh`

`mature_m3_incremental_backup.sh` 仍是生产路径脚本，会停止服务并读取
systemd/Nginx/current/env，因此本阶段只审查、未执行。`rollback-v2.sh` 支持
configurable root 和 dry-run，并拒绝 release root 之外的目标。

## 未来 staging/canary 步骤

1. 完成 pre-release checklist。
2. 运行生产前完整备份并核验 archive SHA-256。
3. 将 RC 解压到新 release 目录，不覆盖旧 release。
4. 使用独立 staging 配置，保持音频、控制和 AccountPool 关闭。
5. 先执行 liveness、application readiness、realtime health。
6. 仅在审批后启用 staging/canary realtime。
7. 完成短时 1/4 路回归并观察 diagnostics。
8. 若 active counters 无法回落或 release failure 增长，立即关闭开关并回滚。

## 回滚成功标准

- current 恢复上一 release；
- VERSION/BUILD 恢复；
- env SHA-256 恢复；
- realtime 开关恢复为 false；
- liveness/readiness 恢复；
- active sessions/streams/Gateway/Media 均为零。

本阶段的回滚演练全部在临时 release tree 内执行，没有访问生产 current、
systemd、Nginx、生产 env 或数据库。
