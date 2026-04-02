# Soumissions Service - Testing Guide

## Prerequisites
1. Docker Desktop running
2. Shared infrastructure started (includes MinIO):
   ```ash
   cd ../../infrastructure
   docker compose up -d
   ```

## Quick Start

### 1. Setup Environment
```ash
# Copy example environment file
cp .env.example .env

# Optional: Edit .env if you need custom values
# The defaults work out of the box with shared infrastructure
```

### 2. Start Service
```ash
# Build and start
docker compose up --build

# Or in background
docker compose up --build -d
```

### 3. Verify Service is Running
```ash
# Check health
curl http://localhost:8004/health

# Expected: {"status": "ok"}
```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check (always returns ok) |
| /ready | GET | Readiness check (verifies DB + Redis + MinIO) |
| /openapi.json | GET | OpenAPI specification |

Full endpoint documentation: See ENDPOINTS.md if available

## Test Examples

### Health Check
```ash
curl http://localhost:8004/health
```

### View OpenAPI Spec
```ash
curl http://localhost:8004/openapi.json | jq
```

### Check Database Tables
```ash
# Connect to shared PostgreSQL
docker exec -it almizan_shared_postgres psql -U soumissions_user -d soumissions_db

# List tables
\dt

# Exit
\q
```
"@
    
    if (True) {
         += @"

### Access MinIO Console
```ash
# MinIO Admin Console: http://localhost:9001
# Default credentials:
# Access Key: minioadmin
# Secret Key: minioadmin
```
"@
    }
    
     += @"

## Troubleshooting

### Port 8004 already in use
```ash
# Change SOUMISSIONS_NGINX_PORT in .env
SOUMISSIONS_NGINX_PORT=18090
```

### Cannot connect to database
1. Verify infrastructure is running:
   ```ash
   docker ps | grep almizan_shared_postgres
   ```
2. Check database credentials in .env match infrastructure/.env
### Cannot connect to MinIO
1. Verify MinIO is running:
   ```ash
   docker ps | grep minio
   ```
2. Check MinIO credentials in .env match infrastructure/.env
3. Verify bucket exists in MinIO console: http://localhost:9001
### Service crashes on startup
```ash
# View logs
docker compose logs -f soumissions_api

# Common issues:
# - entrypoint.sh has wrong line endings (should be LF, not CRLF)
# - Missing .env file
# - MinIO not accessible
```

## Stopping the Service

```ash
# Stop containers
docker compose down

# Stop and remove volumes (⚠️ deletes data)
docker compose down -v
```

## Next Steps

After verifying the service works:
1. Try other services in the Al-Mizan ecosystem
2. Test cross-service communication if needed
3. Use the gateway for unified API access