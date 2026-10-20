from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WalletTransfer(BaseModel):
    block_timestamp: datetime
    direction: Literal["sent", "received"]
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


class WalletLink(BaseModel):
    counterparty: str
    transfers: int
    volume: float
    sent_count: int = Field(description="address -> counterparty")
    sent_volume: float
    received_count: int = Field(description="counterparty -> address")
    received_volume: float
    first_seen: datetime
    last_seen: datetime
    counterparty_links: int = Field(description="how many distinct wallets the counterparty deals with")
    is_hub: bool = Field(description="counterparty looks like an exchange or contract")


class WalletLinks(BaseModel):
    address: str
    links: list[WalletLink]


class DirectLink(BaseModel):
    sent_count: int = Field(description="address -> other")
    sent_volume: float
    received_count: int = Field(description="other -> address")
    received_volume: float
    first_seen: datetime
    last_seen: datetime


class CommonCounterparty(BaseModel):
    counterparty: str
    transfers_with_address: int
    volume_with_address: float
    transfers_with_other: int
    volume_with_other: float
    is_hub: bool


class WalletPair(BaseModel):
    address: str
    other: str
    degree: Literal[1, 2] | None = Field(description="1 = direct transfers, 2 = shared counterparty, null = no link found")
    direct: DirectLink | None
    common_counterparties: list[CommonCounterparty]
