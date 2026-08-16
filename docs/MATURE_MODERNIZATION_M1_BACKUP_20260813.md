# CHA 成熟化改造 M1 增量回滚基线

## 目的

该增量备份用于把 v2 从 M1 或后续版本恢复到已验证的 M0 基础版本。旧 Phase 5 的完整系统回滚仍使用 M0 完整回滚包，两者相互独立。

## 备份信息

- 执行日期：2026-08-13
- 备份前旧生产版本：`/opt/jdair-cha/releases/20260812212342-layout-redesign-phase5`
- 备份前 v2 版本：`/opt/jdair-cha/v2/releases/20260813211851-m0-foundation`
- 备份目录：`/opt/jdair-cha/backups/20260813-212719-before-m1-legacy-adapter`
- 备份归档：`/opt/jdair-cha/backups/jdair-cha-before-m1-legacy-adapter-20260813-212719.tar.gz`
- 归档大小：10,559,198 bytes
- 归档条目：91
- 归档 SHA-256：`7a82745f4097eec3b05ac985707546c5fb7deec172e2a321b2c2202e88602f8f`
- 回滚脚本：`/opt/jdair-cha/backups/20260813-212719-before-m1-legacy-adapter/rollback-v2.sh`

完整归档已经下载到本地异地目录，服务器副本和本地副本 SHA-256 完全一致。完整归档不上传 GitHub。

## 备份范围

1. v2 全部发布目录；
2. v2 当前软链接；
3. `jdair-cha-v2.service`；
4. Nginx 站点配置真实内容；
5. v2 环境文件；
6. 文件清单和 SHA-256 校验清单；
7. 专用 v2 回滚脚本。

## 增量回滚

```bash
bash /opt/jdair-cha/backups/20260813-212719-before-m1-legacy-adapter/rollback-v2.sh
```

该脚本只回滚 v2：

- 恢复 M0 v2 发布目录和软链接；
- 恢复 v2 systemd、环境和 Nginx 配置；
- 重启 v2 服务；
- 验证旧服务、v2 服务以及两个本地 HTTP 健康检查。

## 验证

- tar 归档：通过；
- 服务器归档 SHA-256：通过；
- 本地异地副本 SHA-256：通过；
- Nginx 配置为真实文件：通过；
- v2 环境文件为真实文件：通过；
- 旧服务和 M0 v2 在备份后均为 `active`。
