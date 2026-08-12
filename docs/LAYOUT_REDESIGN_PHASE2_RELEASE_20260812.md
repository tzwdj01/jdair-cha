# cha.jdair.top 页面布局改造（第二阶段）发布记录

- 实施日期（Asia/Shanghai）：2026-08-12
- GitHub 分支：`codex/layout-redesign-20260812`
- 生产发布目录：`/opt/jdair-cha/releases/20260812173330-layout-redesign-phase2`
- 当前软链接：`/opt/jdair-cha/current`
- 主程序 SHA-256：`1931d1b5c2a88a3c245fc1a6c1847fd1964e25c82ef30bb888e4d453b7345553`
- 上一稳定版本：`/opt/jdair-cha/releases/20260812151318-layout-redesign`

## 改造内容

1. 增加日间/夜间主题切换，默认保留当前夜间风格，选择结果保存在浏览器本地。
2. 主页面移除常驻视频播放区；视频改为居中弹窗播放，关闭仅隐藏并暂停，播放窗口与列表不会因关闭自动清空。
3. 保留多视频同时播放和原有网格排列：1 路单画面、2–4 路双列、更多视频三列。
4. 视频记录表改为固定默认行高；参考信息默认折叠，可逐行展开/收起；高清播放、添加、标注保持横向排列。
5. 指挥调度增加左侧标签：设备定位、调度状态表；只显示当前所选内容。
6. 航班动态与例行任务合并为顶部“辅助查询”，通过内部左侧标签切换，避免上下或并列同时显示。
7. 未新增后端能力，未改造接口、数据结构或业务处理。

## 改造前完整备份

- 服务器备份目录：`/opt/jdair-cha/backups/20260812-162937-before-layout-redesign-phase2`
- 服务器备份归档：`/opt/jdair-cha/backups/jdair-cha-before-layout-redesign-phase2-20260812-162937.tar.gz`
- 归档 SHA-256：`5496fb64da2d7e3ad5c25dd2be5ddcb5219e56c8527b194606adb1210389c6cd`
- 归档大小：`3,906,852` 字节
- 本地核验：服务器归档与下载副本 SHA-256 一致。

> 安全说明：完整备份归档包含运行数据和配置，未提交到公共 GitHub 仓库；GitHub 仅保存校验值、路径和恢复说明。

## 验证结果

- Python 语法编译：通过。
- JavaScript 语法检查：通过。
- 后端 Python（HTML 模板外）与上一稳定版本逐字一致：`true`。
- API 字面量：新增 `0`，移除 `0`，现有 `35` 项保持不变。
- `jdair-cha.service`：`active`，并设置为 `enabled`。
- 本机根页面：HTTP `200`。
- 实际登录：成功。
- 实时设备结果：设备 `56`、在线 `3`、定位 `56`（实时数据会变化）。
- 视频记录：加载 `25` 行；默认行高约 `71px`，展开后约 `230px`。
- 操作列：高清播放、添加、标注横向排列。
- 视频播放区不在主页面，弹窗可正常打开。
- 日/夜主题切换：`night → day`，选择可持久化。
- 指挥调度标签互斥显示正常。
- 辅助查询标签互斥显示正常。
- 航班动态加载 `20` 行；例行任务加载 `20` 行。

## 回滚

快速回滚到第二阶段改造前的稳定版本：

```bash
ln -sfn /opt/jdair-cha/releases/20260812151318-layout-redesign /opt/jdair-cha/current
systemctl restart jdair-cha.service
systemctl is-active jdair-cha.service
```

如需恢复运行数据或服务器配置，使用第二阶段改造前备份归档：

```bash
sha256sum /opt/jdair-cha/backups/jdair-cha-before-layout-redesign-phase2-20260812-162937.tar.gz
# 应为 5496fb64da2d7e3ad5c25dd2be5ddcb5219e56c8527b194606adb1210389c6cd
```
