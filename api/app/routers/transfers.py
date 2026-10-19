from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..core.constants import MAX_ROWS
from ..core.db import Database, get_db
from ..queries.transfers import query_latest_transfers
from ..schemas.transfer import Transfer

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("/latest", response_model=list[Transfer])
def latest(
    limit: int = Query(20, ge=1, le=MAX_ROWS),
    since: datetime | None = Query(None, description="only transfers after this UTC datetime"),
    db: Database = Depends(get_db),
):
    return query_latest_transfers(db, limit, since)
