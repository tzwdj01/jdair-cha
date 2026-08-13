# M2 态势看板发布记录

## 发布版本

```text
版本:  0.3.0
构建:  m2-dashboard-preview
目录:  /opt/jdair-cha/v2/releases/20260813230741-m2-dashboard-preview
```

发布制品校验：

```text
package SHA-256:      05a2187d83bd19e6c254fd4712b4d5e0237a56d1c9df62c4aac178513377a8e8
release tree SHA-256: 4165983d7d9f561387b1f0da7f35ddcace0b96eba1de576b3d8c251956521453
```

生产入口：

```text
http://cha.jdair.top/api/v2/dashboard
```

该入口是独立灰度页面，没有替换、重排或修改现有首页，原有业务页面和
所有 `/api/*` 接口保持不变。

## 本次交付

### 1. 独立态势看板

- 日间/夜间主题切换；
- 设备总数、在线率、近 3 日文件数量和存储量；
- 今日航班和今日例行任务；
- 视频记录日期趋势；
- 设备在线状态环图；
- 真实经纬度城市投影；
- 城市设备与视频覆盖表；
- 重点异常列表；
- 数据新鲜度和缓存状态；
- 城市筛选和趋势时间筛选；
- 60 秒自动刷新和手动强制刷新。

### 2. M2 新接口

```text
GET /api/v2/dashboard
GET /api/v2/dashboard/overview
GET /api/v2/dashboard/device-trend
GET /api/v2/dashboard/video-trend
GET /api/v2/dashboard/geography
GET /api/v2/dashboard/coverage
GET /api/v2/dashboard/exceptions
GET /api/v2/dashboard/freshness
```

### 3. 聚合与降级

- 仅转发浏览器现有的 CHA HttpOnly 会话 Cookie；
- M2 不接收、不保存用户密码；
- 设备、文件、航班、任务和趋势分别缓存；
- 首屏等待时间受控，慢数据源后台预热；
- 单一慢源或异常不会阻断已就绪模块；
- 上游暂时失败时允许使用最近一次成功缓存，并显示新鲜度；
- 保存有边界的设备趋势采样，不保存上游账号或令牌。

### 4. 功能开关

本次只开启：

```text
dashboard_v2=true
```

以下能力仍保持关闭：

```text
realtime_readonly=false
realtime_audio=false
realtime_control=false
account_pool_v2=false
records_v2=false
```

## 生产验收

### 自动化测试

- Python 单元测试：12 项全部通过；
- Nginx 配置校验：通过；
- v2 direct health：200；
- v2 proxied health：200；
- 旧版首页：200；
- 未登录看板 API：401；
- 独立看板页面：200；
- 所有 7 个看板数据接口：200。

### 真实会话与数据

2026-08-13 生产抽样：

| 指标 | 值 |
|---|---:|
| 纳管终端 | 56 |
| 在线设备 | 4 |
| 离线设备 | 52 |
| 在线率 | 7.1% |
| 覆盖城市 | 16 |
| 近 3 日文件 | 400 |
| 近 3 日存储量 | 70.67 GB |
| 有文件设备覆盖率 | 51.8% |
| 有文件城市覆盖率 | 75.0% |
| 今日航班 | 34 |
| 今日例行任务 | 43 |

首次冷启动时核心设备和航班数据可先返回，慢源在后台完成；最终缓存命中后，
整套 overview 接口约 0.2～0.7 秒返回。

### 视觉验收

- 1920×1080 浏览器渲染通过；
- 页面宽度与视口一致，无水平溢出；
- 16 个城市行、54 个异常行、6 个新鲜度源均渲染；
- 日间/夜间切换通过；
- 浏览器控制台无错误。

## 回滚验证

已执行：

```text
M2 -> M1 -> M2
```

回滚后 M1、旧版页面和 Nginx 全部正常；随后重新发布 M2，最终生产版本为：

```text
/opt/jdair-cha/v2/releases/20260813230741-m2-dashboard-preview
```

M2 发布目录自带：

```text
/opt/jdair-cha/v2/releases/20260813230741-m2-dashboard-preview/rollback-to-previous.sh
```

此外，M2 改造前备份目录也保留完整恢复脚本。

## 已知边界

1. M2 文件卡片固定使用近 3 日口径；顶部时间筛选只影响文件日期趋势；
2. 城市筛选影响设备、地理、覆盖和异常，航班/例行任务仍使用今日全局口径；
3. 航班/任务与视频记录的精确关联覆盖率尚未启用，避免每次首屏全量关联扫描；
4. 当前缓存为单实例进程缓存，后续多实例部署时应迁移到 Redis；
5. 地理态势使用设备经纬度投影，不依赖第三方在线地图；
6. 实时视频能力属于 M3，不包含在本次 M2 发布。
