# M4 P3.2 — AEE Access Path Diagnostic

Date: `2026-08-16`

Status: `ACCESS PATH IDENTIFIED — SUPPORTED SERVER-SIDE ACCESS CANDIDATE`

Purpose: 纯只读诊断，回答 493 是否与 source IP / browser challenge / WAF
policy 相关，并寻找受支持的服务器端 AEE 数据通道。未尝试绕过 WAF、未启动
browser token daemon、未启用 scheduler、未修改生产业务数据。

---

## A. Browser result — `PASS`

在已授权 AEE 浏览器会话中，对三个数据 API（合法 token header）只读验证：

| API | HTTP | envelope error | recordsTotal | content-type |
| --- | --- | --- | --- | --- |
| `DevOnlineList` | 200 | 200 | 386 | application/json; charset=utf-8 |
| `RecordFileList` | 200 | 200 | 199 | application/json; charset=utf-8 |
| `AlarmList` | 200 | 200 | 7 | application/json; charset=utf-8 |

Server header: `Jdcloud-FE`。BROWSER PATH = **PASS**。

## B. Local HTTP-client result — `PASS`

同一台开发机上用普通 Python HTTP client（非浏览器、无 challenge 模拟），
仅带合法 `token` header + 浏览器 UA，对同一 API 请求：

| API | HTTP | server | 结果 |
| --- | --- | --- | --- |
| `DevOnlineList` | 200 | Jdcloud-FE | error=200, recordsTotal=386 |
| `RecordFileList` | 200 | Jdcloud-FE | error=200, recordsTotal=199 |
| `AlarmList` | 200 | Jdcloud-FE | error=200, recordsTotal=7 |

Local plain HTTP client（无浏览器 challenge）= **PASS**。

## C. CHA server result — `FAIL (HTTP 493)`

从 CHA 生产服务器（egress public IP `111.228.15.31`）请求同一批 API
（带正确 token + 浏览器 UA + Referer，HTTP 与 HTTPS/TLS+SNI 两种）：

```text
HTTP/1.1 493
Server: Jdcloud-FE
X-JFE-Reason: deny:uri
X-JFE-UUID: <per-request id>
X-JFE-Action: forbidden
X-JFE-Via: jd-hb-jfe-08
Via: jd-hb-jfe-08
```

CHA server = **493**（三个源均 `AEE_DATA_HTTP_ERROR`；`/v3/` 页面同样 493）。

## D. DNS / TLS routing evidence

* `aee.jdcloud.com` → A record `116.198.30.190`（单条 A；AAAA 无）。
* TLS 1.3，TLS 终止于 JD Cloud 前端 `Jdcloud-FE`（`Via: jd-hb-jfe-02/08`）。
* 前端呈现证书为过期的自签 `*.cwctest.com`（2018 年签发，SAN 为 cwctest
  系列内网域）——说明源站不直接对外暴露，JFE 作为 WAF/CDN 前端。
* 本机（开发机出口 IP 命中 JFE skip 规则）响应头含 `X-JFE-Reason: skip:ip`，
  CHA 服务器响应头含 `X-JFE-Reason: deny:uri`。

结论：**493 与浏览器 challenge 无关**（本机无浏览器纯 HTTP client 200），
与 **source IP 相关的 JFE WAF 策略**相关（CHA 服务器 IP 未命中 skip 规则，
命中 URI deny 策略）。

## E. Request difference matrix

| 维度 | Browser | Local HTTP client | CHA server |
| --- | --- | --- | --- |
| method/path | GET `/api/v1/*` | GET `/api/v1/*` | GET `/api/v1/*` |
| Host | aee.jdcloud.com | aee.jdcloud.com | aee.jdcloud.com |
| token header | 有 | 有 | 有 |
| UA | browser | browser-like | browser-like |
| X-JFE-Reason | n/a | `skip:ip` | `deny:uri` |
| HTTP status | 200 | 200 | 493 |

差异点 = source IP（JFE 对 CHA 服务器 IP 未放行，URI deny 命中）。

## F. Legacy supported-path evidence — `SUPPORTED SERVER-SIDE ACCESS CANDIDATE`

CHA Legacy（`/opt/jdair-cha/current/mcs8_web_panel.py`）**并未通过
`aee.jdcloud.com` 前端获取数据**。它使用 MCS8 原生 SDK 服务器通道：

* `LocalConfig.xml` `ServerModel.IpAddress = 116.198.18.19`（MCS8 SDK 服务器，
  与 `aee.jdcloud.com` 前端 IP `116.198.30.190` 不同）。
* 登录：`mcs8_ws_login` → WebSocket 到 `116.198.18.19:7711`
  (`/ ?uid=<user>&pwd=<md5>`)，返回 `token`（160 字符）。
* 数据：`call_mcs8_api` → HTTP 到 `116.198.18.19:7712`
  （`api_port = FilePort+5`），带 `token` header + `SessionId` 参数。

在 CHA 服务器上实测该通道（使用 LocalConfig 账号，通过 WS 登录获取新 token，
只读请求）：

| API（116.198.18.19:7712） | HTTP | 结果 |
| --- | --- | --- |
| `/api/GetDevListByGroupId` | 200 | 114 设备（含 nOnline 等字段） |
| `/api/GetRecordFileList` | 200 | recordsTotal=201~202 |
| `/api/v1/RecordFileList` | 200 | recordsTotal=202（error=200） |
| `/api/v1/AlarmList` | 200 | recordsTotal=7（error=200） |
| `/api/v1/DevOnlineList` | 200 | recordsTotal=0（该通道此端点空；设备在线状态可由 GetDevListByGroupId 的 nOnline 覆盖） |

即：**`116.198.18.19:7712`（MCS8 原生服务器）已被 CHA Legacy 生产使用且可用**，
不经过 JFE WAF，是受支持的服务器端上游通道候选。M4 的
`AEEReadOnlyDataAdapter` 可指向该通道（同一批 `/api/v1/*` 语义，
RecordFileList / AlarmList 已验证可用；DevOnlineList 需改用
`GetDevListByGroupId` 或等价的在线状态源）。

## G. Blocker classification

`WAF source-IP policy`：`aee.jdcloud.com` 前端 JFE 对 CHA 生产服务器出口 IP
（`111.228.15.31`）未放行，`/api/v1/*` 与 `/v3/*` URI 命中 deny 规则 →
HTTP 493。不是浏览器 challenge 问题，不是 token 问题。

## H. Recommended supported access path

优先级：

1. **MCS8 原生服务器通道（首选，已存在且受支持）**：
   `116.198.18.19:7711`（WS 登录）→ `:7712`（REST，token+SessionId）。
   Legacy 已在生产使用；M4 adapter 复用即可，无需 WAF 变更。
   DevOnlineList 以 `GetDevListByGroupId`（含 nOnline）或等效在线状态源替代。
2. JD Cloud WAF/JFE 对 CHA 固定出口 IP `111.228.15.31` 合法白名单
   （若必须走 `aee.jdcloud.com` 前端）。
3. 官方服务器端 API 通道（若有 JD Cloud 网关/白名单集成）。

不做 WAF bypass，不把浏览器 challenge 模拟作为生产方案。

## Not performed

未启用 scheduler；未写生产业务数据；未绕过 WAF；未启动浏览器自动化 daemon；
未修改 AEE 安全策略；未修改生产 app/current/nginx。生产 PG（cha_m4）仍为
迁移基线，0 业务行。
