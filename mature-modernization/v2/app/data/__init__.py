"""M4 normalized inspection-data contracts and deterministic aggregations."""

from .metrics import (
    DeviceUptimeAggregationResult,
    DeviceUptimeMetric,
    MediaAggregationResult,
    MediaDeviceMetric,
    aggregate_device_uptime,
    aggregate_media_files,
)

__all__ = [
    "DeviceUptimeMetric",
    "DeviceUptimeAggregationResult",
    "MediaAggregationResult",
    "MediaDeviceMetric",
    "aggregate_device_uptime",
    "aggregate_media_files",
]
