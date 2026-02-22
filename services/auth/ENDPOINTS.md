# Auth Service Curl Guide

Base URL: `http://localhost:18080`

## Setup Variables
```bash
BASE_AUTH="http://localhost:18080"
BASE_ACTEURS="http://localhost:18081"
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="b881872f08299b4764bc6ba78ad1426664978d5c459a0de4"
```

## Common Endpoints
```bash
curl -sS "$BASE_AUTH/health"
curl -sS "$BASE_AUTH/ready"
curl -sS "$BASE_AUTH/openapi.json"
```

## Auth Endpoints
```bash
curl -sS -X POST "$BASE_AUTH/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
```

```bash
REFRESH_TOKEN="<paste refresh token from login>"
curl -sS -X POST "$BASE_AUTH/auth/refresh" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh\":\"$REFRESH_TOKEN\"}"
```

```bash
ACCESS_TOKEN="<paste access token from login>"
REFRESH_TOKEN="<paste refresh token from login>"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE_AUTH/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh\":\"$REFRESH_TOKEN\"}"
```

```bash
ACCESS_TOKEN="<access token>"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE_AUTH/auth/change-password" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"old_password":"old-pass","new_password":"new-pass-123456"}'
```

```bash
curl -sS -X POST "$BASE_AUTH/auth/forgot-password" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\"}"
```

```bash
curl -sS -X POST "$BASE_AUTH/auth/reset-password" \
  -H 'Content-Type: application/json' \
  -d '{"token":"invalid-token","new_password":"new-pass-123456"}'
```

## Users / Roles / Permissions Endpoints
```bash
ACCESS_TOKEN="<access token>"
MEMBRE_ID=1

curl -sS "$BASE_AUTH/users" -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X POST "$BASE_AUTH/users" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"id_role\":1,\"id_membre\":$MEMBRE_ID,\"email\":\"user1@example.com\",\"password\":\"UserPass1234!abcd\"}"

curl -sS "$BASE_AUTH/users/1" -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X PATCH "$BASE_AUTH/users/1" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"user1-updated@example.com\",\"id_membre\":$MEMBRE_ID}"

curl -sS -o /dev/null -w '%{http_code}\n' -X DELETE "$BASE_AUTH/users/9999" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X PATCH "$BASE_AUTH/users/1/role" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"id_role":1}'

curl -sS "$BASE_AUTH/users/1/permissions" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS "$BASE_AUTH/roles" -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X POST "$BASE_AUTH/roles" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom_role":"manager"}'

curl -sS "$BASE_AUTH/roles/1" -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X PATCH "$BASE_AUTH/roles/1" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom_role":"admin"}'

curl -sS -o /dev/null -w '%{http_code}\n' -X DELETE "$BASE_AUTH/roles/9999" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS "$BASE_AUTH/permissions" -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X POST "$BASE_AUTH/permissions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom_permission":"manage_users"}'

curl -sS "$BASE_AUTH/permissions/1" -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X PATCH "$BASE_AUTH/permissions/1" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom_permission":"manage_users"}'

curl -sS -o /dev/null -w '%{http_code}\n' -X DELETE "$BASE_AUTH/permissions/9999" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS "$BASE_AUTH/roles/1/permissions" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -X PUT "$BASE_AUTH/roles/1/permissions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"permission_ids":[1]}'

curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE_AUTH/roles/1/permissions/1" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -sS -o /dev/null -w '%{http_code}\n' -X DELETE "$BASE_AUTH/roles/1/permissions/1" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```
