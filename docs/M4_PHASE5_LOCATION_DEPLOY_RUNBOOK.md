# M4 PHASE 5 — Device Location Persistence Deploy Runbook

Date: `2026-08-18`

Status: `AWAITING OWNER AUTHORIZATION`（生产变更，未授权不得执行）

## 1. 目标

把 MCS8 设备快照中**已携带的当前定位**（`nJingDu`/`nWeiDu`/`gpsTime`/
`ucMapType`）持久化到生产 PostgreSQL `device_location_events`，使
`/dashboard/locations`（设备定位）从诚实空变为真实数据。

这是 PHASE 5 真实使用问题修复（commit `94871e5` + `3b40b52`），
仅补齐既有 DEVICE 来源的数据持久化：

* 不新增上游 API 调用（复用 `GetDevListByGroupId` 同一份快照）；
* 不新增 scheduler source、不改变 DEVICE→MEDIA→ALARM 顺序；
* 不改变采集频率；
* 幂等 upsert（device+gpsTime+坐标 唯一键），位置不变不增行。

## 2. 代码基线（Git）

Branch：`codex/m4-inspection-data-center-20260815`

相关提交：

* `94871e5` fix: persist device locations from MCS8 snapshot
* `3b40b52` test: cover scheduler state JSON serialization of device location flags

## 3. 需要同步到生产 scheduler 的文件（共 3 个）

```text
mature-modernization/v2/app/data/normalization.py
mature-modernization/v2/app/data/__init__.py
mature-modernization/v2/app/data/mcs8_collector.py
```

目标目录：

```text
/opt/jdair-cha/m4-scheduler/app/data/
```

（生产 scheduler 持有独立 app 副本；v2 release 不参与本部署。）

## 4. 部署步骤（授权后执行）

1. 备份目标文件：

   ```bash
   mkdir -p /opt/jdair-cha/m4-scheduler/backups/location-$(date +%Y%m%d%H%M%S)
   cp -a /opt/jdair-cha/m4-scheduler/app/data/{normalization.py,__init__.py,mcs8_collector.py} \
     /opt/jdair-cha/m4-scheduler/backups/location-<STAMP>/
   ```

2. 上传 3 个文件到目标目录（root 上传后 chown 回 jdair-demo）：

   ```bash
   chown jdair-demo:jdair-demo \
     /opt/jdair-cha/m4-scheduler/app/data/{normalization.py,__init__.py,mcs8_collector.py}
   ```

3. 语法自检（部署进程 Python）：

   ```bash
   /opt/jdair-cha/m4-scheduler/venv/bin/python -m py_compile \
     /opt/jdair-cha/m4-scheduler/app/data/{normalization.py,__init__.py,mcs8_collector.py}
   ```

4. 重启 scheduler：

   ```bash
   systemctl restart jdair-cha-m4-scheduler.service
   systemctl is-active jdair-cha-m4-scheduler.service
   ```

5. 确认首个 cycle（约 1 分钟内完成）写入定位：

   ```bash
   # scheduler state 中 device_status 源应出现 device_locations_stored=<N>
   python3 -c "import json;d=json.load(open('/opt/jdair-cha/m4-scheduler/state/scheduler_state.json'));\
   k=sorted(d,key=int)[-1];print([s for s in d[k]['sources'] if s['source']=='device_status'])"

   # PG 行数
   export PGPASSWORD=<CHA_PG_PASSWORD 来自 /etc/cha-pg-secrets>
   psql -h <CHA_PG_HOST> -U cha_app -d cha_m4 -At -c \
     "select count(*), count(distinct device_id) from inspection.device_location_events;"
   ```

   预期：首个 cycle 后 `count(*) ≈ 92`（22 台 `gpsTime=0001-01-01` 哨兵
   设备被正确剔除）；后续 cycle 位置不变时行数不增长。

6. Dashboard 验证：

   ```text
   GET /api/v2/inspection/locations?days=3
   ```

   应返回 `source_event_count > 0`、`devices` 列表、非 EMPTY coverage。

## 5. 回滚

```bash
cp -a /opt/jdair-cha/m4-scheduler/backups/location-<STAMP>/* \
  /opt/jdair-cha/m4-scheduler/app/data/
chown jdair-demo:jdair-demo \
  /opt/jdair-cha/m4-scheduler/app/data/{normalization.py,__init__.py,mcs8_collector.py}
systemctl restart jdair-cha-m4-scheduler.service
```

回滚后 scheduler 恢复为不持久化定位；`device_location_events` 中已写入的
行保留（历史数据不回滚，符合 forward-only 原则）。如需清空测试性定位行，
须单独经 owner 批准。

## 6. 安全与停止条件

* 不修改 `/etc/jdair-cha/m4-scheduler.env`、Nginx、systemd unit 本身、v2
  release 或 Aliyun PG 配置；
* 不写入真实密码/Token 到任何 Git/文档/日志；
* 若重启后 scheduler 异常退出或首个 cycle 非 `all_successful=True`：
  立即回滚并报告；
* 本 runbook 仅用于已授权部署；未授权不得执行第 4 节步骤。
