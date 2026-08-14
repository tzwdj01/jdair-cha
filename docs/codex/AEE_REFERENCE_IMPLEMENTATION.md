# AEE Reference Implementation Principle

## 1. Purpose

`http://aee.jdcloud.com/` 是本项目的重要上游能力参考实现。

AEE 的作用不是作为 CHA 的前端依赖，也不是作为需要复制的实现，而是用于：

> 验证底层 MCS8 / AEE 实际能力、协议行为、SDK 行为、设备行为和媒体链路行为。

对于 AEE 已经具备、CHA 尚未实现的功能，或者 CHA 实现过程中出现：

* 不明协议；
* 不明参数；
* 不明 SDK 行为；
* WebSocket 行为异常；
* RTP 参数不明确；
* codec 行为不明确；
* stream profile 不明确；
* capability 不明确；
* 设备兼容性问题；
* 媒体链路问题；
* AEE 与 CHA 同设备表现不一致；

不得优先自行猜测、重新设计协议或增加复杂 workaround。

应优先进行：

**AEE → CHA 对照验证。**

---

# 2. Reference Environment

在具备合法权限的情况下，应尽可能使用相同的：

* 用户；
* 设备；
* 操作场景；
* 浏览器；
* 网络环境；
* 时间窗口；

分别验证 AEE 和 CHA。

应尽量控制变量，使：

> AEE 与 CHA 的差异成为主要变量。

---

# 3. Allowed Observation

允许通过：

* 浏览器开发者工具；
* Network；
* Console；
* WebSocket inspector；
* Performance；
* Sources；
* 合法测试脚本；

观察：

* HTTP 请求；
* HTTP response；
* WebSocket 建立过程；
* WebSocket 生命周期；
* WebSocket message；
* SDK 方法调用；
* SDK 参数；
* SDK 返回值；
* `rtpParameters`；
* codec；
* stream profile；
* capability；
* SDP / ICE / DTLS 等浏览器正常暴露的媒体协商信息；
* 静态 JS/WASM 依赖；
* 页面状态变化；
* 会话建立行为；
* 重连行为；
* 资源释放行为；
* 播放停止行为；
* 多路播放行为；
* 浏览器资源变化。

目标是理解：

> AEE 实际依赖的底层 MCS8 / AEE 能力以及正确使用方式。

---

# 4. Security and Access Boundary

严格禁止：

* 绕过 AEE 权限；
* 获取无权访问的数据；
* 破解认证；
* 绕过授权检查；
* 提取与任务无关的用户数据；
* 将 AEE Cookie 固化进 CHA；
* 将 AEE 长期 Token 固化进 CHA；
* 将个人认证信息提交到 Git；
* 将敏感凭证写入日志、测试数据或文档；
* 让 CHA 浏览器长期直接依赖 AEE 页面私有接口；
* 将 AEE 页面作为 CHA 生产运行时依赖；
* 简单复制 AEE 前端代码形成强耦合。

AEE 是：

**Reference Implementation**

而不是：

**Runtime Dependency**。

---

# 5. Evidence First

如果 CHA 和 AEE 在同一设备、同一场景上的表现不同：

不得首先修改 CHA。

必须首先形成：

# AEE vs CHA Evidence

至少记录：

## Test Context

* 时间；
* Device ID / 可安全记录的设备标识；
* 浏览器；
* 用户权限场景；
* 操作步骤；
* 网络环境。

## AEE Behaviour

记录：

* 请求；
* WebSocket；
* SDK 调用；
* 参数；
* codec；
* RTP；
* capability；
* stream profile；
* 状态变化；
* 播放结果；
* 资源释放结果。

## CHA Behaviour

以相同维度记录 CHA。

## Difference

明确指出：

* 相同项；
* 不同项；
* 已确认事实；
* 尚未确认事项。

## Conclusion

最后才能形成修复假设。

不得：

> 先提出架构方案，再反向寻找证据。

---

# 6. Capability Classification

完成观察后必须将能力分类。

## Class A — Backend Read-only Capability

可直接通过：

`CHA Backend Adapter`

复用的只读接口。

例如：

* 查询类能力；
* 状态类能力；
* metadata；
* capability 查询。

---

## Class B — SDK / Protocol Media Capability

应通过：

`SDK Adapter`

或：

`Protocol Adapter`

复用的底层媒体能力。

例如：

* 实时播放；
* media session；
* RTP；
* codec；
* stream selection；
* WebRTC negotiation；
* audio；
* reconnect。

---

## Class C — CHA Business Aggregation

底层能力可以借鉴或调用，但业务逻辑应在 CHA 内重新聚合实现。

例如：

* 多设备编排；
* 看板；
* 设备分组；
* 告警联动；
* 会话池；
* UI 状态；
* 业务权限；
* 业务审计。

---

## Class D — Reference Only

只用于理解，不应形成 CHA 运行时依赖的 AEE 页面内部实现。

例如：

* AEE 页面状态管理；
* 页面私有 API；
* AEE 专用 UI glue code；
* 页面私有路由；
* 与 CHA 业务无关的内部实现。

---

# 7. Architecture Escalation Gate

在没有充分证据证明现有 MCS8 / AEE / 浏览器原生能力无法满足需求之前，不得引入：

* FFmpeg；
* 自建媒体服务器；
* 自建 SFU；
* 自定义 decoder；
* 自定义 transcoding pipeline；
* 大型流媒体基础设施；
* 复杂 proxy；
* 复杂 protocol translation；
* 大型 workaround。

如果确实需要引入上述组件，必须先形成：

## Architecture Escalation Evidence

包括：

1. 当前需求；
2. CHA 当前表现；
3. AEE 同场景表现；
4. AEE 使用的能力；
5. 已尝试的原生 MCS8 / SDK 方案；
6. 为什么无法满足；
7. 新基础设施解决的问题；
8. 运维成本；
9. 安全风险；
10. 回滚方案。

无上述证据：

> 不批准架构升级。

---

# 8. When AEE Cannot Be Accessed

如果当前 Codex 执行环境无法访问 AEE，或者没有合法认证上下文：

不得猜测 AEE 行为。

相关事项必须标记：

`AEE VERIFICATION REQUIRED`

并记录：

* Question；
* Device；
* Scenario；
* Expected Observation；
* Required Network Evidence；
* Required WebSocket Evidence；
* Required SDK Evidence；
* Required Media Evidence。

如果该未知项阻塞当前实现：

暂停该依赖分支。

如果不阻塞：

继续完成其它可以独立验证的工作。

---

# 9. Decision Principle

本项目媒体能力相关问题的默认决策顺序为：

**现象**

↓

**复现 CHA**

↓

**使用相同设备和场景复现 AEE**

↓

**AEE vs CHA Evidence**

↓

**确认底层 MCS8 / SDK / Protocol 能力**

↓

**Class A / B / C / D**

↓

**选择最小必要修改**

↓

**CHA 实现**

↓

**回归验证**

而不是：

**现象**

↓

**猜测**

↓

**新增基础设施**

↓

**复杂 workaround**

---

# 10. Core Principle

最终原则：

> AEE 用于理解能力，而不是复制系统。

> Evidence before workaround.

> Adapter before coupling.

> Existing capability before new infrastructure.

> Same device, same scenario, AEE vs CHA before architecture changes.
