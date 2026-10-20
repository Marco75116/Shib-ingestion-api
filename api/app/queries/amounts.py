def amount_predicate(amounts: list[float], tolerance: float) -> tuple[str, dict]:
    """SQL predicate on the `amount` key column: exact IN set, or OR of ranges when a tolerance is given."""
    if tolerance == 0:
        return "amount IN {amounts:Array(Float64)}", {"amounts": amounts}
    clauses, params = [], {}
    for i, a in enumerate(amounts):
        clauses.append(f"(amount BETWEEN {{lo{i}:Float64}} AND {{hi{i}:Float64}})")
        params[f"lo{i}"], params[f"hi{i}"] = a * (1 - tolerance), a * (1 + tolerance)
    return "(" + " OR ".join(clauses) + ")", params
