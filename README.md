# bubblemaps-test

SHIB transfer pipeline: Confluent Kafka → ClickHouse → FastAPI, deployed on a single k3s VM.

## Transfer-count alert job

**Goal.** Prove every hour that ClickHouse holds exactly the SHIB transfers that exist on chain,
by comparing against an independent source: the SQD portal API.

`job/check.py` runs as a CronJob at 20 past every hour. Run it by hand with `make alert-check`;
list past runs and any ALERT lines with `make alerts`.

### Alert of 2026-10-20, hour 16:00–17:00 UTC: one extra row, caused by a reorg

**Trigger.** The 17:20 run reported `sqd=171 clickhouse=172 diff=1`.

**Investigation.** One transaction,
[0xc938d0…](https://etherscan.io/tx/0xc938d00a5155f8ff772b30e112bbe4c8cab5a3dc5a16b3523913e08d25ab4f3a),
appears twice in Kafka with two different `unique_id`s and `block_timestamp`s (16:46:11 and
16:47:35). On chain it exists once, in block [26235088](https://etherscan.io/block/26235088)
at 16:47:35. The block at 16:46:11 was dropped by a reorg
([slot 15474229](https://beaconcha.in/slot/15474229)).
