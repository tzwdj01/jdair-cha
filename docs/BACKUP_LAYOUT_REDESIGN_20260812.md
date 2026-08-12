# cha.jdair.top 页面布局改造前备份记录

- 执行时间（Asia/Shanghai）：2026-08-12 14:44–14:46
- 改造范围：仅页面布局、视觉排版和既有操作入口重组；接口、数据字段和业务逻辑不变
- 服务器备份目录：`/opt/jdair-cha/backups/20260812-064453-before-layout-redesign`
- 服务器归档：`/opt/jdair-cha/backups/jdair-cha-before-layout-redesign-20260812-064453.tar.gz`
- 归档大小：2,593,252 bytes
- SHA-256：`9bf2e684b659ef90c24a274e1cfbde340003580f4aa30897d1e60c53270c3ae2`
- 异地副本校验：通过（服务器端与本地副本哈希一致）
- 改造前发布版本：`/opt/jdair-cha/releases/20260628220754`
- 改造前主程序 SHA-256：`0abc3c0c29a14d3d9aa851998b9441d3b7db5a83363ef998691dc1a37abde057`
- 服务恢复验证：`jdair-cha.service` 为 `active`

## 备份范围

1. `/opt/jdair-cha/releases` 全部发布版本和运行数据
2. Git 元数据及部署软链接目标
3. `device_catalog_cache.json`、`device_catalog_sdk_export.json`
4. `inspection_records.json`（存在时包含）
5. `runtime/LocalConfig.xml`、运行日志及离线地图资源
6. `/etc/systemd/system/jdair-cha.service`
7. `/etc/nginx/sites-enabled/jdair-cha.conf`
8. 文件清单、权限、SHA-256 校验清单和归档目录清单

## 未纳入归档的内容

- 内存中的临时登录会话（服务重启后自然失效）
- 由上游 MCS8 接口持有的视频、GPS、航班和例行任务源数据

## 快速回滚

1. 将 `/opt/jdair-cha/current` 重新指向 `/opt/jdair-cha/releases/20260628220754`
2. 从上述归档恢复发生变化的持久化文件（如有）
3. 重启 `jdair-cha.service`
4. 验证登录、设备、视频记录、地图、航班和例行任务

> 安全说明：此记录不包含服务器密码、登录密码、会话令牌、`LocalConfig.xml` 内容或运行日志内容；完整归档不上传公共 GitHub 仓库。
