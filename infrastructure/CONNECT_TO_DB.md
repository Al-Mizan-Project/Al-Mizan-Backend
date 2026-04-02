# Database Connection Guide

## Credentials

**Admin Account (all databases):**
```
Host:     localhost
Port:     5433
Database: postgres
Username: almizan_admin
Password: almizan_admin_password
```

**Service-specific accounts:**
```
auth_db          → auth_user / auth_password
acteurs_db       → acteurs_user / acteurs_password
appels_db        → appels_user / appels_password
contractant_db   → contractant_user / contractant_password
contrats_db      → contrats_user / contrats_password
documents_db     → documents_user / documents_password
evaluations_db   → evaluations_user / evaluations_password
ia_db            → ia_user / ia_password
notifications_db → notifications_user / notifications_password
soumissions_db   → soumissions_user / soumissions_password
audit_db         → audit_user / audit_password
recours_db       → recours_user / recours_password
```

## Method 1: PgAdmin Desktop

Right-click "Servers" > "Register" > "Server"

**General tab:**
- Name: Al-Mizan PostgreSQL

**Connection tab:**
- Host: localhost
- Port: 5433
- Maintenance database: postgres
- Username: almizan_admin
- Password: almizan_admin_password
- Save password: checked

Browse: Servers > Al-Mizan PostgreSQL > Databases

## Method 2: Command Line (psql)

```bash
docker exec -it almizan_shared_postgres psql -U almizan_admin -d postgres
```

**Common commands:**
```sql
\l                  -- List databases
\c auth_db          -- Connect to database
\dt                 -- List tables
\du                 -- List users
\q                  -- Exit
```

## Method 3: From Application Code

**From your PC:**
```
Host: localhost
Port: 5433
```

**From service containers:**
```
Host: host.docker.internal
Port: 5433
```

## Troubleshooting

**Connection refused:** Check containers are running with `docker compose ps`

**Port already in use:** Check with `netstat -ano | findstr :5433`, stop conflicting service or change port in `infrastructure/.env`

**Database doesn't exist:** Recreate with `docker compose down -v && docker compose up -d`

3. Click **Save**

### Step 3: Browse Databases
- Expand: **Servers** → **Al-Mizan Shared PostgreSQL** → **Databases**
- You'll see all 12 service databases!

---

## 💻 Method 3: psql from Your PC (If PostgreSQL Installed Locally)

### Install psql (Windows)
```powershell
# Using Chocolatey
choco install postgresql16

# Or download from:
# https://www.postgresql.org/download/windows/
```

### Connect
```bash
psql -h localhost -p 5433 -U almizan_admin -d postgres
```

**Password:** `almizan_admin_password`

---

## 🛠️ Method 4: DBeaver / DataGrip / Other Tools

### Connection Settings
```
Type:     PostgreSQL
Host:     localhost
Port:     5433
Database: postgres (or any service database)
User:     almizan_admin
Password: almizan_admin_password
```

### Test Connection
Most tools have a "Test Connection" button - click it to verify!

---

## 🔍 Useful Commands to Explore

### 1. List All Databases
```sql
SELECT datname FROM pg_database WHERE datistemplate = false;
```

Expected output:
```
     datname
------------------
 postgres
 auth_db
 acteurs_db
 appels_db
 contractant_db
 contrats_db
 documents_db
 evaluations_db
 ia_db
 notifications_db
 soumissions_db
 audit_db
 recours_db
```

### 2. Check Database Sizes
```sql
SELECT 
    datname AS "Database",
    pg_size_pretty(pg_database_size(datname)) AS "Size"
FROM pg_database
WHERE datistemplate = false
ORDER BY pg_database_size(datname) DESC;
```

### 3. List All Users
```sql
SELECT usename FROM pg_user;
```

Expected output:
```
       usename
---------------------
 almizan_admin
 auth_user
 acteurs_user
 appels_user
 ...
```

### 4. Check Active Connections
```sql
SELECT 
    datname AS database,
    usename AS user,
    client_addr AS client,
    state
FROM pg_stat_activity
WHERE datname IS NOT NULL;
```

### 5. See All Tables in a Database
```sql
-- First connect to the database
\c auth_db

-- Then list tables
\dt

-- Or with SQL
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

---

## 🐛 Troubleshooting

### "Connection refused" or "Could not connect"
**Problem:** Container isn't running

**Solution:**
```bash
cd infrastructure
docker compose ps
# If not running:
docker compose up -d
```

### "Database does not exist"
**Problem:** Init script didn't run

**Solution:**
```bash
cd infrastructure
docker compose down -v  # ⚠️ Destroys data!
docker compose up -d    # Recreates from scratch
```

### "Password authentication failed"
**Problem:** Wrong credentials

**Solution:** Check `infrastructure/.env` file for actual passwords

### PgAdmin shows "server closed the connection"
**Problem:** Using `localhost` instead of `shared_postgres`

**Solution:** Use `shared_postgres` as host in PgAdmin (container name, not localhost)

---

## 📊 Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│  Al-Mizan Shared PostgreSQL Quick Reference             │
├─────────────────────────────────────────────────────────┤
│  Container:   almizan_shared_postgres                   │
│  Host:        localhost (from PC)                       │
│               host.docker.internal (from containers)    │
│               shared_postgres (from PgAdmin)            │
│  Port:        5433                                      │
│  Admin User:  almizan_admin                             │
│  Admin Pass:  almizan_admin_password                    │
│                                                         │
│  Quick Shell Access:                                    │
│  docker exec -it almizan_shared_postgres \              │
│    psql -U almizan_admin -d postgres                    │
│                                                         │
│  PgAdmin:     http://localhost:5050                     │
│               admin@almizan.dz / admin                  │
└─────────────────────────────────────────────────────────┘
```

---

## 🎓 For Developers

### Connect from a Service Container
Services use `host.docker.internal:5433`:

```python
# Python (SQLAlchemy)
DATABASE_URL = "postgresql://auth_user:auth_password@host.docker.internal:5433/auth_db"
```

```javascript
// Node.js (pg)
const client = new Client({
  host: 'host.docker.internal',
  port: 5432,
  database: 'auth_db',
  user: 'auth_user',
  password: 'auth_password',
});
```

### Connect from Your PC
Your PC uses `localhost:5433`:

```bash
psql -h localhost -p 5433 -U almizan_admin -d auth_db
```

---

## 🔐 Security Notes

**⚠️ IMPORTANT:** These are **development credentials**!

For production:
1. Change all passwords in `infrastructure/.env`
2. Use environment variables, NOT hardcoded values
3. Restrict network access (don't expose port 5433 publicly)
4. Use SSL connections
5. Enable database audit logging

---

## 📚 Additional Resources

- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **psql Commands**: https://www.postgresql.org/docs/current/app-psql.html
- **PgAdmin Docs**: https://www.pgadmin.org/docs/

---

**Happy Querying!** 🐘
