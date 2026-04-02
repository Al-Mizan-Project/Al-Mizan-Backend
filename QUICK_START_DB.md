# Quick Start: Database Container

## Start Database

```bash
cd infrastructure
docker compose up -d
```

Wait ~10 seconds, then verify:

```bash
docker compose ps
```

Expected: `almizan_shared_postgres` and `almizan_shared_redis` showing "Up (healthy)".

## Connect with PgAdmin Desktop

Open PgAdmin desktop app, then right-click "Servers" > "Register" > "Server".

**General tab:**
```
Name: Al-Mizan PostgreSQL
```

**Connection tab:**
```
Host: localhost
Port: 5433
Maintenance database: postgres
Username: almizan_admin
Password: almizan_admin_password
```

Check "Save password", then click Save.

**Browse databases:**
Servers > Al-Mizan PostgreSQL > Databases

You'll see 12 databases: auth_db, acteurs_db, appels_db, audit_db, contractant_db, contrats_db, documents_db, evaluations_db, ia_db, notifications_db, soumissions_db, recours_db.

## Stop Database

```bash
cd infrastructure
docker compose down
```

## Troubleshooting

**Port 5433 already in use:**
Check with `netstat -ano | findstr :5433`, then stop the conflicting service or change `POSTGRES_PORT` in `infrastructure/.env`.

**Connection refused:**
Verify containers are running with `docker compose ps`.

**Databases don't exist:**
Recreate with `docker compose down -v && docker compose up -d` (destroys data).
