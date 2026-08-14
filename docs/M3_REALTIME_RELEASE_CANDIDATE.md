# M3 Realtime Release Candidate

版本：`0.8.0`

构建：`m3-final-rc`

## 发布边界

- Model A 保持不变；
- 支持 1～6 路，正式布局为 1、2×2 和 3×2；
- receive-only audio 和本地截图已实现；
- 9 路未验证、不显示；控制和 AccountPool 未实现；
- 仓库 `FEATURES.env` 中 realtime 生产开关保持关闭；
- audio 生产开关也保持关闭；
- 本 RC 具备进入受控生产 Canary 的技术条件，但不授权自动发布。

## 发布资产

- 构建：`python ops/mature_m3_build_package.py`
- 包：`mature-modernization/jdair-cha-v2-m3-final-rc.tar.gz`
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
4. 仅使用与生产 current、端口、env、systemd 完全隔离的 staging；无法证明
   隔离时不部署。
5. 先执行 liveness、application readiness、realtime health。
6. 仅在审批后启用 staging/canary realtime。
7. 完成短时 1/4/6 路回归并观察 diagnostics。
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

## 首发功能开关

```text
CHA_V2_FEATURE_REALTIME_READONLY=false
CHA_V2_FEATURE_REALTIME_AUDIO=false
CHA_V2_FEATURE_REALTIME_CONTROL=false
CHA_V2_FEATURE_ACCOUNT_POOL_V2=false
CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION=6
```

真正 Canary 时只按审批逐项开启，不能通过发布包自行改变生产 env。
