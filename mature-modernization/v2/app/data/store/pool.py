from __future__ import annotations

import threading
from typing import Any

try:  # pragma: no cover - exercised only with psycopg2 installed
    from psycopg2.pool import PoolError as _PoolError
    from psycopg2.pool import ThreadedConnectionPool as _ThreadedConnectionPool
except ImportError:  # pragma: no cover - optional production driver
    _PoolError = ()  # type: ignore[assignment]
    _ThreadedConnectionPool = None  # type: ignore[assignment]


class PostgresPoolExhaustedError(RuntimeError):
    """A bounded PostgreSQL pool could not lease a connection in time.

    ``psycopg2.pool.ThreadedConnectionPool.getconn`` fails immediately when
    the pool is exhausted.  Application code uses this stable, non-driver
    exception to report a brief, truthful degraded state rather than leaking a
    psycopg2 detail or allowing an upstream dashboard request to cascade.
    """

    code = "database_busy"


class PostgresPoolClosedError(RuntimeError):
    """A process-scoped pool was used after application shutdown."""

    code = "database_unavailable"


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
        acquire_timeout_seconds: float = 0.5,
    ) -> None:
        if min_connections < 1 or max_connections < min_connections:
            raise ValueError("invalid PostgreSQL connection pool bounds")
        if acquire_timeout_seconds <= 0:
            raise ValueError("pool acquire timeout must be positive")
        self._min_connections = min_connections
        self._max_connections = max_connections
        self._connection_kwargs = dict(connection_kwargs)
        self._acquire_timeout_seconds = acquire_timeout_seconds
        self._lock = threading.Lock()
        # psycopg2's ThreadedConnectionPool serializes getconn(), including
        # a cold TCP/TLS connection attempt. Keep a separate, bounded gate in
        # front of that driver call: a slow upstream connect must not strand
        # every asyncio.to_thread caller behind the driver's unbounded lock.
        # Queries still use the full connection pool once a connection is
        # acquired; this gate covers only getconn().
        self._driver_getconn_gate = threading.Lock()
        self._pool: Any = None
        self._closed = False
        # ``ThreadedConnectionPool`` is thread-safe, but its ``getconn`` call
        # is non-waiting.  This semaphore gives the application one short,
        # bounded wait window and keeps the driver's immediate PoolError out of
        # API and readiness paths.
        self._leases = threading.BoundedSemaphore(max_connections)

    def _get_pool(self) -> Any:
        with self._lock:
            if self._closed:
                raise PostgresPoolClosedError(
                    "PostgreSQL pool is closed during application shutdown"
                )
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
        with self._lock:
            if self._closed:
                raise PostgresPoolClosedError(
                    "PostgreSQL pool is closed during application shutdown"
                )
        leased = self._leases.acquire(timeout=self._acquire_timeout_seconds)
        if not leased:
            raise PostgresPoolExhaustedError(
                "PostgreSQL connection pool is temporarily busy"
            )

        driver_gate_acquired = self._driver_getconn_gate.acquire(
            timeout=self._acquire_timeout_seconds
        )
        if not driver_gate_acquired:
            self._leases.release()
            raise PostgresPoolExhaustedError(
                "PostgreSQL connection pool is temporarily busy"
            )

        try:
            pool = self._get_pool()
            connection = pool.getconn()
        except _PoolError as exc:
            # The semaphore is the normal bounded path.  Retain this conversion
            # for a driver-level race or a pool implementation that reports
            # exhaustion independently.
            self._leases.release()
            raise PostgresPoolExhaustedError(
                "PostgreSQL connection pool is temporarily busy"
            ) from exc
        except Exception:
            self._leases.release()
            raise
        finally:
            self._driver_getconn_gate.release()
        return _PooledConnection(pool, connection, self._leases)

    def close(self) -> None:
        """Release all pooled connections during application shutdown."""

        with self._lock:
            pool = self._pool
            self._pool = None
            self._closed = True
        if pool is not None:
            pool.closeall()

    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._pool is not None


class _PooledConnection:
    """Return a raw connection to its pool with safe transaction cleanup."""

    __slots__ = ("_pool", "_conn", "_lease")

    def __init__(
        self,
        pool: Any,
        conn: Any,
        lease: threading.BoundedSemaphore,
    ) -> None:
        self._pool = pool
        self._conn = conn
        self._lease = lease

    def __enter__(self) -> Any:
        if self._conn is None:
            raise RuntimeError("pooled PostgreSQL connection is closed")
        return self._conn

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        conn = self._conn
        pool = self._pool
        self._conn = None
        self._pool = None
        lease = self._lease
        self._lease = None
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
            try:
                pool.putconn(conn, close=discard)
            finally:
                # A lease is released for every success, query exception,
                # transaction-cleanup failure and broken-connection discard.
                # This must happen even if a third-party pool's putconn itself
                # fails, otherwise future requests could remain blocked.
                if lease is not None:
                    lease.release()
        return False
