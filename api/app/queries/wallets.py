from datetime import datetime
from typing import Literal

from ..core.constants import MAX_ROWS
from ..core.db import Database

Direction = Literal["all", "in", "out"]


def query_wallet_transfers(
    db: Database, wallet: str, direction: Direction, limit: int, before: datetime | None
) -> list[dict]:
    limit = min(limit, MAX_ROWS)
    where = "wallet = {wallet:String}"
    if direction != "all":
        where += " AND direction = {direction:String}"
    if before is not None:
        where += " AND block_timestamp < {before:DateTime64(3)}"
    rows = db.query(
        f"""
        SELECT block_timestamp, direction, counterparty, amount, tx_hash, unique_id
        FROM transfers_by_wallet
        WHERE {where}
        ORDER BY block_timestamp DESC, unique_id DESC
        LIMIT {{fetch:UInt32}}
        """,
        {"wallet": wallet, "direction": direction, "before": before, "fetch": limit * 2},
    )
    # Kafka is at-least-once: drop duplicates not yet merged by ReplacingMergeTree, then cut to `limit`.
    seen: set[tuple[str, str]] = set()
    unique = [r for r in rows if (key := (r["unique_id"], r["direction"])) not in seen and not seen.add(key)]
    return unique[:limit]
