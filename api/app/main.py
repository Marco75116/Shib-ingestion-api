from fastapi import FastAPI

from .routers import health, transfers

app = FastAPI(title="SHIB transfers API", version="0.1.0")
app.include_router(health.router)
app.include_router(transfers.router)
