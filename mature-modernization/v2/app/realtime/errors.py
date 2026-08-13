from __future__ import annotations


class RealtimeError(RuntimeError):
    """A safe, client-facing realtime error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AEEUpstreamError(RuntimeError):
    """Internal AEE adapter failure; never return the raw message to clients."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
