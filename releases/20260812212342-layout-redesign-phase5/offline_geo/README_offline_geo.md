# 离线经纬度定位到省-市

## 文件说明

- `city_geo_lite_0p005.json.gz`：从上传的 `ok_geo.csv` 中抽取市级边界，并按约 0.005 度进行简化后的省-市边界数据。
- `offline_geo_lookup.py`：离线查询脚本，无需高德 Key，无需联网。

## 使用方式

```python
from offline_geo_lookup import OfflineGeoLookup

lookup = OfflineGeoLookup("city_geo_lite_0p005.json.gz")

# GPS 原始坐标，WGS84
result = lookup.lookup(116.397428, 39.90923, coord_type="wgs84")
print(result)
```

返回：

```json
{"province": "北京市", "city": "北京市", "code": 1101}
```

## 注意

1. 原始 GPS 通常是 WGS84；国内地图边界数据一般需要用 GCJ-02 坐标查询，所以脚本默认会把 WGS84 转 GCJ-02。
2. 本数据只保留省-市级边界，不返回区县。
3. 边界已简化，靠近城市边界几十米到几百米范围可能出现归属误差。若对边界精度要求更高，可使用未简化或 0.001/0.003 精度版本。
