"""M4 normalized inspection-data contracts and deterministic aggregations."""

from .aee_adapter import AEEPageResult, AEEReadOnlyDataAdapter
from .aee_http import AEEDataHTTPClient, AEEDataHTTPError
from .metrics import (
    AlarmAggregationResult,
    AlarmDeviceMetric,
    DeviceUptimeAggregationResult,
    DeviceUptimeMetric,
    MediaAggregationResult,
    MediaDeviceMetric,
    RealtimeViewAggregationResult,
    RealtimeViewDimensionMetric,
    aggregate_alarm_events,
    aggregate_device_uptime,
    aggregate_media_files,
    aggregate_realtime_views,
)
from .normalization import (
    AlarmEvent,
    AlarmNormalizationResult,
    DeviceLocationEvent,
    DeviceLocationNormalizationResult,
    DeviceStatusEvent,
    DeviceStatusNormalizationResult,
    MediaFile,
    MediaFileNormalizationResult,
    normalize_alarm_events,
    normalize_device_location_events,
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
    "RealtimeViewDimensionMetric",
    "RealtimeViewAggregationResult",
    "aggregate_realtime_views",
    "AlarmDeviceMetric",
    "AlarmAggregationResult",
    "aggregate_alarm_events",
    "DeviceStatusEvent",
    "DeviceStatusNormalizationResult",
    "DeviceLocationEvent",
    "DeviceLocationNormalizationResult",
    "MediaFile",
    "MediaFileNormalizationResult",
    "normalize_device_status_events",
    "normalize_device_location_events",
    "normalize_media_files",
    "AlarmEvent",
    "AlarmNormalizationResult",
    "normalize_alarm_events",
    "AEEPageCollection",
    "collect_aee_pages",
    "RealtimeViewEvent",
    "build_realtime_view_event",
]
