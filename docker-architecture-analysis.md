## Section 1: Problems In Current Docker Setup

Voici les problèmes principaux identifiés après scan des compose:

1. Duplication massive de stack par service

- Pattern répété partout: API + Postgres + PgBouncer + Redis + parfois Nginx + parfois PgAdmin.
- Exemples: `services/auth/docker-compose.yml`, `services/acteurs/docker-compose.yml`, `services/contrats/docker-compose.yml`, `services/notifications/docker-compose.yml`.

2. Double reverse-proxy inutile

- Vous avez un gateway global Nginx: `gateway/docker-compose.yml`.
- Et en plus des Nginx par service (auth, acteurs, ia, contrats, etc.).
- Cela augmente le nombre de conteneurs, la latence, et la complexité de routing sans vrai gain.

3. PgBouncer partout = overkill au stade actuel

- PgBouncer est utile à grande échelle ou avec gros pool de connexions.
- Ici il est dupliqué par microservice, alors que plusieurs services tournent en runserver Django en dev.
- Coût opérationnel supérieur au bénéfice dans votre phase actuelle.

4. Incohérence d’architecture entre compose central et compose locaux

- Compose central partage un Postgres et un Redis: `docker-compose.dev.yml`.
- Compose de services individuels recrée chacun leur DB/Redis/PgBouncer.
- Cela crée des comportements différents entre environnements et complique debug/intégration.

5. Outils dev mélangés avec runtime prod

- PgAdmin embarqué dans plusieurs services (appels, documents, ia, soumissions).
- Ce n’est pas une dépendance runtime métier, cela doit être profil dev uniquement.

6. Couplage fort synchrone inter-services

- IA dépend de Appels + Documents + Soumissions en synchrone: `docker-compose.dev.yml`.
- Le coût de communication et le risque de cascade de panne augmentent.

7. Audit stack très lourde pour usage courant

- Kafka + Zookeeper + Debezium + consumer + DB custom logical: `services/audit/audit_service/docker-compose.yml`.
- Architecture puissante, mais probablement trop coûteuse en exploitation pour votre phase produit actuelle si le volume n’est pas énorme.

8. Images non pinées et parfois latest

- MinIO et PgBouncer en latest sur plusieurs compose.
- Risque de drift et de régressions imprévisibles.

9. Exposition excessive de ports internes

- Plusieurs DB et outils admin exposés localement (5433/5434/5435/5050/5051/5052/5053).
- Pratique utile pour debug local, mais doit être strictement profilée dev.

10. Recours absent du setup infra

- Pas de compose dédié trouvé pour recours dans services.
- Cela confirme le besoin de consolidation dans Procurement Core.

---

## Section 2: Proposed Architecture Diagram (Text-Based)

Proposition simple, propre, orientée production pragmatique:

Client
-> API Gateway
-> IAM API
-> Procurement Core API
-> Documents API
-> AI API
-> Audit API
-> Notification API

Data plane:

- Postgres cluster unique en infra partagée, avec 6 bases logiques:
  - iam_db
  - procurement_db
  - documents_db
  - ai_db
  - audit_db
  - notifications_db
- Redis unique partagé (DB/logical namespace par service), sauf besoin strict contraire.
- MinIO dédié au service Documents.
- RabbitMQ unique pour événements async inter-services.

Event flow recommandé:

- Procurement publie événements métier.
- Notification consomme ces événements.
- Audit consomme événements métier et écrit dans ledger.
- IA consomme événements document/soumission et produit résultats async.

---

## Section 3: Docker Images Per Service (Table)

| Service          | Images nécessaires                                                                                          | Pourquoi                                          | DB recommandée                                    |
| ---------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- |
| IAM              | API (build interne basé sur python:3.12-slim), postgres:16-alpine, redis:7-alpine optionnel                 | Auth, sessions/cache, RBAC                        | Isolée logiquement (iam_db)                       |
| Procurement Core | API (python:3.12-slim), postgres:16-alpine, redis:7-alpine optionnel, worker API optionnel                  | Domaine métier principal, transactions, workflows | Isolée logiquement (procurement_db)               |
| Documents        | API (python:3.12-slim), postgres:16-alpine, minio/minio version pinée, minio/mc init bucket en profil dev   | Métadonnées + stockage objet                      | Isolée logiquement (documents_db)                 |
| AI               | API (python:3.12-slim), worker (même image), postgres:16-alpine optionnel, redis:7-alpine, RabbitMQ partagé | Traitements OCR/NLP async, files de jobs          | Isolée logiquement (ai_db) ou sans DB si possible |
| Audit            | API (python:3.12-slim), postgres:16-alpine, redis optionnel pour cache lecture                              | Ledger immuable, conformité, query audit          | Isolée strictement (audit_db)                     |
| Notification     | API + worker (python:3.12-slim), postgres:16-alpine optionnel, RabbitMQ partagé, redis optionnel            | Envoi async email/push/in-app, retries            | Isolée logiquement (notifications_db)             |

Décision DB:

- Dev: un seul conteneur Postgres, plusieurs bases logiques.
- Prod: un cluster/serveur Postgres managé avec isolation logique par service; audit peut être isolé physiquement si exigence conformité forte.

---

## Section 4: Final Docker-Compose Structure (Example)

Recommandation: approche modulaire unifiée (meilleur compromis simplicité + scalabilité).

1. Fichiers

- compose.base.yml
- compose.dev.yml
- compose.prod.yml
- services/\*/Dockerfile

2. Compose base (contenu)

- gateway
- postgres
- redis
- rabbitmq
- minio
- iam_api
- procurement_api
- documents_api
- ai_api
- ai_worker
- audit_api
- notification_api
- notification_worker

3. Profils conseillés

- dev profile:
  - pgadmin (unique, pas par service)
  - minio console
  - hot reload volumes
- prod profile:
  - pas de pgadmin
  - restart policy
  - resources limits
  - healthchecks stricts
  - log rotation

4. Communication recommandée

- REST synchrone:
  - IAM auth checks
  - lecture immédiate nécessaire pour écran utilisateur
- Async messaging via RabbitMQ:
  - notifications
  - audit event ingestion
  - traitements IA
  - tâches longues/non bloquantes

Pourquoi modular unifiée est meilleure:

- Un point d’entrée opératoire.
- Moins de duplication.
- Environnements cohérents.
- Toujours extensible via profiles/overrides.

---

## Section 5: Optional Improvements (Future Scaling)

1. Remplacer runserver par gunicorn en dev avancé et prod.
2. Ajouter migration job dédié (one-shot) au lieu de lancer migrate au démarrage de chaque API.
3. Pinner toutes les versions images (pas de latest).
4. Standardiser healthcheck readiness/liveness par service.
5. Ajouter observabilité minimale:

- Logs JSON stdout
- Loki + Grafana (léger)
- Métriques de base Prometheus uniquement si nécessaire

6. Ajouter circuit-breaker/retry/timeouts côté clients HTTP inter-services.
7. Introduire Outbox pattern dans Procurement et Notification avant d’aller vers Kafka.

Décision critique finale:

- Pour votre contexte, réduire fortement le nombre de conteneurs est la bonne direction.
- Supprimer PgBouncer et Nginx par service dans la phase actuelle.
- Garder 1 gateway global + 1 postgres + 1 redis + 1 broker + 6 APIs (+2 workers) donne une architecture propre, scalable et exploitable.
