from __future__ import annotations

import threading
from typing import Any

try:  # pragma: no cover - exercised only with psycopg2 installed
    from psycopg2.pool import ThreadedConnectionPool as _ThreadedConnectionPool
except ImportError:  # pragma: no cover - optional production driver
    _ThreadedConnectionPool = None  # type: ignore[assignment]


class PostgresConnectionPool:
    """Small, thread-safe pool for synchronous psycopg2 calls in ``to_thread``.

    The M4 stores execute blocking psycopg2 work through ``asyncio.to_thread``.
    A thread-safe pool avoids reconnecting across the private PostgreSQL link
    for every repository method while retaining an intentionally small,
    bounded connection footprint.
    """

    def __init__(
        self,
        *,
        min_connections: int,
        max_connections: int,
        connection_kwargs: dict[str, Any],
    ) -> None:
        if min_connections < 1 or max_connections < min_connections:
            raise ValueError("invalid PostgreSQL connection pool bounds")
        self._min_connections = min_connections
        self._max_connections = max_connections
        self._connection_kwargs = dict(connection_kwargs)
        self._lock = threading.Lock()
        self._pool: Any = None

    def _get_pool(self) -> Any:
        with self._lock:
            if self._pool is None:
                if _ThreadedConnectionPool is None:
                    raise ImportError(
                        "psycopg2.pool is required to use PostgreSQL stores"
                    )
                self._pool = _ThreadedConnectionPool(
                    self._min_connections,
                    self._max_connections,
                    **self._connection_kwargs,
                )
            return self._pool

    def connection(self) -> "_PooledConnection":
        pool = self._get_pool()
        return _PooledConnection(pool, pool.getconn())

    def close(self) -> None:
        """Release all pooled connections during application shutdown."""

        with self._lock:
            pool = self._pool
            self._pool = None
        if pool is not None:
            pool.closeall()

    @property
    def initialized(self) -> bool:
        return self._pool is not None


class _PooledConnection:
    """Return a raw connection to its pool with safe transaction cleanup."""

    __slots__ = ("_pool", "_conn")

    def __init__(self, pool: Any, conn: Any) -> None:
        self._pool = pool
        self._conn = conn

    def __enter__(self) -> Any:
        if self._conn is None:
            raise RuntimeError("pooled PostgreSQL connection is closed")
        return self._conn

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        conn = self._conn
        pool = self._pool
        self._conn = None
        self._pool = None
        if conn is None or pool is None:
            return False

        discard = False
        try:
            if exc_type is None:
                conn.commit()
            else:
                conn.rollback()
        except Exception:
            # A failed commit/rollback leaves the transaction state unknown.
            # Never return that connection to the pool for future requests.
            discard = True
            raise
        finally:
            pool.putconn(conn, close=discard)
        return False
