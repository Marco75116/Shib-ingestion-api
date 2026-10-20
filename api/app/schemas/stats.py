from datetime import datetime

from pydantic import BaseModel


class TimeBucket(BaseModel):
    bucket: datetime
    transfers: int
    volume: float
    senders: int
    receivers: int

