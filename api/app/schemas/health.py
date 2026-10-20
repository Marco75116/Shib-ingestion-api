from pydantic import BaseModel, Field


class Health(BaseModel):
    status: str
    clickhouse: str
    transfers: int | None = None
    seconds_since_last_transfer: int | None = Field(
        None, description="now - newest block_timestamp; grows naturally between on-chain transfers"
    )
    pipeline_latency_seconds: float | None = Field(
        None, description="avg(ingested_at - inserted_at) over the last hour: Kafka producer -> ClickHouse"
    )
