# CHA 成熟化改造 M0 基础版本发布记录

## 发布结果

- 发布日期：2026-08-13
- v2 版本：`0.1.0`
- 构建标识：`m0-foundation`
- v2 发布目录：`/opt/jdair-cha/v2/releases/20260813211851-m0-foundation`
- v2 服务：`jdair-cha-v2.service`
- v2 内部端口：`127.0.0.1:8791`
- 旧生产版本：保持 `/opt/jdair-cha/releases/20260812212342-layout-redesign-phase5`
- 旧生产接口和页面：未替换

## 本次完成

1. 建立独立 FastAPI 模块化服务；
2. 建立 `/api/v2/` 和 `/ws/v2/` Nginx 分流；
3. 增加统一响应信封、请求 ID 和响应耗时；
4. 增加基础安全响应头；
5. 增加健康、就绪、版本、功能开关和 OpenAPI 接口；
6. 建立功能开关配置；
7. 业务功能开关默认全部关闭；
8. 建立独立 v2 发布目录、虚拟环境、systemd 服务和环境文件；
9. 使用锁定的 Linux/Python 3.12 离线依赖；
10. 保留旧服务和全部旧接口。

## 当前 v2 接口

```text
GET /api/v2/health
GET /api/v2/health/live
GET /api/v2/health/ready
GET /api/v2/system/version
GET /api/v2/system/features
GET /api/v2/openapi.json
GET /api/v2/docs
```

## 功能开关状态

以下功能均为关闭状态：

```text
dashboard_v2=false
realtime_readonly=false
realtime_audio=false
realtime_control=false
account_pool_v2=false
records_v2=false
```

因此，本次发布只建立工程底座，不改变用户当前看到的页面和业务行为。

## 生产验证

- `jdair-cha.service`：`active`
- `jdair-cha-v2.service`：`active`
- 旧服务直连：HTTP 200
- 旧服务 Nginx 代理：HTTP 200
- 旧页面代理内容与直连内容：完全一致
- v2 直连健康接口：HTTP 200
- v2 Nginx 代理健康接口：HTTP 200
- v2 就绪接口：HTTP 200
- v2 版本接口：HTTP 200
- v2 功能开关接口：HTTP 200
- v2 OpenAPI：HTTP 200
- Nginx 配置检查：通过
- v2 环境文件权限：`600`
- 本机通过公网域名访问旧主页和 v2 接口：HTTP 200
- 最终回滚演练：通过；回滚后旧 Phase 5 恢复，v2 路由移除，旧站 HTTP 200
- 回滚演练后的 v2 离线重部署：通过

## 下一阶段

后续将在 v2 底座上继续建设：

1. 上游适配器和统一错误模型；
2. 看板指标定义、缓存和数据新鲜度；
3. `dashboard_v2` 只读接口；
4. 多账号池模型；
5. 单路实时视频会话 PoC；
6. 通过功能开关按用户灰度开放。

在任何后续生产修改前，继续执行增量发布备份；需要完全放弃 v2 时使用 M0 回滚脚本。
