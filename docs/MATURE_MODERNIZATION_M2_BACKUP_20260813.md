# M2 改造前备份记录

## 备份时间

- 2026-08-13 22:30:30（Asia/Shanghai）
- 用途：M2 态势看板实施前恢复点

## 备份对象

- M1 v2 全部 releases；
- `/opt/jdair-cha/v2/current`；
- `jdair-cha-v2.service`；
- Nginx 站点配置；
- `/etc/jdair-cha/v2.env`；
- 备份内文件级 SHA-256 清单；
- 一键恢复脚本。

旧版生产页面仍由以下版本提供：

```text
/opt/jdair-cha/releases/20260812212342-layout-redesign-phase5
```

M2 实施前 v2 目标：

```text
/opt/jdair-cha/v2/releases/20260813215638-m1-legacy-adapter
```

## 备份位置

服务器目录：

```text
/opt/jdair-cha/backups/20260813-223030-before-m2-dashboard
```

服务器压缩包：

```text
/opt/jdair-cha/backups/jdair-cha-before-m2-dashboard-20260813-223030.tar.gz
```

恢复脚本：

```text
/opt/jdair-cha/backups/20260813-223030-before-m2-dashboard/rollback-v2.sh
```

## 校验

```text
SHA-256: bd70a0c95defdd10e8f397cda894c27861d89977f6eca7e3e519820bd4b07db3
大小:    10,581,339 bytes
条目:    119
```

压缩包已下载到本地离线备份目录，服务器与本地计算的 SHA-256 一致。
压缩包本体没有提交到 GitHub，避免仓库承载生产备份和运行配置。

## 备份完成后的生产状态

- `jdair-cha.service`: active；
- `jdair-cha-v2.service`: active；
- 旧站点 HTTP: 200；
- v2 health HTTP: 200；
- M1 版本：`0.2.0 / m1-legacy-adapter`；
- `dashboard_v2`: false。

## 回滚能力

恢复脚本会还原：

1. M1 v2 release 和 current 链接；
2. v2 systemd 单元；
3. v2 生产环境配置；
4. Nginx 站点配置；
5. v2 与旧版服务运行状态。

M2 发布后已经执行实际回滚演练，确认恢复到 M1 后：

- M1 版本恢复为 `0.2.0`；
- `dashboard_v2` 恢复为 false；
- M2 看板接口返回 404；
- 旧版页面和 v2 健康检查均返回 200。
