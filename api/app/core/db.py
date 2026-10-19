import logging
import time
from datetime import datetime, timezone
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver import httputil
from clickhouse_connect.driver.client import Client

from .config import settings
from .constants import STARTUP_ATTEMPTS, STARTUP_RETRY_SECONDS

log = logging.getLogger("uvicorn.error")


class Database:
    def __init__(self) -> None:
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=settings.host,
                port=settings.port,
                username=settings.user,
                password=settings.password,
                database=settings.db,
                connect_timeout=5,
                send_receive_timeout=30,
                autogenerate_session_id=False,
                pool_mgr=httputil.get_pool_manager(maxsize=settings.pool_size, block=True),
            )
        return self._client

    def connect(self) -> None:
        """Open the client and prove ClickHouse answers. Raises after STARTUP_ATTEMPTS failures."""
        target = f"{settings.host}:{settings.port} as {settings.user!r} on db {settings.db!r}"
        for attempt in range(1, STARTUP_ATTEMPTS + 1):
            try:
                self.client.command("SELECT 1")
                log.info("ClickHouse reachable at %s", target)
                return
            except Exception as exc:
                log.warning("ClickHouse not reachable (%d/%d): %s", attempt, STARTUP_ATTEMPTS, exc)
                self.close()
                if attempt == STARTUP_ATTEMPTS:
                    raise RuntimeError(f"ClickHouse unreachable at {target}") from exc
                time.sleep(STARTUP_RETRY_SECONDS)

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = self.client.query(sql, parameters=params).named_results()
        return [{k: _as_utc(v) for k, v in row.items()} for row in rows]

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = self.query(sql, params)
        return rows[0] if rows else {}

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _as_utc(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


database = Database()


def get_db() -> Database:
    return database
