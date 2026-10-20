from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.db import Database, get_db
from ..core.params import MAX_RANGE_HOURS, RANGE_DOC, parse_range
from ..queries.stats import Bucket, query_timeseries
from ..schemas.stats import TimeBucket

router = APIRouter(prefix="/stats", tags=["stats"])

AUTO_DAILY_FROM_HOURS = 48  # ranges longer than this default to daily buckets


@router.get(
    "/timeseries",
    response_model=list[TimeBucket],
    summary="Transfers, volume and active wallets per bucket over a range",
)
def timeseries(
    range_: str | None = Query(None, alias="range", description=f"{RANGE_DOC}. Default 24h"),
    bucket: Bucket | None = Query(None, description="size of each value: 1h or 1d. Default 1h up to 48h, else 1d"),
    hours: int | None = Query(None, ge=1, le=MAX_RANGE_HOURS, deprecated=True, description="use range"),
    interval: Bucket | None = Query(None, deprecated=True, description="use bucket"),
    db: Database = Depends(get_db),
):
    if range_ is not None:
        total_hours = parse_range(range_)
    elif hours is not None:
        total_hours = hours
    else:
        total_hours = 24

    bucket = bucket or interval or ("1h" if total_hours <= AUTO_DAILY_FROM_HOURS else "1d")
    if bucket == "1d" and total_hours < 24:
        raise HTTPException(422, "bucket=1d needs a range of at least 24h")

    return query_timeseries(db, bucket, total_hours)
