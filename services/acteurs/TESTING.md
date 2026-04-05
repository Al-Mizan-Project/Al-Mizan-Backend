# Acteurs Service - Testing Guide

## Prerequisites
1. Docker Desktop running
2. Shared infrastructure started:
   ```bash
   cd ../../infrastructure
   docker compose up -d
   ```

## Quick Start

### 1. Setup Environment
```bash
# Copy example environment file
cp .env.example .env
```

### 2. Start Service
```bash
# Build and start
docker compose up --build

# Or in background
docker compose up --build -d
```

### 3. Verify Service is Running
```bash
# Check health
curl http://localhost:18081/health

# Expected: {"status": "ok"}
```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check (DB + Redis) |
| `/openapi.json` | GET | OpenAPI specification |
| `/organisations` | GET | List organizations |
| `/organisations` | POST | Create organization |
| `/operateurs-economiques` | GET | List economic operators |
| `/membres` | GET | List members |
| `/tutelles` | GET | List supervision authorities |

Full endpoint documentation: See `ENDPOINTS.md`

## Test Examples

### Health Check
```bash
curl http://localhost:18081/health
```

### List Organizations
```bash
curl http://localhost:18081/organisations
```

### Check Database Tables
```bash
docker exec -it almizan_shared_postgres psql -U acteurs_user -d acteurs_db

# List tables
\dt

# Exit
\q
```

## Troubleshooting

### Port 18081 already in use
```bash
# Change ACTEURS_NGINX_PORT in .env
ACTEURS_NGINX_PORT=18091
```

### Cannot connect to database
Verify infrastructure is running:
```bash
docker ps | grep almizan_shared_postgres
```

## Stopping the Service

```bash
docker compose down
```
