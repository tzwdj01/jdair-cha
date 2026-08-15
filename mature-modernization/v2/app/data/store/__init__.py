"""Driver-agnostic durable inspection-history repository seam.

The store interface consumes only normalized event contracts from
``app.data.normalization`` and ``app.data.realtime_views``. It does not know
about AEE HTTP, WebRTC runtime state or browser data.
"""

from .memory import MemoryInspectionStore
from .repository import InspectionStore
from .sinks import StoreViewEventSink

__all__ = [
    "InspectionStore",
    "MemoryInspectionStore",
    "StoreViewEventSink",
]
