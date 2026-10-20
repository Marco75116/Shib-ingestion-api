from datetime import datetime

from ..core.constants import MAX_ROWS
from ..core.db import Database

LATEST_WINDOW_DAYS = 7


def query_latest_transfers(db: Database, limit: int, since: datetime | None) -> list[dict]:
    """Newest transfers, bounded on the primary key: `since` if given, else the last LATEST_WINDOW_DAYS."""
    limit = min(limit, MAX_ROWS)
    where = (
        "WHERE block_timestamp > {since:DateTime64(3)}"
        if since
        else "WHERE block_timestamp >= now() - INTERVAL {days:UInt32} DAY"
    )
    rows = db.query(
        f"""
        SELECT block_timestamp, tx_hash, from_address, to_address, amount, unique_id
        FROM transfers
        {where}
        ORDER BY block_timestamp DESC
        LIMIT {{fetch:UInt32}}
        """,
        {"since": since, "days": LATEST_WINDOW_DAYS, "fetch": limit * 2},
    )
    # No FINAL (it merges every part before LIMIT). Kafka is at-least-once: drop duplicates
    # not yet collapsed by ReplacingMergeTree, then cut to `limit`.
    seen: set[str] = set()
    unique = [r for r in rows if r["unique_id"] not in seen and not seen.add(r["unique_id"])]
    return [{k: v for k, v in r.items() if k != "unique_id"} for r in unique[:limit]]
