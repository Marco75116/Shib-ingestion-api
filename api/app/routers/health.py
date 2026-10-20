from fastapi import APIRouter, Depends, Response

from ..core.db import Database, get_db
from ..queries.health import query_ingestion_status
from ..schemas.health import Health

router = APIRouter(tags=["ops"])


@router.get("/live", include_in_schema=False)
def live():
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
def ready(response: Response, db: Database = Depends(get_db)):
    """Readiness probe: ClickHouse answers. Cheap on purpose; /health carries the ingestion detail."""
    try:
        db.client.command("SELECT 1")
    except Exception as exc:
        response.status_code = 503
        return {"status": "degraded", "clickhouse": f"{type(exc).__name__}: {exc}"[:200]}
    return {"status": "ok"}


@router.get("/health", response_model=Health)
def health(response: Response, db: Database = Depends(get_db)):
    try:
        status = query_ingestion_status(db)
    except Exception as exc:
        response.status_code = 503
        return Health(status="degraded", clickhouse=f"{type(exc).__name__}: {exc}"[:200])
    return Health(status="ok", clickhouse="ok", **status)
