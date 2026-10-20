"""Print raw messages from the topic by partition:offset. Used from the Makefile: make kafka-read AT="5:10295 0:78351"."""
import json, os, sys
from confluent_kafka import Consumer, TopicPartition
c = Consumer({
    "bootstrap.servers": os.environ["BROKER"], "security.protocol": "SASL_SSL", "sasl.mechanisms": "PLAIN",
    "sasl.username": os.environ["KAFKA_API_KEY"], "sasl.password": os.environ["KAFKA_API_SECRET"],
    "group.id": "bubblemaps-inspect", "enable.auto.commit": False,
})
topic = os.environ["TOPIC"]
for spec in sys.argv[1:]:
    part, off = map(int, spec.split(":"))
    c.assign([TopicPartition(topic, part, off)])
    m = c.poll(15)
    print(f"--- partition {part} offset {off}:", end=" ")
    if m is None or m.error(): print("nothing"); continue
    ts_type, ts = m.timestamp()
    print(f"kafka timestamp {ts} key={m.key()}")
    print(json.dumps(json.loads(m.value()), indent=2))
c.close()
