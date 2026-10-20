"""Reset a consumer group to the earliest retained offset of a topic.

Usage: BROKER=... TOPIC=... GROUP=... KAFKA_API_KEY=... KAFKA_API_SECRET=... python reset_offsets.py
The group must be inactive (DETACH the ClickHouse Kafka table first).
"""
import os

from confluent_kafka import Consumer, ConsumerGroupTopicPartitions, TopicPartition
from confluent_kafka.admin import AdminClient

broker, topic, group = os.environ["BROKER"], os.environ["TOPIC"], os.environ["GROUP"]
conf = {
    "bootstrap.servers": broker,
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.environ["KAFKA_API_KEY"],
    "sasl.password": os.environ["KAFKA_API_SECRET"],
}

admin = AdminClient(conf)
partitions = admin.list_topics(topic, timeout=30).topics[topic].partitions

consumer = Consumer({**conf, "group.id": group})
targets = []
for p in partitions:
    low, high = consumer.get_watermark_offsets(TopicPartition(topic, p), timeout=30)
    targets.append(TopicPartition(topic, p, low))
    print(f"partition {p}: earliest={low} latest={high} -> reset to {low}")
consumer.close()

futures = admin.alter_consumer_group_offsets([ConsumerGroupTopicPartitions(group, targets)])
for _, fut in futures.items():
    fut.result()
print(f"group {group!r} reset to earliest on {len(targets)} partitions")
