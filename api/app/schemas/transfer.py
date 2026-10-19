from datetime import datetime

from pydantic import BaseModel


class Transfer(BaseModel):
    block_timestamp: datetime
    tx_hash: str
    from_address: str
    to_address: str
    amount: float
