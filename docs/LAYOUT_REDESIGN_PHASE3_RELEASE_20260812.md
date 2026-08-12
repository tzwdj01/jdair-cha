# cha.jdair.top 页面布局改造（第三阶段）发布记录

- 实施日期（Asia/Shanghai）：2026-08-12
- GitHub 分支：`codex/layout-redesign-20260812`
- 生产发布目录：`/opt/jdair-cha/releases/20260812193050-layout-redesign-phase3`
- 当前软链接：`/opt/jdair-cha/current`
- 主程序 SHA-256：`cb15037e73a4a11daa195fb32125e46283272f68fab24d32f3ee5795a80b6e91`
- 主程序大小：`248,304` 字节
- 上一稳定版本：`/opt/jdair-cha/releases/20260812173330-layout-redesign-phase2`

## 本次改造内容

1. 指挥调度的“调度状态表”取消固定半屏高度，表格随全部设备记录平铺展开；仍保留横向溢出保护。
2. 视频记录查询移除“文件类型”列，将表格缩减为 8 列并缩小字体；扩大“参考信息”列，压缩设备、时间等辅助列，操作按钮保持横向排列。
3. 原“标注”操作改为“复制名称”，复制当前记录的完整文件名称；浏览器禁止自动剪贴板时，打开已全选文件名的手动复制窗口。
4. 辅助查询右侧新增“系统功能与版本记录”模块，集中展示当前功能清单和基础版本、第一阶段、第二阶段、第三阶段变更记录。
5. 本次只调整前端页面布局与交互方式，未新增或改造后端接口、数据结构及业务处理逻辑。

## 数据备份与恢复点

- 改造前服务器备份目录：`/opt/jdair-cha/backups/20260812-162937-before-layout-redesign-phase2`
- 改造前服务器备份归档：`/opt/jdair-cha/backups/jdair-cha-before-layout-redesign-phase2-20260812-162937.tar.gz`
- 备份 SHA-256：`5496fb64da2d7e3ad5c25dd2be5ddcb5219e56c8527b194606adb1210389c6cd`

> 完整备份含运行数据和配置，不上传到公共 GitHub；仓库仅记录备份路径、校验值和恢复说明。

## 验证结果

- Python 语法编译：通过。
- 内嵌 JavaScript 语法检查：通过。
- 生产服务：`jdair-cha.service` 状态为 `active`。
- 本机服务根页面：HTTP `200`。
- 实际登录：成功，数据会话状态正常。
- 设备、概览、记录、航班、例行任务相关接口：HTTP `200`。
- 调度状态表：56 行，容器 `max-height: none`，内容高度约 `3028px`，不再限制为半屏。
- 视频记录表：8 列、25 行、字体 `11.5px`；“文件类型”列已移除，“参考信息”列明显加宽。
- 操作列：“高清播放”“添加”“复制名称”同一行横向排列。
- 复制名称：HTTP 页面下浏览器不允许自动剪贴板时，手动复制弹窗正常打开，文件名称已全选。
- 辅助查询：右侧功能与版本模块正常显示，包含 6 项功能介绍和 4 条版本记录。

## 快速回滚

回滚到第三阶段前的稳定版本：

```bash
ln -sfn /opt/jdair-cha/releases/20260812173330-layout-redesign-phase2 /opt/jdair-cha/current
systemctl restart jdair-cha.service
systemctl is-active jdair-cha.service
```

如需恢复运行数据或服务器配置，使用上述完整备份归档，并先核验 SHA-256。
