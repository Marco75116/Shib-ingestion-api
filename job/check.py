"""Hourly check: SHIB Transfer logs on SQD Portal vs rows in ClickHouse for the last finalized hour.

Prints "OK ..." or "ALERT ..." (exit 1). Only reads one hour, bounded on the transfers primary key.
Standard library only, so it runs in a plain python:3.12-slim image.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SQD_PORTAL_URL = os.environ.get("SQD_PORTAL_URL", "https://portal.sqd.dev/datasets/ethereum-mainnet")
CH_URL = os.environ.get("CH_URL", "http://clickhouse:8123")
CH_USER = os.environ.get("CH_USER", "api")
CH_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
HOURS_AGO = int(os.environ.get("HOURS_AGO", "1"))
SHIB = "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
USER_AGENT = "bubblemaps-job/0.1"  # Cloudflare rejects the default Python-urllib agent
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}  # the Portal answers 429/529 when busy


def http(url: str, body: bytes | None = None, headers: dict | None = None, tries: int = 5) -> str:
    req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode()
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUSES or attempt == tries:
                raise
            time.sleep(float(exc.headers.get("Retry-After") or 2 * attempt))
        except urllib.error.URLError:
            if attempt == tries:
                raise
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def block_at(ts: int) -> int:
    return json.loads(http(f"{SQD_PORTAL_URL}/timestamps/{ts}/block"))["block_number"]


def sqd_count(from_block: int, to_block: int) -> int:
    count, block = 0, from_block
    while block <= to_block:
        query = {
            "type": "evm",
            "fromBlock": block,
            "toBlock": to_block,
            "fields": {"block": {"number": True}, "log": {"logIndex": True}},
            "logs": [{"address": [SHIB], "topic0": [TRANSFER]}],
        }
        body = http(
            f"{SQD_PORTAL_URL}/finalized-stream",
            json.dumps(query).encode(),
            {"Content-Type": "application/json"},
        )
        lines = [json.loads(line) for line in body.splitlines() if line]
        if not lines:  # 204: nothing left in the finalized range
            break
        count += sum(len(b.get("logs", [])) for b in lines)
        block = lines[-1]["header"]["number"] + 1  # the stream may stop early: resume after the last block
    return count


def clickhouse_count(start: int, end: int) -> int:
    sql = (
        "SELECT count() FROM transfers FINAL "
        f"WHERE block_timestamp >= toDateTime({start}, 'UTC') AND block_timestamp < toDateTime({end}, 'UTC')"
    )
    auth = base64.b64encode(f"{CH_USER}:{CH_PASSWORD}".encode()).decode()
    return int(http(f"{CH_URL}/?database=shib", sql.encode(), {"Authorization": f"Basic {auth}"}))


def main() -> int:
    end = int(time.time()) // 3600 * 3600 - (HOURS_AGO - 1) * 3600
    start = end - 3600
    hour = datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    from_block, to_block = block_at(start), block_at(end) - 1
    finalized = json.loads(http(f"{SQD_PORTAL_URL}/finalized-head"))["number"]
    if to_block > finalized:
        print(f"SKIP hour={hour} not finalized yet (to={to_block} finalized={finalized})")
        return 0

    sqd_n = sqd_count(from_block, to_block)
    ch_n = clickhouse_count(start, end)
    fields = f"hour={hour} blocks={from_block}..{to_block} sqd={sqd_n} clickhouse={ch_n}"
    if sqd_n == ch_n:
        print(f"OK {fields}")
        return 0
    print(f"ALERT shib transfer count mismatch {fields} diff={ch_n - sqd_n}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
