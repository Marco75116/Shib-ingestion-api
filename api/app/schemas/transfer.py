from datetime import datetime

from pydantic import BaseModel, Field


class Transfer(BaseModel):
    block_timestamp: datetime
    tx_hash: str
    from_address: str
    to_address: str
    amount: float


class AmountTransfers(BaseModel):
    amount: float
    tolerance: float
    hours: int
    frequency: int = Field(description="transfers carrying this amount in the window; rare amounts are signatures")
    senders: int
    receivers: int
    transfers: list[Transfer]
