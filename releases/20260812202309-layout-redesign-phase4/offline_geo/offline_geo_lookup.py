# -*- coding: utf-8 -*-
"""
离线经纬度 -> 省/市 查询
数据文件：city_geo_lite_0p005.json.gz
坐标系：默认输入 GPS/WGS84，经函数转为 GCJ-02 后查询。若你的坐标本来就是高德/腾讯坐标，可传 coord_type='gcj02'。
"""
import gzip
import json
import math
from pathlib import Path

PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323


def out_of_china(lon: float, lat: float) -> bool:
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y
    ret += 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) + 320.0 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x
    ret += 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lon: float, lat: float) -> tuple[float, float]:
    if out_of_china(lon, lat):
        return lon, lat
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrt_magic) * PI)
    dlon = (dlon * 180.0) / (A / sqrt_magic * math.cos(radlat) * PI)
    return lon + dlon, lat + dlat


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting 点在多边形内判断。ring: [[lon, lat], ...]"""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        # 判断水平射线是否穿过边
        if ((yi > lat) != (yj > lat)):
            x_intersect = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-20) + xi
            if lon < x_intersect:
                inside = not inside
        j = i
    return inside


class OfflineGeoLookup:
    def __init__(self, data_path: str | Path):
        data_path = Path(data_path)
        if data_path.suffix == ".gz":
            with gzip.open(data_path, "rt", encoding="utf-8") as f:
                self.cities = json.load(f)
        else:
            with open(data_path, "r", encoding="utf-8") as f:
                self.cities = json.load(f)

    def lookup(self, lon: float, lat: float, coord_type: str = "wgs84") -> dict | None:
        """
        lon, lat: 经度、纬度
        coord_type:
          - 'wgs84': GPS原始坐标，默认，会转 GCJ-02
          - 'gcj02': 高德/腾讯坐标，不转换
        """
        if coord_type.lower() == "wgs84":
            lon, lat = wgs84_to_gcj02(lon, lat)

        candidates = []
        for city in self.cities:
            minx, miny, maxx, maxy = city["bbox"]
            if minx <= lon <= maxx and miny <= lat <= maxy:
                candidates.append(city)

        for city in candidates:
            for ring in city["polygon"]:
                if point_in_ring(lon, lat, ring):
                    return {
                        "province": city["province"],
                        "city": city["city"],
                        "code": city["code"],
                    }
        return None


if __name__ == "__main__":
    lookup = OfflineGeoLookup("city_geo_lite_0p005.json.gz")
    print(lookup.lookup(116.397428, 39.90923, coord_type="wgs84"))
