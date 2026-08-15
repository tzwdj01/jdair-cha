from __future__ import annotations

from ..realtime_views import RealtimeViewEvent
from .repository import InspectionStore


class StoreViewEventSink:
    """Persist finalized RealtimeViewEvent rows through an InspectionStore.

    The session manager calls this sink when a stream/session closes, times
    out or disconnects. Failures propagate to the session manager, which keeps
    the finalized event for an idempotent retry; the store's
    first-finalization-per-stream semantics make the retry safe.

    This is a real write path for CHA-owned inspection usage history. It is
    only constructed when a caller explicitly provides a store, so production
    behavior is unchanged until a durable store is configured.
    """

    def __init__(self, store: InspectionStore) -> None:
        self._store = store

    async def __call__(self, event: RealtimeViewEvent) -> None:
        await self._store.upsert_realtime_view_events((event,))
