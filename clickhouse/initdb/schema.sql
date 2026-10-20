CREATE DATABASE IF NOT EXISTS shib;

CREATE TABLE IF NOT EXISTS shib.kafka_transfers
(
    block_timestamp  DateTime64(3, 'UTC'),
    chain            String,
    contract_address String,
    from_address     String,
    to_address       String,
    amount           Float64,
    tx_hash          String,
    unique_id        String,
    inserted_at      DateTime64(3, 'UTC')
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list       = 'pkc-z1o60.europe-west1.gcp.confluent.cloud:9092',
    kafka_topic_list        = 'transfer_shib',
    kafka_group_name        = 'bubblemaps-marc',
    kafka_format            = 'JSONEachRow',
    kafka_num_consumers     = 1,
    kafka_handle_error_mode = 'stream';

CREATE TABLE IF NOT EXISTS shib.transfers
(
    block_timestamp DateTime64(3, 'UTC'),
    tx_hash         String,
    unique_id       String,
    from_address    String,
    to_address      String,
    amount_raw      Float64,
    amount          Float64,
    inserted_at     DateTime64(3, 'UTC'),
    ingested_at     DateTime64(3, 'UTC') DEFAULT now64(3),
    kafka_partition UInt16,
    kafka_offset    UInt64
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(block_timestamp)
ORDER BY (block_timestamp, unique_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS shib.mv_kafka_to_transfers
TO shib.transfers
AS
SELECT
    block_timestamp,
    lower(tx_hash)      AS tx_hash,
    unique_id,
    lower(from_address) AS from_address,
    lower(to_address)   AS to_address,
    amount              AS amount_raw,
    amount / 1e18       AS amount,
    inserted_at,
    _partition          AS kafka_partition,
    _offset             AS kafka_offset
FROM shib.kafka_transfers
WHERE _error = '';

CREATE TABLE IF NOT EXISTS shib.kafka_errors
(
    received_at     DateTime64(3, 'UTC') DEFAULT now64(3),
    topic           String,
    kafka_partition UInt16,
    kafka_offset    UInt64,
    raw_message     String,
    error           String
)
ENGINE = MergeTree
ORDER BY received_at;

CREATE MATERIALIZED VIEW IF NOT EXISTS shib.mv_kafka_errors
TO shib.kafka_errors
AS
SELECT
    _topic        AS topic,
    _partition    AS kafka_partition,
    _offset       AS kafka_offset,
    _raw_message  AS raw_message,
    _error        AS error
FROM shib.kafka_transfers
WHERE _error != '';

CREATE TABLE IF NOT EXISTS shib.transfers_hourly
(
    hour       DateTime('UTC'),
    transfers  SimpleAggregateFunction(sum, UInt64),
    volume     SimpleAggregateFunction(sum, Float64),
    max_amount SimpleAggregateFunction(max, Float64),
    senders    AggregateFunction(uniq, String),
    receivers  AggregateFunction(uniq, String)
)
ENGINE = AggregatingMergeTree
ORDER BY hour;

CREATE MATERIALIZED VIEW IF NOT EXISTS shib.mv_transfers_hourly
TO shib.transfers_hourly
AS
SELECT
    toStartOfHour(block_timestamp) AS hour,
    count()                        AS transfers,
    sum(amount)                    AS volume,
    max(amount)                    AS max_amount,
    uniqState(from_address)        AS senders,
    uniqState(to_address)          AS receivers
FROM shib.transfers
GROUP BY hour;

CREATE TABLE IF NOT EXISTS shib.transfers_by_wallet
(
    wallet          String,
    direction       Enum8('sent' = 1, 'received' = 2),
    block_timestamp DateTime64(3, 'UTC'),
    unique_id       String,
    tx_hash         String,
    counterparty    String,
    amount          Float64
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(block_timestamp)
ORDER BY (wallet, block_timestamp, unique_id, direction);

CREATE MATERIALIZED VIEW IF NOT EXISTS shib.mv_transfers_by_wallet_sent
TO shib.transfers_by_wallet
AS
SELECT from_address AS wallet, 'sent' AS direction, block_timestamp, unique_id, tx_hash, to_address AS counterparty, amount
FROM shib.transfers;

CREATE MATERIALIZED VIEW IF NOT EXISTS shib.mv_transfers_by_wallet_received
TO shib.transfers_by_wallet
AS
SELECT to_address AS wallet, 'received' AS direction, block_timestamp, unique_id, tx_hash, from_address AS counterparty, amount
FROM shib.transfers;

CREATE TABLE IF NOT EXISTS shib.wallet_stats
(
    wallet          String,
    sent_count      SimpleAggregateFunction(sum, UInt64),
    sent_volume     SimpleAggregateFunction(sum, Float64),
    received_count  SimpleAggregateFunction(sum, UInt64),
    received_volume SimpleAggregateFunction(sum, Float64),
    counterparties  AggregateFunction(uniq, String),
    first_seen      SimpleAggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen       SimpleAggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
ORDER BY wallet;

CREATE MATERIALIZED VIEW IF NOT EXISTS shib.mv_wallet_stats
TO shib.wallet_stats
AS
SELECT
    wallet,
    countIf(direction = 'sent')          AS sent_count,
    sumIf(amount, direction = 'sent')    AS sent_volume,
    countIf(direction = 'received')      AS received_count,
    sumIf(amount, direction = 'received') AS received_volume,
    uniqState(counterparty)          AS counterparties,
    min(block_timestamp)             AS first_seen,
    max(block_timestamp)             AS last_seen
FROM shib.transfers_by_wallet
GROUP BY wallet;

CREATE TABLE IF NOT EXISTS shib.wallet_links
(
    wallet          String,
    counterparty    String,
    sent_count      SimpleAggregateFunction(sum, UInt64),
    sent_volume     SimpleAggregateFunction(sum, Float64),
    received_count  SimpleAggregateFunction(sum, UInt64),
    received_volume SimpleAggregateFunction(sum, Float64),
    first_seen      SimpleAggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen       SimpleAggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
ORDER BY (wallet, counterparty);

CREATE MATERIALIZED VIEW IF NOT EXISTS shib.mv_wallet_links
TO shib.wallet_links
AS
SELECT
    wallet,
    counterparty,
    countIf(direction = 'sent')           AS sent_count,
    sumIf(amount, direction = 'sent')     AS sent_volume,
    countIf(direction = 'received')       AS received_count,
    sumIf(amount, direction = 'received') AS received_volume,
    min(block_timestamp)                  AS first_seen,
    max(block_timestamp)                  AS last_seen
FROM shib.transfers_by_wallet
GROUP BY wallet, counterparty;
