# Al-Mizan Backend

Microservices architecture with **shared infrastructure** (single PostgreSQL instance with multiple databases + single Redis instance).

## Quick Start

```bash
# 1. Start shared infrastructure FIRST
cd infrastructure && docker compose up -d

# 2. Then start any service
cd services/auth && docker compose up --build
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Shared Infrastructure                        │
│  ┌──────────────────────┐    ┌──────────────────────┐          │
│  │   PostgreSQL 16      │    │      Redis 7.4       │          │
│  │  (12 databases)      │    │    (shared cache)    │          │
│  │  - auth_db           │    │                      │          │
│  │  - acteurs_db        │    └──────────────────────┘          │
│  │  - appels_db         │                                      │
│  │  - contrats_db ...   │    ┌──────────────────────┐          │
│  └──────────────────────┘    │     PgAdmin 4        │          │
│                              │   (optional UI)      │          │
│                              └──────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Auth Service │   │Acteurs Service│   │ ... Services  │
│  Django API   │   │  Django API   │   │  Django API   │
│  + NGINX      │   │  + NGINX      │   │  + NGINX      │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `auth` | 18080 | Authentication, users, roles, permissions, JWT |
| `acteurs` | 18081 | Organizations & members |
| `contractant` | 18082 | Contracting services & commissions |
| `appels` | 18083 | Tender calls (appels d'offres) |
| `documents` | 8003 | Document management (GED) + MinIO |
| `soumissions` | 8004 | Bid submissions |
| `contrats` | 18085 | Contracts |
| `evaluations` | 18086 | Bid evaluations |
| `notifications` | 18087 | User notifications |
| `ia` | 18088 | AI/ML anomaly detection |
| `audit` | 8000 | Audit logs (Kafka + Debezium CDC) |

## Shared Infrastructure

All services connect to centralized infrastructure:

- **PostgreSQL** (port 5433): 12 logical databases, one per service
- **Redis** (port 6379): Shared cache and rate limiting
- **PgAdmin** (port 5050): Web UI for database management

```bash
# Start infrastructure
cd infrastructure && docker compose up -d

# Check status
docker compose ps
```

## Deployment Models

### 1) Local Development (default)

```bash
# Start infrastructure
cd infrastructure && docker compose up -d

# Start services individually
cd services/auth && docker compose up --build
cd services/acteurs && docker compose up --build
```

### 2) With Gateway

```bash
# Start infrastructure + services, then gateway
cd gateway && docker compose up --build
```

Gateway routes:
- `/auth/*` → auth service
- `/acteurs/*` → acteurs service
- `/ia/*` → ia service

### 3) Distributed (multi-host)

Set environment variables per host:
- `DB_HOST=postgres.internal.company`
- `REDIS_URL=redis://:password@redis.internal.company:6379/0`

## Environment Variables

Primary env files:
- `infrastructure/.env` - shared database/redis credentials
- `services/<service>/.env` - service-specific config

Key variables:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_URL`
- `DJANGO_ENV`, `DEBUG`, `SECRET_KEY`

## Health Endpoints

Each service exposes:
- `GET /health` - liveness check
- `GET /ready` - readiness (DB + Redis)
- `GET /openapi.json` - API schema

## Documentation

- `infrastructure/README.md` - Infrastructure setup
- `context/database.md` - Database schema reference
- Service-specific: `services/<service>/ENDPOINTS.md`

