from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.constants import HUB_COUNTERPARTIES, MAX_ROWS
from ..core.db import Database, get_db
from ..queries.wallets import (
    Direction,
    LinkOrder,
    query_common_counterparties,
    query_direct_link,
    query_funder_stats,
    query_wallet_links,
    query_wallet_siblings,
    query_wallet_stats,
    query_wallet_transfers,
)
from ..schemas.wallets import WalletLinks, WalletPair, WalletSiblings, WalletStats, WalletTransfer
from .deps import valid_address, valid_other

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("/{address}/transfers", response_model=list[WalletTransfer])
def wallet_transfers(
    address: str = Depends(valid_address),
    direction: Direction = "all",
    limit: int = Query(50, ge=1, le=MAX_ROWS),
    before: datetime | None = Query(None, description="keyset pagination: only transfers older than this"),
    db: Database = Depends(get_db),
):
    return query_wallet_transfers(db, address, direction, limit, before)


@router.get("/{address}/stats", response_model=WalletStats)
def wallet_stats(address: str = Depends(valid_address), db: Database = Depends(get_db)):
    stats = query_wallet_stats(db, address)
    if not stats or stats["sent_count"] + stats["received_count"] == 0:
        raise HTTPException(status_code=404, detail="wallet has no transfers in the retained window")
    return WalletStats(
        address=address,
        net_flow=stats["received_volume"] - stats["sent_volume"],
        seeded_wallets=query_funder_stats(db, address).get("seeded_wallets", 0),
        **stats,
    )


@router.get("/{address}/links", response_model=WalletLinks, summary="Direct counterparties of a wallet")
def wallet_links(
    address: str = Depends(valid_address),
    limit: int = Query(20, ge=1, le=200),
    order: LinkOrder = "volume",
    db: Database = Depends(get_db),
):
    rows = query_wallet_links(db, address, limit, order)
    return WalletLinks(
        address=address,
        links=[{**r, "is_hub": r["counterparty_links"] > HUB_COUNTERPARTIES} for r in rows],
    )


@router.get("/{address}/links/{other}", response_model=WalletPair, summary="Link between two wallets")
def wallet_pair(
    address: str = Depends(valid_address),
    other: str = Depends(valid_other),
    limit: int = Query(20, ge=1, le=200),
    db: Database = Depends(get_db),
):
    direct = query_direct_link(db, address, other)
    has_direct = bool(direct) and (direct["sent_count"] + direct["received_count"]) > 0
    common = [
        {**r, "is_hub": r["counterparty_links"] > HUB_COUNTERPARTIES}
        for r in query_common_counterparties(db, address, other, limit)
    ]
    return WalletPair(
        address=address,
        other=other,
        degree=1 if has_direct else (2 if common else None),
        direct=direct if has_direct else None,
        common_counterparties=common,
    )


@router.get("/{address}/siblings", response_model=WalletSiblings, summary="Wallets seeded by the same first funder")
def wallet_siblings(
    address: str = Depends(valid_address),
    limit: int = Query(50, ge=1, le=MAX_ROWS),
    db: Database = Depends(get_db),
):
    stats = query_wallet_stats(db, address)
    if not stats or stats["sent_count"] + stats["received_count"] == 0:
        raise HTTPException(status_code=404, detail="wallet has no transfers in the retained window")
    funder = stats["first_funder"]
    if funder is None:
        return WalletSiblings(address=address, first_funder=None, first_received_at=None,
                              funder_is_hub=False, seeded_wallets=0, siblings=[])
    funder_is_hub = query_wallet_stats(db, funder).get("counterparties", 0) > HUB_COUNTERPARTIES
    rows = [] if funder_is_hub else query_wallet_siblings(db, funder, address, limit)
    return WalletSiblings(
        address=address,
        first_funder=funder,
        first_received_at=stats["first_received_at"],
        funder_is_hub=funder_is_hub,
        seeded_wallets=query_funder_stats(db, funder).get("seeded_wallets", 0),
        siblings=[{**r, "is_hub": r["counterparties"] > HUB_COUNTERPARTIES} for r in rows],
    )

