from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class WalletTransfer(BaseModel):
    block_timestamp: datetime
    direction: Literal["in", "out"]
    counterparty: str
    amount: float
    tx_hash: str
    unique_id: str
