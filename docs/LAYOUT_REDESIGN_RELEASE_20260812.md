# cha.jdair.top 页面布局改造发布记录

- 发布时间（Asia/Shanghai）：2026-08-12 15:13
- GitHub 分支：`codex/layout-redesign-20260812`
- 生产发布目录：`/opt/jdair-cha/releases/20260812151318-layout-redesign`
- 当前软链接：`/opt/jdair-cha/current`
- 新主程序 SHA-256：`17bec5745733cbc193c5c36bfb70bc3e635f6bd4f01d1facfdc138adadf27c06`
- 改造前发布目录：`/opt/jdair-cha/releases/20260628220754`
- 改造前主程序 SHA-256：`0abc3c0c29a14d3d9aa851998b9441d3b7db5a83363ef998691dc1a37abde057`

## 改造内容

1. 将顶部区域重排为品牌区、主功能导航和系统操作区。
2. 将设备侧栏入口并入顶部操作区，强化设备状态、搜索、筛选和分组层级。
3. 为监察工作台、指挥调度、航班动态、例行任务增加统一的模块标题层。
4. 将查询条件统一为紧凑的查询工具栏，减少散乱控件带来的视觉跳跃。
5. 使用深色航空监察主题统一面板、表格、状态、登录页和响应式布局。
6. 保留原有全部 DOM ID、事件处理函数、API 路径和后端业务实现。

## 验证结果

- Python 语法编译：通过
- 原有 JavaScript 业务代码块：未修改
- 原有 DOM ID：全部保留
- `/api/login`：HTTP 200
- `/api/auth/session`：HTTP 200
- `/api/dashboard`：HTTP 200
- `/api/devices`：HTTP 200
- `/api/summary`：HTTP 200
- 登录后设备指标：56 台设备、2 台在线、56 台有定位
- 登录后工作台指标：56 台设备、2 台在线、54 台离线、18 个覆盖城市
- 指挥调度：地图初始化成功
- 航班动态：列表加载 20 条
- 例行任务：列表加载 20 条
- `jdair-cha.service`：`active`

在线设备数量和覆盖城市数量来自实时数据，可能随上游状态变化。

## 回滚

```bash
ln -sfn /opt/jdair-cha/releases/20260628220754 /opt/jdair-cha/current
systemctl restart jdair-cha.service
systemctl is-active jdair-cha.service
```

如需恢复持久化文件，使用改造前备份：

`/opt/jdair-cha/backups/jdair-cha-before-layout-redesign-20260812-064453.tar.gz`

备份 SHA-256：

`9bf2e684b659ef90c24a274e1cfbde340003580f4aa30897d1e60c53270c3ae2`

> 安全说明：运行配置、登录凭据、会话令牌、缓存数据、日志和完整备份归档均未提交到公共仓库。
