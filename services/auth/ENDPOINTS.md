# Auth Service Endpoints

## Health

- `GET /health`
- `GET /ready`
- `GET /openapi.json`

## Authentication

- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/change-password`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`

## Users

- `GET /users`
- `POST /users`
- `GET /users/{user_id}`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`
- `PATCH /users/{user_id}/role`
- `GET /users/{user_id}/permissions`

## Roles

- `GET /roles`
- `POST /roles`
- `GET /roles/{role_id}`
- `PATCH /roles/{role_id}`
- `DELETE /roles/{role_id}`
- `GET /roles/{role_id}/permissions`
- `PUT /roles/{role_id}/permissions`
- `POST /roles/{role_id}/permissions/{permission_id}`
- `DELETE /roles/{role_id}/permissions/{permission_id}`

## Permissions

- `GET /permissions`
- `POST /permissions`
- `GET /permissions/{permission_id}`
- `PATCH /permissions/{permission_id}`
- `DELETE /permissions/{permission_id}`
