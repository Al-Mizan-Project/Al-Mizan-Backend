**Title:** `Audit service with CDC, CQRS, transactional outbox, and Redis caching`

---

## Summary

`audit_service` — a production-grade, append-only audit ledger built on Django, PostgreSQL, Debezium, Kafka, and Redis. It implements the full CQRS + CDC + Transactional Outbox pattern from scratch.

---

## Context & Motivation

Audit logs are a compliance and forensic requirement. They must satisfy:
- **Immutability** — no UPDATE or DELETE ever touches a written audit record
- **Strong consistency** — an event is either fully written or not written at all, never half-committed
- **Integrity verifiability** — every record is hash-chained; tampering is detectable
- **Read performance** — query endpoints must not hit the write database under load
- **Event propagation** — downstream systems receive audit events without coupling to Django internals

None of these can be achieved with a simple Django model + signals approach. This PR implements the correct architecture.

---

## Architecture Overview

```
Client
  │
  ├── POST /journaux-audit/create
  │       │
  │       ▼
  │   Django (audit_ledger)
  │   transaction.atomic('ledger')
  │     ├── INSERT → journaux_audit       (immutable ledger)
  │     └── INSERT → journaux_outbox      (transactional outbox)
  │                       │
  │                       ▼ (WAL — PostgreSQL logical replication)
  │                   Debezium (Kafka Connect)
  │                       │
  │                       ▼
  │                   Kafka topic: outbox.event.AuditLog
  │                       │
  │                       ▼
  │               projection-consumer
  │                       │
  │                       ▼ (idempotent UPSERT)
  │                   read_db.audit_read_projection
  │
  ├── GET  /journaux-audit/*
          │
          ├── Redis cache hit? ──► return cached response
          │
          └── Redis cache miss ──► query read_db ──► cache ──► return
```

### Infrastructure Details

- **Audit PostgreSQL**: Port 5434 (separate from shared infrastructure on 5433)
- **Shared Redis**: Port 6379 (used for caching read queries)
- **Django API**: Port 8000
- **Debezium Connect**: Port 8083
- **Kafka**: Internal only (9092 inside Docker network)

---

## What Changed

### New Files

```
audit_service/
├── audit_ledger/
│   ├── models.py           # AuditLog (immutable) + OutboxEvent
│   ├── services.py         # create_audit_log() — atomic write
│   ├── hashing.py          # SHA-256 hash chain computation
│   ├── repository.py       # ledger DB access layer
│   ├── permissions.py      # IsAuditWriter permission class
│   ├── signals.py          # post_save guard — blocks direct model saves
│   └── views.py            # POST /journaux-audit/create
│
├── audit_read/
│   ├── models.py           # AuditLogRead (read projection)
│   ├── views.py            # GET endpoints (list, detail, entity, user)
│   └── filters.py          # django-filter filterset for list endpoint
│
├── integrity/
│   ├── services.py         # hash chain verifier
│   ├── merkle.py           # Merkle tree builder for batch verification
│   └── views.py            # GET /verifier-integrite endpoints
│
├── common/
│   ├── db_router.py        # Routes ledger models → ledger_db, read → read_db
│   ├── cache.py            # Redis cache key builder + invalidation helpers
│   └── utils.py            # Shared utilities
│
├── config/
│   ├── settings.py         # Updated: multi-DB, Redis, Kafka env vars
│   └── urls.py             # All endpoint routes
│
projection-consumer/
├── Dockerfile
├── requirements.txt
├── consumer.py             # Kafka consumer main loop
├── deserialise.py          # Debezium JSON envelope unwrapping
├── project.py              # project_event() — upsert into read_db
└── django_setup.py         # Django ORM bootstrap for standalone script
│
postgres/
├── Dockerfile              # postgres:15 + WAL config
├── postgresql.conf         # wal_level=logical
└── init.sql                # CREATE PUBLICATION + ALTER ROLE
│
debezium/connectors/
└── outbox-connector.json   # Debezium connector config
│
docker-compose.yml          # All 7 services
```

### Modified Files

```
config/settings.py          # Added: Redis cache config, read DB, env-var hosts
config/urls.py              # Added: all endpoint routes
requirements.txt            # Added: django-redis, confluent-kafka, django-filter
```

