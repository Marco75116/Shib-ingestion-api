from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..core.constants import MAX_ROWS
from ..core.db import Database, get_db
from ..queries.amounts import query_transfers_by_amount
from ..queries.transfers import query_latest_transfers
from ..schemas.transfer import AmountTransfers, Transfer

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("/latest", response_model=list[Transfer])
def latest(
    limit: int = Query(20, ge=1, le=MAX_ROWS),
    since: datetime | None = Query(None, description="only transfers after this UTC datetime (default: last 7 days)"),
    db: Database = Depends(get_db),
):
    return query_latest_transfers(db, limit, since)


@router.get("/by-amount", response_model=AmountTransfers, summary="Who moved this exact amount")
def by_amount(
    amount: float = Query(gt=0, description="SHIB amount, e.g. 5339303.133208998"),
    tolerance: float = Query(0, ge=0, le=0.05, description="relative tolerance, 0.001 = 0.1%"),
    hours: int = Query(168, ge=1, le=720),
    limit: int = Query(50, ge=1, le=MAX_ROWS),
    db: Database = Depends(get_db),
):
    return AmountTransfers(amount=amount, tolerance=tolerance, hours=hours, **query_transfers_by_amount(db, amount, tolerance, hours, limit))
