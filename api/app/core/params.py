import re

from fastapi import HTTPException

MAX_RANGE_HOURS = 24 * 30
RANGE_RE = re.compile(r"^(\d+)([hd])$")
RANGE_DOC = "how far back to look: 24h, 7d, 30d (max 30d)"


def parse_range(value: str) -> int:
    """'24h' / '7d' -> hours. Shared by every endpoint that takes a time window."""
    m = RANGE_RE.match(value)
    if not m:
        raise HTTPException(422, "range must look like 24h, 7d or 30d")
    n, unit = int(m.group(1)), m.group(2)
    hours = n * 24 if unit == "d" else n
    if not 1 <= hours <= MAX_RANGE_HOURS:
        raise HTTPException(422, f"range must be between 1h and {MAX_RANGE_HOURS // 24}d")
    return hours
