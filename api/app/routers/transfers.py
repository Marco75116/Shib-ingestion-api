from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..core.constants import MAX_ROWS
from ..core.db import Database, get_db
from ..core.params import MAX_RANGE_HOURS, RANGE_DOC, parse_range
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
    range_: str | None = Query(None, alias="range", description=f"{RANGE_DOC}. Default 7d"),
    hours: int | None = Query(None, ge=1, le=MAX_RANGE_HOURS, deprecated=True, description="use range"),
    limit: int = Query(50, ge=1, le=MAX_ROWS, description="max transfers returned; frequency counts them all"),
    db: Database = Depends(get_db),
):
    if range_ is not None:
        total_hours = parse_range(range_)
    elif hours is not None:
        total_hours, range_ = hours, f"{hours}h"
    else:
        total_hours, range_ = 24 * 7, "7d"
    return AmountTransfers(
        amount=amount, tolerance=tolerance, range=range_,
        **query_transfers_by_amount(db, amount, tolerance, total_hours, limit),
    )
