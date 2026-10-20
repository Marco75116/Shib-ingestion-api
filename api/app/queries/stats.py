from typing import Literal

from ..core.constants import MAX_ROWS
from ..core.db import Database

Bucket = Literal["1h", "1d"]

# (bucket expression, window start) per bucket size. Daily buckets start at midnight so the first
# bucket is a full day; the last bucket (the current hour/day) is always partial.
BUCKET = {
    "1h": ("hour", "toStartOfHour(now() - INTERVAL {hours:UInt32} HOUR)"),
    "1d": ("toStartOfDay(hour)", "toStartOfDay(now() - INTERVAL {hours:UInt32} HOUR)"),
}


def query_timeseries(db: Database, bucket: Bucket, hours: int) -> list[dict]:
    """One row per bucket over the last `hours`, read from the pre-aggregated transfers_hourly table."""
    bucket_expr, window_start = BUCKET[bucket]
    return db.query(
        f"""
        SELECT
            {bucket_expr}        AS bucket,
            sum(transfers)       AS transfers,
            sum(volume)          AS volume,
            uniqMerge(senders)   AS senders,
            uniqMerge(receivers) AS receivers
        FROM transfers_hourly
        WHERE hour >= {window_start}
        GROUP BY bucket
        ORDER BY bucket
        LIMIT {{max_rows:UInt32}}
        """,
        {"hours": hours, "max_rows": MAX_ROWS},
    )
