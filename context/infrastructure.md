# 🏗️ Al-Mizan Infrastructure Guide

> **Pour les développeurs et agents IA** : Ce document explique comment démarrer et utiliser l'infrastructure partagée du backend Al-Mizan.

---

## 📋 Vue d'Ensemble

Al-Mizan utilise une **infrastructure partagée** pour tous les microservices :

| Composant | Port | Description |
|-----------|------|-------------|
| **PostgreSQL 16** | 5433 | Base de données unique avec 12 databases logiques |
| **Redis 7.4** | 6379 | Cache partagé et rate-limiting |
| **PgAdmin 4** | 5050 | Interface web d'administration (optionnel) |

### Avantages
- ✅ Moins de conteneurs à gérer (3 au lieu de 36+)
- ✅ Ressources optimisées (un seul processus PostgreSQL)
- ✅ Simplification des opérations (backup, monitoring)
- ✅ Isolation logique maintenue (une DB par service)

---

## 🚀 Démarrage Rapide

### Prérequis
- Docker Desktop installé et démarré
- Git pour cloner le repository

### Étape 1 : Démarrer l'Infrastructure

```bash
# Depuis la racine du projet
cd infrastructure

# Démarrer PostgreSQL + Redis + PgAdmin
docker compose up -d

# Vérifier que tout fonctionne
docker compose ps
```

**Sortie attendue :**
```
NAME                      STATUS
almizan_shared_postgres   running (healthy)
almizan_shared_redis      running (healthy)
almizan_pgadmin           running
```

### Étape 2 : Démarrer un Service

```bash
# Exemple : démarrer le service Auth
cd ../services/auth
docker compose up --build

# Ou en arrière-plan
docker compose up --build -d
```

### Étape 3 : Vérifier la Connexion

```bash
# Test endpoint health
curl http://localhost:18080/health
```

---

## 🗄️ Bases de Données

L'infrastructure crée automatiquement 12 databases au premier démarrage :

| Service | Database | User | Redis DB |
|---------|----------|------|----------|
| auth | `auth_db` | `auth_user` | 0 |
| acteurs | `acteurs_db` | `acteurs_user` | 1 |
| appels | `appels_db` | `appels_user` | 2 |
| contrats | `contrats_db` | `contrats_user` | 3 |
| contractant | `contractant_db` | `contractant_user` | 4 |
| evaluations | `evaluations_db` | `evaluations_user` | 5 |
| notifications | `notifications_db` | `notifications_user` | 6 |
| ia | `ia_db` | `ia_user` | 7 |
| documents | `documents_db` | `documents_user` | 8 |
| soumissions | `soumissions_db` | `soumissions_user` | 9 |
| audit | `audit_db` | `audit_user` | 10 |
| recours | `recours_db` | `recours_user` | 11 |

### Mot de passe par défaut
Tous les users utilisent le pattern `<service>_password` (ex: `auth_password`).

---

## 🔧 Configuration des Services

Chaque service doit configurer ces variables d'environnement :

### Connexion Base de Données

```env
# Via variables individuelles
DB_HOST=host.docker.internal
DB_PORT=5433
DB_NAME=auth_db
DB_USER=auth_user
DB_PASSWORD=auth_password

# Ou via DATABASE_URL (format Django/SQLAlchemy)
DATABASE_URL=postgres://auth_user:auth_password@host.docker.internal:5433/auth_db
```

### Connexion Redis

```env
# Format standard avec authentification
REDIS_URL=redis://:almizan_redis_password@host.docker.internal:6379/0

# Le chiffre final (0-15) est l'index de la DB Redis pour isoler les services
```

### Note sur `host.docker.internal`
- Sous **Windows/Mac** : Docker Desktop fournit `host.docker.internal` automatiquement
- Sous **Linux** : Ajouter `--add-host=host.docker.internal:host-gateway` ou utiliser le réseau Docker

---

## 🌐 Ports des Services

| Service | Port API | Port NGINX |
|---------|----------|------------|
| auth | 8000 | 18080 |
| acteurs | 8000 | 18081 |
| contractant | 8000 | 18082 |
| appels | 8000 | 18083 |
| contrats | 8000 | 18085 |
| evaluations | 8000 | 18086 |
| notifications | 8000 | 18087 |
| ia | 8000 | 18088 |
| documents | 8003 | - |
| soumissions | 8004 | - |
| audit | 8000 | - |

---

## 🛠️ Commandes Utiles

### Infrastructure

```bash
# Démarrer l'infrastructure
cd infrastructure && docker compose up -d

# Voir les logs
docker compose logs -f shared_postgres
docker compose logs -f shared_redis

# Arrêter sans supprimer les données
docker compose stop

# Arrêter ET supprimer les données (⚠️ destructif)
docker compose down -v

# Redémarrer proprement
docker compose restart
```

### Accès Base de Données

```bash
# Via psql dans le conteneur
docker exec -it almizan_shared_postgres psql -U almizan_admin

# Lister les databases
\l

# Se connecter à une database spécifique
\c auth_db

# Lister les tables
\dt
```

