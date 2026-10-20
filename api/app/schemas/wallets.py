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


class WalletStats(BaseModel):
    address: str
    sent_count: int
    sent_volume: float
    received_count: int
    received_volume: float
    net_flow: float
    counterparties: int
    first_seen: datetime
    last_seen: datetime
