from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..core.constants import MAX_ROWS
from ..core.db import Database, get_db
from ..queries.wallets import Direction, query_wallet_transfers
from ..schemas.wallets import WalletTransfer
from .deps import valid_address

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
