# CHA 成熟化改造 M0 生产回滚基线

## 基线信息

- 执行日期：2026-08-13
- 改造前生产版本：`/opt/jdair-cha/releases/20260812212342-layout-redesign-phase5`
- 改造前主程序 SHA-256：`517bb0f26e7f56e79291d6391160c84df9a578288ce0cf545d82363e98d4afc2`
- 旧服务：`jdair-cha.service`
- 旧服务端口：`127.0.0.1:8790`

## 最终有效备份

- 备份目录：`/opt/jdair-cha/backups/20260813-205421-before-mature-modernization`
- 备份归档：`/opt/jdair-cha/backups/jdair-cha-before-mature-modernization-20260813-205421.tar.gz`
- 归档大小：17,222,728 bytes
- 归档条目：482
- 归档 SHA-256：`a33ca7be8d4168fe54bdc599346e10573d6601d1dca6dceaa22cf3616c425610`
- 回滚脚本：`/opt/jdair-cha/backups/20260813-205421-before-mature-modernization/rollback.sh`

归档已经下载到异地本地目录，服务器副本和本地副本 SHA-256 完全一致。完整归档可能包含运行配置和敏感数据，因此不上传 GitHub。

## 备份范围

1. `/opt/jdair-cha/releases` 全部历史发布版本；
2. 当前生产软链接及当前程序；
3. Git 元数据；
4. systemd 服务配置；
5. Nginx 站点配置的真实文件内容；
6. 设备目录缓存、离线地图、运行配置等随发布目录保存的数据；
7. 文件清单、权限、所有者和 SHA-256 校验清单；
8. 服务状态、监听端口、磁盘信息和 Nginx 完整配置快照；
9. 自动回滚脚本。

## 验证结果

- 归档 SHA-256：通过；
- tar 归档读取：通过；
- Nginx 备份文件不是软链接：通过；
- 备份 Nginx 与改造前在线配置 SHA-256 一致：通过；
- 备份主程序与改造前在线程序 SHA-256 一致：通过；
- 回滚脚本 Bash 语法：通过；
- 回滚目标目录和主程序：存在；
- 回滚配置不包含 v2 路由：通过；
- 旧服务状态：`active`；
- 旧服务 HTTP：`200`。

## 快速回滚

仅在确认需要放弃 v2 并恢复到本基线时，在服务器执行：

```bash
bash /opt/jdair-cha/backups/20260813-205421-before-mature-modernization/rollback.sh
```

该脚本会：

1. 停止并停用 `jdair-cha-v2.service`；
2. 恢复历史发布目录；
3. 将 `/opt/jdair-cha/current` 指回 Phase 5；
4. 恢复改造前 systemd 和 Nginx 配置；
5. 重载 Nginx 并重启旧服务；
6. 验证旧服务为 `active` 且根页面返回 HTTP 200。

## 说明

首次候选部署演练暴露出 Nginx 软链接备份和服务器在线依赖下载两个问题。生产旧页面始终可用，随后已恢复原配置，并修正为：

- Nginx 配置解引用后保存真实内容；
- v2 依赖使用 Linux/Python 3.12 离线 wheel 包；
- 部署失败自动恢复原 Nginx、停止 v2 并清理候选发布；
- 重新生成并验证本文件记录的最终回滚基线。
