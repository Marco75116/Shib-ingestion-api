"""Read the topic directly with the API key, no UI needed.

  python read_offsets.py 5:10295 0:78351          print the messages at these partition:offset
  python read_offsets.py --find <text>            scan every retained message, print the ones containing <text>
                                                  (a tx hash, an address, a block_timestamp like '2026-10-20 16:47')
Env: BROKER, TOPIC, KAFKA_API_KEY, KAFKA_API_SECRET. Used from the Makefile: make kafka-read / make kafka-find.
"""
import json, os, sys, time
from confluent_kafka import Consumer, TopicPartition, OFFSET_BEGINNING

conf = {
    "bootstrap.servers": os.environ["BROKER"], "security.protocol": "SASL_SSL", "sasl.mechanisms": "PLAIN",
    "sasl.username": os.environ["KAFKA_API_KEY"], "sasl.password": os.environ["KAFKA_API_SECRET"],
    "group.id": "bubblemaps-inspect", "enable.auto.commit": False, "auto.offset.reset": "earliest",
}
topic = os.environ["TOPIC"]
c = Consumer(conf)


def show(m):
    _, ts = m.timestamp()
    print(f"--- partition {m.partition()} offset {m.offset()} kafka_time {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts / 1000))}Z")
    print(json.dumps(json.loads(m.value()), indent=2))


if sys.argv[1:2] == ["--find"]:
    needle = sys.argv[2]
    md = c.list_topics(topic, timeout=15).topics[topic]
    parts = []
    for p in md.partitions:
        lo, hi = c.get_watermark_offsets(TopicPartition(topic, p), timeout=15)
        parts.append((p, lo, hi))
    c.assign([TopicPartition(topic, p, OFFSET_BEGINNING) for p, _, _ in parts])
    remaining = {p: hi for p, lo, hi in parts if hi > lo}
    total = hits = 0
    while remaining:
        m = c.poll(10)
        if m is None:
            break
        if m.error():
            continue
        total += 1
        if needle in m.value().decode():
            hits += 1
            show(m)
        if m.offset() + 1 >= remaining.get(m.partition(), 0):
            remaining.pop(m.partition(), None)
    print(f"=== scanned {total} retained messages across {len(parts)} partitions, {hits} match '{needle}'")
else:
    for spec in sys.argv[1:]:
        part, off = map(int, spec.split(":"))
        c.assign([TopicPartition(topic, part, off)])
        m = c.poll(15)
        if m is None or m.error():
            print(f"--- partition {part} offset {off}: nothing")
        else:
            show(m)
c.close()
