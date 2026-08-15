"""M4 normalized inspection-data contracts and deterministic aggregations."""

from .aee_adapter import AEEPageResult, AEEReadOnlyDataAdapter
from .aee_http import AEEDataHTTPClient, AEEDataHTTPError
from .metrics import (
    DeviceUptimeAggregationResult,
    DeviceUptimeMetric,
    MediaAggregationResult,
    MediaDeviceMetric,
    aggregate_device_uptime,
    aggregate_media_files,
)
from .pagination import AEEPageCollection, collect_aee_pages

__all__ = [
    "AEEDataHTTPClient",
    "AEEDataHTTPError",
    "AEEPageResult",
    "AEEReadOnlyDataAdapter",
    "DeviceUptimeMetric",
    "DeviceUptimeAggregationResult",
    "MediaAggregationResult",
    "MediaDeviceMetric",
    "aggregate_device_uptime",
    "aggregate_media_files",
    "AEEPageCollection",
    "collect_aee_pages",
]
