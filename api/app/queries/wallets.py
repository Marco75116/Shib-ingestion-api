from datetime import datetime
from typing import Literal

from ..core.constants import MAX_ROWS
from ..core.db import Database

Direction = Literal["all", "sent", "received"]


def query_wallet_transfers(
    db: Database, wallet: str, direction: Direction, limit: int, before: datetime | None
) -> list[dict]:
    limit = min(limit, MAX_ROWS)
    where = "wallet = {wallet:String}"
    if direction != "all":
        where += " AND direction = {direction:String}"
    if before is not None:
        where += " AND block_timestamp < {before:DateTime64(3)}"
    rows = db.query(
        f"""
        SELECT block_timestamp, direction, counterparty, amount, tx_hash, unique_id
        FROM transfers_by_wallet
        WHERE {where}
        ORDER BY block_timestamp DESC, unique_id DESC
        LIMIT {{fetch:UInt32}}
        """,
        {"wallet": wallet, "direction": direction, "before": before, "fetch": limit * 2},
    )
    # Kafka is at-least-once: drop duplicates not yet merged by ReplacingMergeTree, then cut to `limit`.
    seen: set[tuple[str, str]] = set()
    unique = [r for r in rows if (key := (r["unique_id"], r["direction"])) not in seen and not seen.add(key)]
    return unique[:limit]


def query_wallet_stats(db: Database, wallet: str) -> dict:
    return db.one(
        """
        SELECT
            sum(sent_count)           AS sent_count,
            sum(sent_volume)          AS sent_volume,
            sum(received_count)       AS received_count,
            sum(received_volume)      AS received_volume,
            uniqMerge(counterparties) AS counterparties,
            min(first_seen)           AS first_seen,
            max(last_seen)            AS last_seen,
            nullIf(argMinMerge(first_funder), '') AS first_funder,
            min(first_received_at)    AS first_received_at
        FROM wallet_stats
        WHERE wallet = {wallet:String}
        """,
        {"wallet": wallet},
    )


def query_funder_stats(db: Database, funder: str) -> dict:
    return db.one(
        "SELECT seeded_wallets, first_seeded, last_seeded FROM funder_stats WHERE funder = {funder:String}",
        {"funder": funder},
    )


def query_wallet_siblings(db: Database, funder: str, exclude: str, limit: int) -> list[dict]:
    return db.query(
        """
        WITH sib AS
        (
            SELECT wallet, first_received_at
            FROM funder_wallets
            WHERE funder = {funder:String} AND wallet != {exclude:String}
            ORDER BY first_received_at
            LIMIT {limit:UInt32}
        )
        SELECT
            sib.wallet                      AS wallet,
            sib.first_received_at           AS first_received_at,
            ifNull(s.received_count, 0)     AS received_count,
            ifNull(s.received_volume, 0)    AS received_volume,
            ifNull(s.counterparties, 0)     AS counterparties
        FROM sib
        LEFT JOIN
        (
            SELECT wallet, sum(received_count) AS received_count, sum(received_volume) AS received_volume,
                   uniqMerge(counterparties) AS counterparties
            FROM wallet_stats
            WHERE wallet IN (SELECT wallet FROM sib)
            GROUP BY wallet
        ) AS s ON s.wallet = sib.wallet
        ORDER BY first_received_at
        """,
        {"funder": funder, "exclude": exclude, "limit": min(limit, MAX_ROWS)},
    )

LinkOrder = Literal["volume", "transfers", "last_seen"]
LINK_ORDER = {"volume": "volume DESC", "transfers": "transfers DESC", "last_seen": "last_seen DESC"}


def _neighbors(param: str) -> str:
    """Counterparties of the wallet bound to `param`: one primary-key range read on wallet_links."""
    return f"""
        SELECT
            counterparty,
            sum(sent_count)               AS sent_count,
            sum(sent_volume)              AS sent_volume,
            sum(received_count)           AS received_count,
            sum(received_volume)          AS received_volume,
            sent_count + received_count   AS transfers,
            sent_volume + received_volume AS volume,
            min(first_seen)               AS first_seen,
            max(last_seen)                AS last_seen
        FROM wallet_links
        WHERE wallet = {{{param}:String}}
        GROUP BY counterparty
    """


def query_wallet_links(db: Database, wallet: str, limit: int, order: LinkOrder) -> list[dict]:
    return db.query(
        f"""
        WITH links AS
        (
            {_neighbors("wallet")}
            ORDER BY {LINK_ORDER[order]}
            LIMIT {{limit:UInt32}}
        )
        SELECT links.*, ifNull(stats.counterparties, 0) AS counterparty_links
        FROM links
        LEFT JOIN
        (
            SELECT wallet, uniqMerge(counterparties) AS counterparties
            FROM wallet_stats
            WHERE wallet IN (SELECT counterparty FROM links)
            GROUP BY wallet
        ) AS stats ON stats.wallet = links.counterparty
        ORDER BY {LINK_ORDER[order]}
        """,
        {"wallet": wallet, "limit": min(limit, MAX_ROWS)},
    )


def query_direct_link(db: Database, address: str, other: str) -> dict:
    return db.one(
        """
        SELECT
            sum(sent_count)      AS sent_count,
            sum(sent_volume)     AS sent_volume,
            sum(received_count)  AS received_count,
            sum(received_volume) AS received_volume,
            min(first_seen)      AS first_seen,
            max(last_seen)       AS last_seen
        FROM wallet_links
        WHERE wallet = {address:String} AND counterparty = {other:String}
        """,
        {"address": address, "other": other},
    )


def query_common_counterparties(db: Database, address: str, other: str, limit: int) -> list[dict]:
    return db.query(
        f"""
        WITH
            la AS ({_neighbors("address")}),
            lb AS ({_neighbors("other")})
        SELECT
            la.counterparty                 AS counterparty,
            la.transfers                    AS transfers_with_address,
            la.volume                       AS volume_with_address,
            lb.transfers                    AS transfers_with_other,
            lb.volume                       AS volume_with_other,
            ifNull(stats.counterparties, 0) AS counterparty_links
        FROM la
        INNER JOIN lb ON la.counterparty = lb.counterparty
        LEFT JOIN
        (
            SELECT wallet, uniqMerge(counterparties) AS counterparties
            FROM wallet_stats
            WHERE wallet IN (SELECT counterparty FROM la)
            GROUP BY wallet
        ) AS stats ON stats.wallet = la.counterparty
        WHERE la.counterparty NOT IN ({{address:String}}, {{other:String}})
        ORDER BY volume_with_address + volume_with_other DESC
        LIMIT {{limit:UInt32}}
        """,
        {"address": address, "other": other, "limit": min(limit, MAX_ROWS)},
    )
