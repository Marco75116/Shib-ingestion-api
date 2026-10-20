from ..core.constants import MAX_ROWS
from ..core.db import Database


def amount_predicate(amounts: list[float], tolerance: float) -> tuple[str, dict]:
    """SQL predicate on the `amount` key column: exact IN set, or OR of ranges when a tolerance is given."""
    if tolerance == 0:
        return "amount IN {amounts:Array(Float64)}", {"amounts": amounts}
    clauses, params = [], {}
    for i, a in enumerate(amounts):
        clauses.append(f"(amount BETWEEN {{lo{i}:Float64}} AND {{hi{i}:Float64}})")
        params[f"lo{i}"], params[f"hi{i}"] = a * (1 - tolerance), a * (1 + tolerance)
    return "(" + " OR ".join(clauses) + ")", params


def query_transfers_by_amount(db: Database, amount: float, tolerance: float, hours: int, limit: int) -> dict:
    """Every transfer carrying `amount` (within tolerance) in the window: a prefix read on transfers_by_amount."""
    predicate, params = amount_predicate([amount], tolerance)
    params = {**params, "hours": hours}
    where = f"{predicate} AND block_timestamp >= now() - INTERVAL {{hours:UInt32}} HOUR"
    stats = db.one(
        f"""
        SELECT count() AS frequency, uniqExact(from_address) AS senders, uniqExact(to_address) AS receivers
        FROM transfers_by_amount
        WHERE {where}
        """,
        params,
    )
    transfers = db.query(
        f"""
        SELECT block_timestamp, tx_hash, from_address, to_address, amount
        FROM transfers_by_amount
        WHERE {where}
        ORDER BY block_timestamp DESC
        LIMIT {{limit:UInt32}}
        """,
        {**params, "limit": min(limit, MAX_ROWS)},
    )
    return {**stats, "transfers": transfers}
