"""Async Postgres access with an asyncpg connection pool.

Why async here: the AI service spends most of its time waiting on the network
(database, LLM APIs). While one request waits, the event loop serves others,
instead of tying up a whole worker thread as a sync Flask worker would.
"""

import asyncio
import logging

import asyncpg

log = logging.getLogger("ppa_ai.db")


class DatabaseUnavailable(Exception):
    """The database cannot be reached right now. Details are logged, never returned to clients."""


class Database:
    def __init__(self, dsn: str | None, *, min_size: int = 1, max_size: int = 5, timeout: float = 3.0):
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._pool: asyncpg.Pool | None = None
        # Several requests can arrive while the pool does not exist yet.
        # The lock makes sure only one of them creates it.
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._pool is not None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise DatabaseUnavailable()
        return self._pool

    async def connect(self) -> bool:
        """Create the pool if needed. Returns False (and logs) instead of raising,
        so the service can start even while the database is down."""
        if self._pool is not None:
            return True
        if not self._dsn:
            log.warning("AI_DATABASE_URL is not set; database features are unavailable")
            return False
        async with self._lock:
            if self._pool is not None:  # another request created it while we waited
                return True
            try:
                self._pool = await asyncpg.create_pool(
                    self._dsn,
                    min_size=self._min_size,
                    max_size=self._max_size,
                    timeout=self._timeout,
                    command_timeout=self._timeout,
                )
            except (OSError, asyncio.TimeoutError, asyncpg.PostgresError) as exc:
                # Log the error type only: the message can contain host or user names.
                log.warning("Could not connect to the AI database (%s)", type(exc).__name__)
                return False
            return True

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def vector_version(self) -> str | None:
        """Installed pgvector version, or None if the extension is missing."""
        if not await self.connect():
            raise DatabaseUnavailable()
        try:
            async with self._pool.acquire(timeout=self._timeout) as conn:
                return await conn.fetchval(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
        except (OSError, asyncio.TimeoutError, asyncpg.PostgresError,
                asyncpg.InterfaceError) as exc:
            log.warning("AI database query failed (%s)", type(exc).__name__)
            raise DatabaseUnavailable() from exc
