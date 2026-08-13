# M3.1 单路实时视频会话

## 链路与分层

M3.1 继续复用已验证的 AEE 原生链路：

`AEE Token → Gateway WebSocket → mcs8_admin → openVideo → MediaStream`

CHA 新增的职责仅为会话编排、状态、心跳、释放和同源
WebSocket 中继：

`浏览器 → CHA Realtime API/Session Manager → AEE Adapter → AEE`

没有新增转码、拉流中转或替换 WebRTC 媒体层。

## 生命周期

1. 已登录 CHA 的用户创建 `session_id`；
2. 服务端 AEE Adapter 使用环境变量中的凭据登录，Token 仅留在内存；
3. 单个 session 最多创建一个 video stream；
4. 浏览器 SDK 通过 CHA 同源 Gateway/Media WebSocket 中继加入
   `mcs8_admin` 并调用 `openVideo`；
5. 浏览器通过 control WebSocket 上报首帧和播放状态；
6. 删除 stream 时，服务端命令浏览器执行 `closeVideo`。未收到确认时，
   服务端强制断开该 session 的 AEE 媒体和 Gateway 连接；
7. 关闭 session 时执行 SDK `close()`，服务端同时关闭媒体和 Gateway
   连接并清理 CHA session；
8. session 心跳过期后由后台清理任务执行同样的强制关闭。

control、Gateway 或 Media WebSocket 非预期断开时，Session Manager 将会话
标记为 `DEGRADED` 并强制断开剩余 AEE 连接，避免继续留下媒体房间或
后台 relay。

关闭接口具备幂等性；已关闭 session 在短暂保留期内仍可查询和重复关闭。

## 安全边界

- 浏览器不接收 AEE 用户名、密码、登录 Token 或媒体 Token；
- Adapter 截获 AEE `ConnecteInfo`，保存真实媒体参数，并仅返回 CHA
  同源代理地址和无效占位 Token；
- 同源中继只允许接收方向 WebRTC、`openVideo`/`closeVideo` 所需命令，
  并绑定当前选择的设备；音频、回放、控制和发送媒体命令会被拒绝；
- WebSocket 代理使用只在对应 session 路径有效的 `HttpOnly` lease
  Cookie；
- Token、Authorization、Cookie 和密码禁止写入结构化日志；
- 生产环境凭据只允许进入 `/etc/jdair-cha/v2.env` 等受控配置，不进入
  Git 或发布文档。

## 功能开关与限制

- 提交的 `FEATURES.env` 继续保持 `realtime_readonly=false`；
- `realtime_audio=false`、`realtime_control=false`；
- 仅支持一 session 一路视频；
- 没有多账号池、自动重连、4/6/9 布局、截图、对讲、录像或云台；
- session 当前为进程内状态，服务重启会强制失效，后续阶段再引入跨进程
  持久化或账号池。

## 基线工具

- `ops/mature_m3_aee_baseline.py`：JSON 结果、浏览器日志、服务器日志分别
  保存，统一 UTF-8；登录用户名、密码和 CHA 地址均通过环境变量或参数
  注入；
- `ops/mature_m3_incremental_backup.sh`：不含服务器固定 IP、Token 或密码，
  所有可变路径和服务名通过环境变量覆盖；
- `docs/M3_REALTIME_BASELINE_SAMPLE.json`：仅保留脱敏结构样例。

浏览器 SDK 固化自已验证 PoC 的 `mcs8Client.js`，来源和最小兼容修改记录
在 `app/static/vendor/README.md`。
