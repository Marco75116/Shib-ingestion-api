import re

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.db import Database, get_db
from ..queries.stats import Bucket, query_timeseries
from ..schemas.stats import TimeBucket

router = APIRouter(prefix="/stats", tags=["stats"])

MAX_RANGE_HOURS = 24 * 30
RANGE_RE = re.compile(r"^(\d+)([hd])$")
AUTO_DAILY_FROM_HOURS = 48  # ranges longer than this default to daily buckets


def parse_range(value: str) -> int:
    m = RANGE_RE.match(value)
    if not m:
        raise HTTPException(422, "range must look like 24h, 7d or 30d")
    n, unit = int(m.group(1)), m.group(2)
    hours = n * 24 if unit == "d" else n
    if not 1 <= hours <= MAX_RANGE_HOURS:
        raise HTTPException(422, f"range must be between 1h and {MAX_RANGE_HOURS // 24}d")
    return hours


@router.get(
    "/timeseries",
    response_model=list[TimeBucket],
    summary="Transfers, volume and active wallets per bucket over a range",
)
def timeseries(
    range_: str | None = Query(None, alias="range", description="how far back to look: 24h, 7d, 30d (max 30d). Default 24h"),
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
