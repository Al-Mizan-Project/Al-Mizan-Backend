# Auth Service - Testing Guide

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

# Optional: Edit .env if you need custom values
# The defaults work out of the box with shared infrastructure
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
curl http://localhost:18080/health

# Expected: {"status": "ok"}
```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (always returns ok) |
| `/ready` | GET | Readiness check (verifies DB + Redis) |
| `/openapi.json` | GET | OpenAPI specification |
| `/auth/login` | POST | User login |
| `/auth/refresh` | POST | Refresh JWT token |
| `/users` | GET | List users (requires auth) |
| `/roles` | GET | List roles (requires auth) |

Full endpoint documentation: See `ENDPOINTS.md`

## Test Examples

### Health Check
```bash
curl http://localhost:18080/health
```

### View OpenAPI Spec
```bash
curl http://localhost:18080/openapi.json | jq
```

### Check Database Tables
```bash
# Connect to shared PostgreSQL
docker exec -it almizan_shared_postgres psql -U auth_user -d auth_db

# List tables
\dt

# Exit
\q
```

## Troubleshooting

### Port 18080 already in use
```bash
# Change AUTH_NGINX_PORT in .env
AUTH_NGINX_PORT=18090
```

### Cannot connect to database
1. Verify infrastructure is running:
   ```bash
   docker ps | grep almizan_shared_postgres
   ```
2. Check database credentials in `.env` match `infrastructure/.env`

### Service crashes on startup
```bash
# View logs
docker compose logs -f auth_api

# Common issues:
# - entrypoint.sh has wrong line endings (should be LF, not CRLF)
# - Missing .env file
```

## Stopping the Service

```bash
# Stop containers
docker compose down

# Stop and remove volumes (⚠️ deletes data)
docker compose down -v
```

## Next Steps

After verifying the service works:
1. Try the acteurs service (handles organizations)
2. Test cross-service communication if needed
3. Use the gateway for unified API access