### Accès Redis

```bash
# Via redis-cli dans le conteneur
docker exec -it almizan_shared_redis redis-cli -a almizan_redis_password

# Vérifier la connexion
PING

# Voir les clés d'une DB spécifique
SELECT 0
KEYS *
```

### Accès PgAdmin (Interface Web)

1. Ouvrir http://localhost:5050
2. Login : `admin@almizan.dz` / `admin`
3. Ajouter un serveur :
   - Host : `shared_postgres`
   - Port : `5433`
   - Username : `almizan_admin`
   - Password : `almizan_admin_password`

---

## 🔄 Workflow de Développement

### Démarrage Complet (tous les services)

```bash
# Terminal 1 : Infrastructure
cd infrastructure && docker compose up -d

# Terminal 2 : Service Auth
cd services/auth && docker compose up --build

# Terminal 3 : Service Acteurs
cd services/acteurs && docker compose up --build

# Terminal 4 : Gateway (optionnel)
cd gateway && docker compose up --build
```

### Développement d'un Service Unique

```bash
# 1. S'assurer que l'infrastructure tourne
cd infrastructure && docker compose ps

# 2. Lancer le service en mode développement
cd services/documents
docker compose up --build

# 3. Les logs s'affichent en temps réel
# Ctrl+C pour arrêter
```

### Réinitialiser une Database

```bash
# Se connecter en admin
docker exec -it almizan_shared_postgres psql -U almizan_admin

# Supprimer et recréer une database
DROP DATABASE auth_db;
CREATE DATABASE auth_db OWNER auth_user;
\c auth_db
GRANT ALL ON SCHEMA public TO auth_user;
\q

# Relancer les migrations du service
cd services/auth
docker compose exec auth_api python manage.py migrate
```

---

## 🐛 Dépannage

### "Connection refused" à la base de données

1. Vérifier que l'infrastructure tourne :
   ```bash
   docker compose -f infrastructure/docker-compose.yml ps
   ```
2. Vérifier que `DB_HOST=host.docker.internal` est configuré
3. Sous Linux, utiliser l'IP du host ou le réseau Docker

### "FATAL: password authentication failed"

- Vérifier le mot de passe dans `.env` du service
- Les credentials par défaut sont dans `infrastructure/.env`

### "Redis connection error"

1. Vérifier que Redis tourne :
   ```bash
   docker exec -it almizan_shared_redis redis-cli -a almizan_redis_password PING
   ```
2. Vérifier le format de `REDIS_URL` (inclure le mot de passe)

### Données corrompues après mise à jour

```bash
# Reset complet (⚠️ perd toutes les données)
cd infrastructure
docker compose down -v
docker compose up -d
```

---

## 📁 Structure des Fichiers

```
Al-Mizan-Backend/
├── infrastructure/           # Infrastructure partagée
│   ├── docker-compose.yml   # PostgreSQL + Redis + PgAdmin
│   ├── init-databases.sql   # Script de création des DBs
│   ├── .env                 # Variables d'environnement
│   └── README.md            # Documentation infrastructure
│
├── gateway/                  # API Gateway (NGINX)
│   └── docker-compose.yml
│
├── services/
│   ├── auth/                # Service authentification
│   │   ├── docker-compose.yml
│   │   ├── .env
│   │   └── ...
│   ├── acteurs/             # Service acteurs
│   ├── appels/              # Service appels d'offres
│   ├── documents/           # Service GED (+ MinIO local)
│   ├── soumissions/         # Service soumissions
│   └── ...                  # Autres services
│
└── context/                  # Documentation développeur
    ├── infrastructure.md    # Ce fichier
    ├── database.md          # Schéma BDD
    └── ...
```

---

## ⚡ Différences avec l'Ancienne Architecture

| Aspect | Avant | Maintenant |
|--------|-------|------------|
| PostgreSQL | 1 conteneur par service | 1 conteneur partagé |
| PgBouncer | 1 conteneur par service | ❌ Supprimé |
| Redis | 1 conteneur par service | 1 conteneur partagé |
| Isolation | Conteneurs séparés | Databases logiques |
| Démarrage | Chaque service autonome | Infrastructure d'abord |

### Migration depuis l'ancienne architecture

Si vous avez des données existantes dans les anciens conteneurs :

1. Exporter les données : `pg_dump -U <user> <db> > backup.sql`
2. Démarrer la nouvelle infrastructure
3. Importer : `psql -U <user> -d <db> < backup.sql`

---

## 🔐 Sécurité en Production

⚠️ **Les valeurs par défaut sont pour le développement uniquement !**

En production, modifiez :
- `POSTGRES_ADMIN_PASSWORD`
- `REDIS_PASSWORD`
- Tous les mots de passe des services (`*_DB_PASSWORD`)
- `PGADMIN_PASSWORD` (ou désactivez PgAdmin)

Utilisez des secrets Docker ou un gestionnaire de secrets (Vault, AWS Secrets Manager).
