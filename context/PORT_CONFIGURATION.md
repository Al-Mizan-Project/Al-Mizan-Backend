# Port Configuration

## Port Change: 5432 → 5433

**Date:** April 2, 2026  
**Reason:** Avoid conflicts with local PostgreSQL installations

## Current Ports

| Service | Port | Notes |
|---------|------|-------|
| PostgreSQL | 5433 | Changed from 5432 to avoid conflicts |
| Redis | 6379 | Default |

## Why Change?

PostgreSQL's default port is 5432. If you have PostgreSQL installed locally or another PostgreSQL container running, the infrastructure won't start due to port conflicts. Port 5433 is used as a common alternative.

## Connection Methods

**PgAdmin Desktop:**
```
Host: localhost
Port: 5433
Database: postgres
Username: almizan_admin
Password: almizan_admin_password
```

**Command line (psql):**
```bash
psql -h localhost -p 5433 -U almizan_admin -d postgres
```

**From service containers:**
```
Host: host.docker.internal
Port: 5433
```

**Inside Docker (docker exec):**
```bash
docker exec -it almizan_shared_postgres psql -U almizan_admin -d postgres
```

## Change Port

To use a different port, edit `infrastructure/.env`:

```bash
POSTGRES_PORT=5434  # or any available port
```

Update all service `.env` files to match, then restart:

```bash
cd infrastructure
docker compose down
docker compose up -d
```

## Troubleshooting

**Port already in use:**
```powershell
netstat -ano | findstr :5433
```
Stop the conflicting service or change the port.

**Connection refused:**
Verify infrastructure is running with `docker compose ps`.
Login:    admin@almizan.dz / admin

Server Connection:
  Host:     shared_postgres
  Port:     5432  ← Inside Docker, still uses 5432
  User:     almizan_admin
  Password: almizan_admin_password
```

### From Application Code (Outside Docker)
```python
# Python
DATABASE_URL = "postgresql://auth_user:auth_password@localhost:5433/auth_db"
                                                            # ^^^^^ Use 5433
```

```javascript
// Node.js
const client = new Client({
  host: 'localhost',
  port: 5433,  // Use 5433
  database: 'auth_db',
  user: 'auth_user',
  password: 'auth_password',
});
```

### From Service Containers (Inside Docker)
```bash
# In .env files, services already use:
DB_HOST=host.docker.internal
DB_PORT=5433  ← Changed to 5433
```

---

## 🛠️ What If You Want a Different Port?

Just change `POSTGRES_PORT` in `infrastructure/.env`:

```bash
# infrastructure/.env
POSTGRES_PORT=5434  # or any available port
```

Then update all service `.env` files:
```bash
# services/auth/.env (and all others)
DB_PORT=5434  # match the infrastructure port
```

Finally, restart infrastructure:
```bash
cd infrastructure
docker compose down
docker compose up -d
```

---

## 🚨 Troubleshooting

### "Port 5433 is already in use"
**Check what's using it:**
```powershell
# Windows
netstat -ano | findstr :5433

# Get process details
Get-Process -Id <PID>
```

**Solution:** Either:
1. Stop the conflicting service
2. Change `POSTGRES_PORT` to another port (e.g., 5434)

### "Connection refused on port 5433"
**Check if infrastructure is running:**
```bash
cd infrastructure
docker compose ps
```

**If not running:**
```bash
docker compose up -d
```

### "Still connecting to old port 5432"
**Your `.env` file wasn't updated. Fix it:**
```bash
# For a specific service
cd services/auth
nano .env  # Change DB_PORT=5432 to DB_PORT=5433

# Then restart the service
docker compose down
docker compose up -d
```

---

## 📊 Quick Reference

```
┌─────────────────────────────────────────────────────────┐
│  Al-Mizan PostgreSQL Connection Info                    │
├─────────────────────────────────────────────────────────┤
│  External Port:   5433  ← From your PC                  │
│  Internal Port:   5432  ← Inside Docker                 │
│                                                         │
│  Connect from PC:                                       │
│    localhost:5433                                       │
│                                                         │
│  Connect from Service Container:                        │
│    host.docker.internal:5433                            │
│                                                         │
│  Connect from PgAdmin:                                  │
│    shared_postgres:5432                                 │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ Verification

Infrastructure is now running on **port 5433**:

```
$ docker compose ps
NAME                      PORTS
almizan_shared_postgres   0.0.0.0:5433->5432/tcp  ✅
almizan_shared_redis      0.0.0.0:6379->6379/tcp
almizan_pgadmin           0.0.0.0:5050->80/tcp
```

All databases are accessible:
```
$ docker exec -it almizan_shared_postgres psql -U almizan_admin -d postgres -c "\l"
✅ 12 service databases + postgres
```

---

## 👥 For Your Coworkers

When they clone the repo and run:
```bash
cd infrastructure
cp .env.example .env  # Already has POSTGRES_PORT=5433
docker compose up -d
```

Everything will work without conflicts! 🎉

---

**Questions?** Check:
- `infrastructure/CONNECT_TO_DB.md` - Connection guide
- `infrastructure/README.md` - Setup instructions
- `context/MIGRATION_SUMMARY.md` - Complete migration details
