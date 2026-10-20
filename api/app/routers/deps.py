import re

from fastapi import HTTPException, Path

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def valid_address(address: str = Path(description="Ethereum address: 0x + 40 hex chars")) -> str:
    if not ADDRESS_RE.match(address):
        raise HTTPException(status_code=422, detail="address must be 0x followed by 40 hex characters")
    return address.lower()
