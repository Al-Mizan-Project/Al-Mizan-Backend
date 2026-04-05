# Acteurs Service Endpoints

## Health

- `GET /health`
- `GET /ready`
- `GET /openapi.json`

## Organisations

- `GET /organisations`
- `POST /organisations`
- `GET /organisations/{organisation_id}`
- `PATCH /organisations/{organisation_id}`
- `DELETE /organisations/{organisation_id}`
- `GET /organisations/{organisation_id}/membres`
- `GET /services-contractants`
- `POST /services-contractants`
- `GET /services-contractants/{service_id}`
- `PATCH /services-contractants/{service_id}`
- `DELETE /services-contractants/{service_id}`
- `GET /services-contractants/{service_id}/membres`

## Operateurs Economiques

- `GET /operateurs-economiques`
- `POST /operateurs-economiques`
- `GET /operateurs-economiques/{operateur_id}`
- `PATCH /operateurs-economiques/{operateur_id}`
- `DELETE /operateurs-economiques/{operateur_id}`
- `GET /operateurs-economiques/by-nif/{nif}`

## Membres

- `GET /membres`
- `POST /membres`
- `GET /membres/{membre_id}`
- `PATCH /membres/{membre_id}`
- `DELETE /membres/{membre_id}`

## Tutelles

- `GET /tutelles`
- `POST /tutelles`
- `GET /tutelles/{tutelle_id}`
- `PATCH /tutelles/{tutelle_id}`
- `DELETE /tutelles/{tutelle_id}`
