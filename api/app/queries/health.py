from ..core.db import Database


def query_ingestion_status(db: Database) -> dict:
    return db.one(
        """
        SELECT
            count()                                                      AS transfers,
            dateDiff('second', max(block_timestamp), now())              AS seconds_since_last_transfer,
            round(avgIf(dateDiff('second', inserted_at, ingested_at),
                        ingested_at > now() - INTERVAL 1 HOUR))          AS pipeline_latency_seconds
        FROM transfers
        """
    )
