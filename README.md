# Al-Mizan Backend

Each service owns its runtime, database, Redis, and PgBouncer, and can be deployed on the same machine or on separate hosts.

## Services

- `services/auth`: authentication, users, roles, permissions, JWT flows.
- `services/acteurs`: membres domain service.
- `gateway`: optional edge reverse proxy routing `/auth/` and `/acteurs/`...

## Architecture

Each service runs as an isolated stack:

- Django API (ASGI: Gunicorn + Uvicorn worker)
- PostgreSQL
- PgBouncer (connection pooling)
- Redis (cache + rate counters)
- NGINX (service-local ingress)

Gateway is a separate stack and is optional. Services can be called directly without gateway.

## Deployment Models

### 1) Independent service deployment

Run each service from its own directory:

```bash
cd services/auth && docker compose up --build
cd services/acteurs && docker compose up --build
```

Each service is self-contained and can run without the other.

### 2) With gateway

```bash
cd gateway && docker compose up --build
```

Gateway forwards:

- `/auth/*` -> auth upstream
- `/acteurs/*` -> acteurs upstream

### 3) Distributed SOA (multi-host)

Set `.env` values per environment:

- `gateway/.env`
  - `AUTH_UPSTREAM=auth.company.internal:80`
  - `ACTEURS_UPSTREAM=acteurs.company.internal:80`
- `services/auth/.env`
  - `MEMBRES_SERVICE_URL=http://acteurs.company.internal`

No code changes are required to move between environments.

## Environment and Operations

Primary env files:

- `services/auth/.env`
- `services/acteurs/.env`
- `gateway/.env`

Key controls:

- Runtime: `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT`
- Security: `DJANGO_ENV`, `DEBUG`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
- Database: `DATABASE_URL` or `DB_*`, `CONN_MAX_AGE`
- Cache and throttling: `REDIS_URL`, `CACHE_TTL`, `THROTTLE_*`
- Gateway routing/tuning: `AUTH_UPSTREAM`, `ACTEURS_UPSTREAM`, timeout and keepalive variables

## Health and API Discovery

Each service exposes:

- `GET /health`
- `GET /ready` (checks DB + Redis)
- `GET /openapi.json`

Detailed endpoint usage is documented in:

- `services/auth/ENDPOINTS.md`
- `services/acteurs/ENDPOINTS.md`

