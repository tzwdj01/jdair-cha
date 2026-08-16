# CHA 成熟化改造 M1 只读适配层发布记录

## 发布信息

- 发布日期：2026-08-13
- v2 版本：`0.2.0`
- 构建标识：`m1-legacy-adapter`
- 发布目录：`/opt/jdair-cha/v2/releases/20260813215638-m1-legacy-adapter`
- 上一 v2 版本：`/opt/jdair-cha/v2/releases/20260813211851-m0-foundation`
- 旧生产版本保持：`/opt/jdair-cha/releases/20260812212342-layout-redesign-phase5`

## 本次完成

1. 新增严格白名单的旧服务只读适配器；
2. 新增旧服务健康和响应延迟检查；
3. 新增首个 v2 看板接口契约；
4. 使用当前浏览器 CHA Cookie 访问旧服务，不复制或保存登录密码；
5. 看板接口受 `dashboard_v2` 功能开关保护；
6. 默认开关关闭，不改变现有页面；
7. 新增版本级增量回退脚本；
8. 每个发布目录自带 `VERSION` 和 `BUILD`，回退后版本信息保持一致；
9. 部署复用锁定的离线依赖并执行 `pip check`；
10. 部署时无条件重启独立 v2 服务，确保加载当前软链接代码。

## 新增接口

```text
GET /api/v2/health/upstreams
GET /api/v2/dashboard/overview
```

`/api/v2/dashboard/overview` 当前因 `dashboard_v2=false` 返回 HTTP 404 和 `feature_disabled`，不会被现有用户页面调用。

## 验证结果

- 本地单元测试：6项通过；
- 本地 HTTP 契约测试：通过；
- 服务器依赖完整性 `pip check`：通过；
- 服务器单元测试：6项通过；
- 旧服务：`active`；
- v2 服务：`active`；
- 旧主页：HTTP 200；
- v2 健康接口：HTTP 200；
- v2 上游健康接口：HTTP 200；
- v2 版本接口：HTTP 200；
- v2 看板接口：HTTP 404，符合功能开关关闭预期；
- v2 OpenAPI：HTTP 200；
- 公网域名访问：通过。

## 实际增量回退演练

已执行：

1. 从 M1 执行发布级回退脚本；
2. v2 成功切回 M0；
3. M0 版本接口返回 `0.1.0 / m0-foundation`；
4. M0 不存在上游健康接口，返回 HTTP 404；
5. 旧服务全程保持 `active`；
6. 重新将 v2 切回 M1；
7. M1 版本恢复为 `0.2.0 / m1-legacy-adapter`；
8. 上游健康接口恢复 HTTP 200；
9. 看板接口仍因开关关闭返回 HTTP 404。

增量回退演练结果：**通过**。

## 回滚入口

### 回到上一 v2 版本

```bash
bash /opt/jdair-cha/v2/releases/20260813215638-m1-legacy-adapter/rollback-to-previous.sh
```

### 使用 M1 前增量备份恢复

```bash
bash /opt/jdair-cha/backups/20260813-212719-before-m1-legacy-adapter/rollback-v2.sh
```

### 完全放弃成熟化改造、恢复旧 Phase 5

```bash
bash /opt/jdair-cha/backups/20260813-205421-before-mature-modernization/rollback.sh
```

## 下一步

下一阶段将在保持功能开关关闭的情况下继续：

1. 定义看板指标口径；
2. 增加设备、视频、航班和任务聚合接口；
3. 增加缓存和数据新鲜度；
4. 制作态势总览新页面；
5. 仅对指定灰度用户启用 `dashboard_v2`。