---

## Cache Behaviour Per Endpoint

| Endpoint | Cache Key Pattern | TTL | Invalidated On |
|---|---|---|---|
| `GET /list` | `audit:list:{params_hash}` | 5 min | POST /create |
| `GET /{log_id}` | `audit:detail:{log_id}` | 5 min | Never (immutable record) |
| `GET /entity/{type}/{id}` | `audit:entity:{type}:{id}` | 5 min | POST /create |
| `GET /user/{user_id}` | `audit:user:{user_id}` | 5 min | POST /create |
| `GET /verifier-integrite` | `audit:integrity:global` | 5 min | POST /create |
| `GET /verifier-integrite/record/{id}` | `audit:integrity:record:{id}` | 5 min | Never (immutable record) |

**Note on `IGNORE_EXCEPTIONS: True`:** if Redis is unreachable, all cache reads return `None` and all cache writes silently fail. Every endpoint falls back to querying the database directly. The service stays functional; it just loses the cache performance benefit.

---

## Integrity Guarantee Summary

| Layer | Guarantee |
|---|---|
| `AuditLog.save()` override | Raises `ValidationError` on any UPDATE attempt |
| `AuditLog.delete()` override | Raises `ValidationError` on any DELETE attempt |
| `create_audit_log()` | Wraps ledger write + outbox write in `transaction.atomic('ledger')` |
| Hash chain | Every record encodes `hash_actuel` of the previous record — linear tamper evidence |
| Outbox pattern | Events emitted only after transaction commits — no dual-write race |
| `projection-consumer` | `enable.auto.commit=False` — offset committed only after successful DB write |
| UPSERT on read model | `update_or_create` by `id` — idempotent under at-least-once delivery |
| Integrity endpoints | Recompute hashes from raw fields against stored values — detects field-level tampering |

---

## How to Run

### Prerequisites

Start the shared infrastructure (PostgreSQL on port 5433 and Redis on port 6379):
```bash
cd ../../infrastructure
docker compose up -d
```

The audit service uses:
- **Shared PostgreSQL** (localhost:5433) with two databases: `audit_ledger` and `audit_read`
- **Shared Redis** (localhost:6379) for caching read queries

### Environment Variables

The service is configured in `docker-compose.yml` to use:
```
DB_HOST=host.docker.internal
DB_PORT=5433
DB_LEDGER_NAME=audit_ledger
DB_READ_NAME=audit_read
DB_LEDGER_USER=audit_user
DB_LEDGER_PASSWORD=audit_password
REDIS_URL=redis://:almizan_redis_password@host.docker.internal:6379/10
```

### Startup

```bash
# Navigate to audit service
cd audit_service

# Start Kafka infrastructure and Django
docker compose up --build -d

# Run migrations on shared PostgreSQL
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate ledger --database=ledger
docker compose exec web python manage.py migrate readstore --database=read

# Configure WAL on shared PostgreSQL for CDC
docker exec almizan_shared_postgres psql -U audit_user -d audit_ledger -c "CREATE PUBLICATION debezium_outbox_pub FOR TABLE journaux_outbox;"

# Register Debezium connector
Invoke-RestMethod -Method Post -ContentType "application/json" -Body (Get-Content -Raw ./debezium/connectors/outbox-connector.json) -Uri "http://localhost:8083/connectors"

# Create Kafka topic
docker compose exec kafka kafka-topics --create --topic outbox.event.AuditLog --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

### Test Endpoints

```bash
# Create audit log
$json = '{"utilisateur_id": 123, "action": "USER_LOGIN", "entite_type": "USER", "entite_id": 456, "details": {"ip": "127.0.0.1"}}'
Invoke-WebRequest -Method Post -Uri "http://localhost:8000/journaux-audit/create/" -ContentType "application/json" -Body $json

# List audit logs
Invoke-WebRequest -Method Get -Uri "http://localhost:8000/journaux-audit/list/"

# Verify integrity
Invoke-WebRequest -Method Get -Uri "http://localhost:8000/journaux-audit/verifier-integrite/"
```

## To Do Later

Additional features to add later :
- **Add pgbouncer**
- **Create script to simplify image startup**
- **Materialize the read database for more optimisation**
