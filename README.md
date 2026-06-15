# Al-Mizan Backend

Django backend for Al-Mizan.

Runtime flow:

`Client -> Nginx -> Django -> logical service -> Postgres/Redis`

Optional background work:

`Django -> Celery -> Redis -> worker`

## Structure

```text
.
├── backend/                      # Django backend
├── deploy/                       # Main Docker Compose stack + env files
├── gateway/                      # Nginx gateway config
├── al-mizan-backend-documentation.md
└── README.md
```

## Run

1. Create `deploy/.env` from `deploy/.env.example`.

2. Start the backend stack:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

3. Open the app:

- API base: `http://127.0.0.1:8080`
- Swagger UI: `http://127.0.0.1:8080/docs/swagger/`
- ReDoc: `http://127.0.0.1:8080/docs/redoc/`
- OpenAPI schema: `http://127.0.0.1:8080/openapi.json`

For Android/mobile setup, use the dedicated runbook:

```text
backend/README_MOBILE_APP.md
```

## Useful Commands

Start or rebuild:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

Recreate backend and nginx:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --force-recreate backend nginx
```

View logs:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs -f backend nginx
```

Stop the stack:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

## Initial Admin

The first admin account is bootstrapped from `deploy/.env` on backend startup.

Required variables:

```env
INITIAL_ADMIN_ENABLED=true
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=StrongPassword123!
INITIAL_ADMIN_ROLE=admin
INITIAL_ADMIN_MEMBRE_ID=1
```

If you change those values, recreate the backend:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --force-recreate backend nginx
```

## Dev Seed Data

You can now seed a coherent test dataset (acteurs, auth users, roles/permissions, contractant, appels, watched appels, soumissions, notifications)
with one command.

Local run:

```bash
cd backend
sh scripts/seed_dev_data.sh --flush
```

Mobile-focused seed wrapper:

```bash
cd backend
sh scripts/seed_mobile_app.sh
```

Docker run:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend sh -c "cd /app && sh scripts/seed_dev_data.sh --flush"
```

Mobile-focused Docker run:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend sh scripts/seed_mobile_app.sh
```

Optional flags:

- `--with-documents` to also run `seed_documents` (requires MinIO ready)
- `--soumissions-count 8` to customize soumissions volume
- `--notifications-count 10` to customize notifications volume
- `--watched-count 4` to customize watched appels seeded for the contractant user
- `--legacy-contractant-email ""` to disable legacy contractant compatibility user

Default test credentials created by the seed flow:

- Admin: `a@a.dz` / `admin1234`
- Contractant (primary): `c@a.dz` / `test1234`
- Contractant (legacy compatibility): `contractant.demo@almizan.local` / `ContractantPass123!`

## Current Stack

- `backend`: Django + Gunicorn/Uvicorn
- `nginx`: public entrypoint
- `postgres`: main database
- `redis`: cache, throttling, broker
- `minio`: object storage
- `celery`: optional worker profile
