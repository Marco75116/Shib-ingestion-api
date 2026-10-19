from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.db import database
from .routers import health, transfers


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.connect()
    yield
    database.close()


app = FastAPI(title="SHIB transfers API", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(transfers.router)
