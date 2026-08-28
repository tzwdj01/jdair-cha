"""Driver-agnostic durable inspection-history repository seam.

The store interface consumes only normalized event contracts from
``app.data.normalization`` and ``app.data.realtime_views``. It does not know
about AEE HTTP, WebRTC runtime state or browser data.
"""

from .inspection_memory import MemoryInspectionRecordStore
from .inspection_postgres import PostgresInspectionRecordStore
from .inspection_repository import InspectionRecordStore
from .memory import MemoryInspectionStore
from .postgres import PostgresInspectionStore
from .repository import InspectionStore
from .sinks import StoreViewEventSink

__all__ = [
    "InspectionStore",
    "InspectionRecordStore",
    "MemoryInspectionRecordStore",
    "MemoryInspectionStore",
    "PostgresInspectionRecordStore",
    "PostgresInspectionStore",
    "StoreViewEventSink",
]
