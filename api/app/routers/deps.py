import re

from fastapi import HTTPException, Path

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def normalize_address(value: str) -> str:
    if not ADDRESS_RE.match(value):
        raise HTTPException(status_code=422, detail="address must be 0x followed by 40 hex characters")
    return value.lower()


def valid_address(address: str = Path(description="Ethereum address: 0x + 40 hex chars")) -> str:
    return normalize_address(address)


def valid_other(other: str = Path(description="second Ethereum address")) -> str:
    return normalize_address(other)
