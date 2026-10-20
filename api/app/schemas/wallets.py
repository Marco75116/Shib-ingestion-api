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
    first_funder: str | None = Field(description="first wallet that ever sent SHIB to this address")
    first_received_at: datetime | None
    seeded_wallets: int = Field(description="wallets whose first SHIB came from this address (refreshed every 10 min)")


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


class Similarity(BaseModel):
    shared_counterparties: int = Field(description="wallets both deal with, hubs excluded")
    degree_address: int = Field(description="distinct counterparties of address, hubs excluded")
    degree_other: int
    union: int
    jaccard: float = Field(description="shared / union; punishes asymmetric pairs")
    overlap: float = Field(description="shared / smaller degree; 1.0 = one address book contains the other")


class WalletPair(BaseModel):
    address: str
    other: str
    degree: Literal[1, 2] | None = Field(description="1 = direct transfers, 2 = shared counterparty, null = no link found")
    direct: DirectLink | None
    common_counterparties: list[CommonCounterparty]
    similarity: Similarity


class Sibling(BaseModel):
    wallet: str
    first_received_at: datetime
    received_count: int
    received_volume: float
    counterparties: int
    is_hub: bool


class WalletSiblings(BaseModel):
    address: str
    first_funder: str | None
    first_received_at: datetime | None
    funder_is_hub: bool = Field(description="funder is an exchange-like wallet; siblings are not meaningful")
    seeded_wallets: int = Field(description="total wallets seeded by first_funder, including this one")
    siblings: list[Sibling] = Field(description="other wallets whose first SHIB also came from first_funder")


class SimilarWallet(BaseModel):
    wallet: str
    shared_counterparties: int
    degree: int = Field(description="all counterparties of the candidate, hubs included")
    overlap: float
    jaccard: float
    is_direct_link: bool = Field(description="the candidate also transacted with address directly")


class SimilarWallets(BaseModel):
    address: str
    degree: int = Field(description="address's non-hub counterparties that were expanded")
    min_shared: int
    results: list[SimilarWallet]
