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
from .normalization import (
    DeviceStatusEvent,
    DeviceStatusNormalizationResult,
    MediaFile,
    MediaFileNormalizationResult,
    normalize_device_status_events,
    normalize_media_files,
)
from .pagination import AEEPageCollection, collect_aee_pages
from .realtime_views import RealtimeViewEvent, build_realtime_view_event

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
    "DeviceStatusEvent",
    "DeviceStatusNormalizationResult",
    "MediaFile",
    "MediaFileNormalizationResult",
    "normalize_device_status_events",
    "normalize_media_files",
    "AEEPageCollection",
    "collect_aee_pages",
    "RealtimeViewEvent",
    "build_realtime_view_event",
]
