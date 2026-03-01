"""
Kafka consumer for materialising the AuditLogRead projection.
 
Run this as: python consumer.py
It runs indefinitely, processing messages one at a time.
 
Offset commit strategy: manual, AFTER successful DB write.
On any unhandled DB error: log, do NOT commit, allow Kafka to redeliver.
On deserialisation error: log, commit anyway (bad message will never be fixed
    by retrying; send to dead-letter topic instead).
"""
import os
import sys
import logging
import signal
import time
 
# ── Bootstrap Django FIRST, before any model imports ────────────────────
import django_setup
django_setup.setup()
 
# ── Now safe to import Django models and project logic ──────────────────
from confluent_kafka import Consumer, KafkaError, KafkaException
from deserialise import unwrap_debezium_json, DeserialisationError
from project import dispatch_event, ProjectionError
 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('projection-consumer')
 
 
# ── Configuration from environment variables ─────────────────────────────
KAFKA_BOOTSTRAP   = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
KAFKA_TOPIC       = os.environ.get('KAFKA_TOPIC', 'outbox.event.AuditLog')
CONSUMER_GROUP_ID = os.environ.get('CONSUMER_GROUP_ID', 'audit-projection-consumer')
POLL_TIMEOUT_SEC  = float(os.environ.get('POLL_TIMEOUT_SEC', '1.0'))
 
 
def build_consumer() -> Consumer:
    return Consumer({
        'bootstrap.servers':     KAFKA_BOOTSTRAP,
        'group.id':              CONSUMER_GROUP_ID,
        'auto.offset.reset':     'earliest',  # on first start, read from beginning
        'enable.auto.commit':    False,        # CRITICAL: manual commits only
        'session.timeout.ms':    30000,
        'max.poll.interval.ms':  300000,
        # Reconnect on broker disconnect
        'socket.keepalive.enable': True,
    })
 
 
def process_message(consumer: Consumer, msg) -> None:
    """
    Process one Kafka message:
      1. Deserialise
      2. Project to read DB
      3. Commit offset
 
    Raises on DB errors (offset NOT committed — message will be redelivered).
    Commits and skips on deserialisation errors (retrying a corrupt message
    will never succeed).
    """
    topic     = msg.topic()
    partition = msg.partition()
    offset    = msg.offset()
    key       = msg.key().decode('utf-8') if msg.key() else '<no key>'
 
    log.info(f"Received: topic={topic} partition={partition} offset={offset} key={key}")

    # Corrected code in consumer.py:
    # ── Step 1: Deserialise ──────────────────────────────────────────────
    try:
        event = unwrap_debezium_json(msg.value())
    except DeserialisationError as e:
        log.error(f"Deserialisation failed at offset={offset}: {e}")
        log.error(f"Raw value (first 500 bytes): {msg.value()[:500]}")
        # IMPORTANT: Commit the offset even on deserialisation failure.
        # A corrupt message will NEVER be fixed by retrying it.
        # In production, write it to a dead-letter topic before committing.
        consumer.commit(message=msg, asynchronous=False)
        log.warning(f"Committed offset={offset} for corrupt message (skipped).")
        return
 
    # ── Step 2: Project ──────────────────────────────────────────────────
    try:
        created = dispatch_event(event)
        status  = 'INSERTED' if created else 'UPSERTED(idempotent)'
        log.info(f"Projected id={event.get('id')} [{status}]")
    except ProjectionError as e:
        # Projection logic error — bad event structure.
        # Commit and skip (same rationale as DeserialisationError).
        log.error(f"ProjectionError at offset={offset}: {e}")
        consumer.commit(message=msg, asynchronous=False)
        log.warning(f"Committed offset={offset} for invalid event (skipped).")
        return
    except Exception as e:
        # DB error, network error, etc.
        # Do NOT commit — let Kafka redeliver after consumer restarts.
        log.error(f"DB error projecting offset={offset}: {e}", exc_info=True)
        raise   # propagate to main loop, which will exit and let Docker restart
 
    # ── Step 3: Commit offset AFTER successful write ─────────────────────
    # asynchronous=False means we wait for broker acknowledgement.
    # Slower but correct. For high throughput, batch commits are an option.
    consumer.commit(message=msg, asynchronous=False)
    log.info(f"Committed offset={offset}")
 
 
def run():
    consumer = build_consumer()
    consumer.subscribe([KAFKA_TOPIC])
    log.info(f"Subscribed to topic: {KAFKA_TOPIC}")
    log.info(f"Consumer group: {CONSUMER_GROUP_ID}")
 
    # Graceful shutdown on SIGTERM (sent by Docker on container stop)
    shutdown = {'requested': False}
    def handle_sigterm(sig, frame):
        log.info("SIGTERM received — shutting down gracefully.")
        shutdown['requested'] = True
    signal.signal(signal.SIGTERM, handle_sigterm)
 
    try:
        while not shutdown['requested']:
            msg = consumer.poll(timeout=POLL_TIMEOUT_SEC)
 
            if msg is None:
                continue  # No message this poll cycle — normal
 
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition — not an error, just caught up
                    log.debug(f"End of partition {msg.partition()} offset {msg.offset()}")
                    continue
                else:
                    log.error(f"Kafka error: {msg.error()}")
                    raise KafkaException(msg.error())
 
            process_message(consumer, msg)
 
    except KeyboardInterrupt:
        log.info("Keyboard interrupt — stopping.")
    finally:
        # Close cleanly: commits any pending offsets, leaves the consumer group
        consumer.close()
        log.info("Consumer closed.")
 
 
if __name__ == '__main__':
    run()