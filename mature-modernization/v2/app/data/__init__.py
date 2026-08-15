"""M4 normalized inspection-data contracts and deterministic aggregations."""

from .aee_http import AEEDataHTTPClient, AEEDataHTTPError
from .metrics import (
    DeviceUptimeAggregationResult,
    DeviceUptimeMetric,
    MediaAggregationResult,
    MediaDeviceMetric,
    aggregate_device_uptime,
    aggregate_media_files,
)

__all__ = [
    "AEEDataHTTPClient",
    "AEEDataHTTPError",
    "DeviceUptimeMetric",
    "DeviceUptimeAggregationResult",
    "MediaAggregationResult",
    "MediaDeviceMetric",
    "aggregate_device_uptime",
    "aggregate_media_files",
]
