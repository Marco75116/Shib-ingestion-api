from ..core.db import Database

LATENCY_WINDOW_HOURS = 1
LAST_TRANSFER_LOOKBACK_DAYS = 1


def query_ingestion_status(db: Database) -> dict:
    """Ingestion status without scanning `transfers`.

    - count(): trivial metadata read.
    - newest block_timestamp: reverse primary-key read with LIMIT 1 (a few granules), bounded to a day.
    - latency: rows in the last hour only, by primary key. Clamped at 0 because the producer clock
      can run slightly ahead of this host's.
    Both are NULL (not an error, not NaN) when the window holds no rows, e.g. on a fresh deployment.
    """
    return db.one(
        """
        SELECT
            (SELECT count() FROM transfers) AS transfers,
            (SELECT dateDiff('second', max(toNullable(block_timestamp)), now())
             FROM (SELECT block_timestamp FROM transfers
                   WHERE block_timestamp >= now() - INTERVAL {lookback:UInt32} DAY
                   ORDER BY block_timestamp DESC LIMIT 1)) AS seconds_since_last_transfer,
            (SELECT greatest(0, round(avgIfOrNull(dateDiff('second', inserted_at, ingested_at),
                                                  ingested_at > now() - INTERVAL {window:UInt32} HOUR)))
             FROM transfers
             WHERE block_timestamp >= now() - INTERVAL {window:UInt32} HOUR) AS pipeline_latency_seconds
        """,
        {"lookback": LAST_TRANSFER_LOOKBACK_DAYS, "window": LATENCY_WINDOW_HOURS},
    )
