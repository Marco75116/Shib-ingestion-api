from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.constants import HUB_COUNTERPARTIES, MAX_ROWS
from ..core.db import Database, get_db
from ..queries.wallets import (
    Direction,
    LinkOrder,
    query_common_counterparties,
    query_direct_link,
    query_wallet_links,
    query_wallet_stats,
    query_wallet_transfers,
)
from ..schemas.wallets import WalletLinks, WalletPair, WalletStats, WalletTransfer
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
