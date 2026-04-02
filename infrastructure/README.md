# Al-Mizan Shared Infrastructure

Centralized PostgreSQL and Redis for all Al-Mizan microservices.

## Quick Start

```bash
# Start shared infrastructure (run this FIRST before any service)
docker compose up -d

# Verify services are healthy
docker compose ps
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `shared_postgres` | 5433 | PostgreSQL 16 with all service databases |
| `shared_redis` | 6379 | Redis 7.4 for caching and rate limiting |
| `pgadmin` | 5050 | PgAdmin web UI (optional) |

## Databases

The PostgreSQL container automatically creates these databases on first startup:

| Database | User | Service |
|----------|------|---------|
| auth_db | auth_user | Authentication & RBAC |
| acteurs_db | acteurs_user | Organizations & Members |
| appels_db | appels_user | Tender Calls |
| audit_db | audit_user | Audit Logs |
| contractant_db | contractant_user | Contracting Services |
| contrats_db | contrats_user | Contracts |
| documents_db | documents_user | Document Management |
| evaluations_db | evaluations_user | Bid Evaluations |
| ia_db | ia_user | AI/ML Services |
| notifications_db | notifications_user | Notifications |
| soumissions_db | soumissions_user | Submissions |
| recours_db | recours_user | Appeals (future) |

## Connecting Services

Each service should use these environment variables:

```env
# Database
DB_HOST=host.docker.internal  # or 'shared_postgres' if on same network
DB_PORT=5433
DB_NAME=<service>_db
DB_USER=<service>_user
DB_PASSWORD=<service>_password

# Redis
REDIS_URL=redis://:almizan_redis_password@host.docker.internal:6379/0
```

Or if services join the `almizan-infra` network:

```env
DB_HOST=shared_postgres
REDIS_URL=redis://:almizan_redis_password@shared_redis:6379/0
```

## PgAdmin Access

1. Open http://localhost:5050
2. Login: `admin@almizan.dz` / `admin`
3. Add server:
   - Host: `shared_postgres`
   - Port: `5433`
   - Username: `almizan_admin`
   - Password: `almizan_admin_password`

## Data Persistence

Data is stored in Docker volumes:
- `shared-postgres-data` - PostgreSQL data
- `shared-redis-data` - Redis AOF persistence

## Network

Services can connect to infrastructure via:
1. **Host networking**: `host.docker.internal:5433` (default for isolated services)
2. **Shared network**: Join `almizan-infra` network and use service names

To join the network from another compose file:
```yaml
networks:
  almizan-infra:
    external: true
```
