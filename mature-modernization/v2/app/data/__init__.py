"""M4 normalized inspection-data contracts and deterministic aggregations."""

from .aee_adapter import AEEPageResult, AEEReadOnlyDataAdapter
from .aee_http import AEEDataHTTPClient, AEEDataHTTPError
from .device_snapshot import (
    DeviceSnapshotProcessingResult,
    MCS8DeviceSnapshotProcessor,
)
from .mcs8_adapter import MCS8ReadOnlyDataAdapter
from .mcs8_auth import MCS8AuthError, MCS8ServerAuthProvider
from .mcs8_http import MCS8DataHTTPClient
from .mcs8_collector import MCS8InspectionCollector
from .metrics import (
    AlarmAggregationResult,
    AlarmDeviceMetric,
    DeviceLocationAggregationResult,
    DeviceLocationMetric,
    DeviceUptimeAggregationResult,
    DeviceUptimeMetric,
    MediaAggregationResult,
    MediaDeviceMetric,
    RealtimeViewAggregationResult,
    RealtimeViewDimensionMetric,
    aggregate_alarm_events,
    aggregate_device_locations,
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
    normalize_mcs8_device_snapshot,
    normalize_mcs8_device_snapshot_locations,
)
from .pagination import AEEPageCollection, collect_aee_pages
from .realtime_views import RealtimeViewEvent, build_realtime_view_event
from .store import InspectionStore, MemoryInspectionStore

__all__ = [
    "AEEDataHTTPClient",
    "AEEDataHTTPError",
    "AEEPageResult",
    "AEEReadOnlyDataAdapter",
    "DeviceSnapshotProcessingResult",
    "MCS8DataHTTPClient",
    "MCS8DeviceSnapshotProcessor",
    "MCS8InspectionCollector",
    "MCS8ReadOnlyDataAdapter",
    "MCS8ServerAuthProvider",
    "MCS8AuthError",
    "DeviceUptimeMetric",
    "DeviceUptimeAggregationResult",
    "DeviceLocationMetric",
    "DeviceLocationAggregationResult",
    "MediaAggregationResult",
    "MediaDeviceMetric",
    "aggregate_device_uptime",
    "aggregate_device_locations",
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
    "normalize_mcs8_device_snapshot",
    "normalize_mcs8_device_snapshot_locations",
    "AlarmEvent",
    "AlarmNormalizationResult",
    "normalize_alarm_events",
    "AEEPageCollection",
    "collect_aee_pages",
    "RealtimeViewEvent",
    "build_realtime_view_event",
    "InspectionStore",
    "MemoryInspectionStore",
]
