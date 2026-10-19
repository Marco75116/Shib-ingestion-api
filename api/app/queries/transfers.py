from datetime import datetime

from ..core.constants import MAX_ROWS
from ..core.db import Database


def query_latest_transfers(db: Database, limit: int, since: datetime | None) -> list[dict]:
    where = "WHERE block_timestamp > {since:DateTime64(3)}" if since else ""
    return db.query(
        f"""
        SELECT block_timestamp, tx_hash, from_address, to_address, amount
        FROM transfers FINAL
        {where}
        ORDER BY block_timestamp DESC
        LIMIT {{limit:UInt32}}
        """,
        {"limit": min(limit, MAX_ROWS), "since": since},
    )
