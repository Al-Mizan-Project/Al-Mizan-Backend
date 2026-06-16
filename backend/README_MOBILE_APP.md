# Mobile App Backend Runbook

Use this path when running the backend for the Android mobile app. It uses Docker so Python dependencies, Postgres, Redis, and MinIO are started consistently.

Current backend branch:

```bash
feature/mobile-backend-integration
```

## 1. Prepare the environment

From the backend repository root:

```powershell
cd "d:\AL MIZAN\almizan"
Copy-Item deploy\.env.example deploy\.env -Force
```

Keep these ports available unless you change them in `deploy/.env`:

- `8000`: direct Django backend
- `8080`: Nginx gateway
- `5433`: Postgres on the host
- `6379`: Redis on the host
- `9000` and `9001`: MinIO

## 2. Start the backend stack

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

Check the services:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8080/health
```

If `8000` works but `8080` does not, check the `nginx` logs. If both fail, check `backend`, `postgres`, and `redis` logs.

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs -f backend nginx postgres redis
```

## 3. Seed the mobile dataset

The mobile wrapper runs migrations and then calls the unified seed command for acteurs, contractant, appels, auth users, watched appels, soumissions, and notifications.

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend sh scripts/seed_mobile_app.sh
```

Default mobile seed behavior:

- Flushes seedable data.
- Creates mobile appels-offres cases for all supported status/procedure/validation combinations.
- Creates soumissions and recours-compatible soumission data.
- Creates notifications for the contractant user.
- Does not seed document files by default, so MinIO object upload issues do not block the mobile app.

To customize volumes:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend sh scripts/seed_mobile_app.sh --flush --soumissions-count 5 --notifications-count 8 --watched-count 3
```

To test PDF downloads, include document objects after MinIO is healthy. This creates real PDF bytes in MinIO, links them to appels-offres, and adds receipt download URLs to seeded soumissions:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend sh scripts/seed_mobile_app.sh --flush --with-documents
```

## 4. Mobile login credentials

Seeded users:

- Contractant/operator: `c@a.dz` / `test1234`
- Legacy contractant compatibility user: `contractant.demo@almizan.local` / `ContractantPass123!`
- Admin: `a@a.dz` / `admin1234`

Quick login check:

```powershell
$body = @{ email = "c@a.dz"; password = "test1234" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/auth/login" -ContentType "application/json" -Body $body
```

## 5. Android base URL

The app reads `ALMIZAN_API_BASE_URL`.

Recommended values:

- Android emulator direct backend: `http://10.0.2.2:8000/`
- Android emulator through gateway: `http://10.0.2.2:8080/`
- Physical device over USB reverse tunnel: `http://127.0.0.1:8000/`
- Physical device on same Wi-Fi: `http://<your-pc-ip>:8000/`

For USB reverse tunnel:

```powershell
adb reverse tcp:8000 tcp:8000
.\gradlew.bat assembleDebug -PALMIZAN_API_BASE_URL=http://127.0.0.1:8000/
```

For emulator direct backend:

```powershell
.\gradlew.bat assembleDebug -PALMIZAN_API_BASE_URL=http://10.0.2.2:8000/
```

Use one port consistently. The current mobile `gradle.properties` points at `http://10.0.2.2:8000/`.

## 6. Stop or reset

Stop containers but keep data:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

Full database reset:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend sh scripts/seed_mobile_app.sh --flush --with-documents
```

## Local Python fallback

Only use this if Docker is not available. Create a fresh environment and install all backend dependencies first:

```powershell
cd "d:\AL MIZAN\almizan\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_dev_data --flush
python manage.py runserver 0.0.0.0:8000
```

If local Python reports missing `django`, `celery`, or database drivers, the environment is incomplete. Use Docker or reinstall `backend/requirements.txt`.
