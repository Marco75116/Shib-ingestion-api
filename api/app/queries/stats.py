from typing import Literal

from ..core.constants import MAX_ROWS
from ..core.db import Database

Interval = Literal["1h", "1d"]

BUCKET = {"1h": "hour", "1d": "toStartOfDay(hour)"}


def query_timeseries(db: Database, interval: Interval, hours: int) -> list[dict]:
    return db.query(
        f"""
        SELECT
            {BUCKET[interval]}  AS bucket,
            sum(transfers)      AS transfers,
            sum(volume)         AS volume,
            uniqMerge(senders)  AS senders,
            uniqMerge(receivers) AS receivers
        FROM transfers_hourly
        WHERE hour >= toStartOfHour(now() - INTERVAL {{hours:UInt32}} HOUR)
        GROUP BY bucket
        ORDER BY bucket
        LIMIT {{max_rows:UInt32}}
        """,
        {"hours": hours, "max_rows": MAX_ROWS},
    )

