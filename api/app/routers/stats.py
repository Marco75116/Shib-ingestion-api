from fastapi import APIRouter, Depends, Query

from ..core.db import Database, get_db
from ..queries.stats import Interval, query_timeseries
from ..schemas.stats import TimeBucket

router = APIRouter(prefix="/stats", tags=["stats"])
MAX_HOURS = 24 * 30


@router.get("/timeseries", response_model=list[TimeBucket])
def timeseries(
    interval: Interval = "1h",
    hours: int = Query(24, ge=1, le=MAX_HOURS),
    db: Database = Depends(get_db),
):
    return query_timeseries(db, interval, hours)

