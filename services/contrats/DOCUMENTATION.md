# Documentation Complète — Service Contrats (Al-Mizan)

> **Audience :** Étudiants en 4ᵉ année d'informatique
> **Dernière mise à jour :** 27 février 2026
> **Version :** 1.1.0

---

## Table des Matières

1. [Introduction Générale](#1-introduction-générale)
2. [Architecture du Microservice](#2-architecture-du-microservice)
3. [Stack Technologique](#3-stack-technologique)
4. [Structure du Projet](#4-structure-du-projet)
5. [Modèles de Données (models.py)](#5-modèles-de-données-modelspy)
6. [Sérialiseurs (serializers.py)](#6-sérialiseurs-serializerspy)
7. [Vues et Logique Métier (views.py)](#7-vues-et-logique-métier-viewspy)
8. [Routage URL (urls.py)](#8-routage-url-urlspy)
9. [Configuration Django (settings.py)](#9-configuration-django-settingspy)
   - 9.1 Fonctions Utilitaires d'Environnement
   - 9.2 Variables d'Environnement
   - 9.3 Base de Données — Support `dj-database-url`
   - 9.4 CORS (Cross-Origin Resource Sharing)
   - 9.5 Sécurité
   - 9.6 Cache avec Redis (amélioré)
   - 9.7 Throttling (limitation de débit)
   - 9.8 Logging structuré
   - 9.9 API Documentation (drf-spectacular)
10. [Communication Inter-Services](#10-communication-inter-services)
11. [Infrastructure Docker](#11-infrastructure-docker)
    - 11.1 Dockerfile — Construction de l'Image
    - 11.2 Entrypoint — Script de Démarrage
    - 11.3 Docker Compose — Orchestration (5 services)
    - 11.4 PgBouncer — Connection Pooler
    - 11.5 Nginx — Reverse Proxy (amélioré)
    - 11.6 Gateway — Reverse Proxy Centralisé
12. [Endpoints API — Référence Complète](#12-endpoints-api--référence-complète)
13. [Schéma de Base de Données](#13-schéma-de-base-de-données)
14. [Diagramme de Flux](#14-diagramme-de-flux)
15. [Guide de Déploiement](#15-guide-de-déploiement)
16. [Bonnes Pratiques et Concepts Clés](#16-bonnes-pratiques-et-concepts-clés)
    - 16.1 Patterns Utilisés (14 patterns)
    - 16.2 Sécurité (9 mesures)
    - 16.3 Performance (8 techniques)
    - 16.4 Django REST Framework — Rappels
    - 16.5 Conventions de Code
17. [Glossaire](#17-glossaire) (21 termes)

---

## 1. Introduction Générale

### 1.1 Qu'est-ce qu'Al-Mizan ?

**Al-Mizan** (الميزان — « La Balance ») est une plateforme de gestion des marchés publics construite selon une **architecture microservices**. Chaque domaine fonctionnel (authentification, acteurs, soumissions, contrats, documents, etc.) est isolé dans son propre service indépendant.

### 1.2 Rôle du Service Contrats

Le **service Contrats** est responsable de la gestion du cycle de vie complet d'un contrat de marché public :

| Fonction              | Description                                                              |
| --------------------- | ------------------------------------------------------------------------ |
| **Validation**        | Gestion des validations internes, externes et de tutelle avant signature |
| **Contrats**          | Création, modification, suivi de statut et signature des contrats        |
| **Documents**         | Association de documents à un contrat (relation N-N)                     |
| **Recherche croisée** | Retrouver un contrat à partir de l'identifiant d'une soumission          |

### 1.3 Positionnement dans l'Architecture Globale

```
                    ┌──────────────────────────────────────┐
                    │   Gateway Nginx (port 8080)          │
                    │   Reverse proxy centralisé           │
                    └──┬──────────┬──────────┬─────────────┘
                       │          │          │
              /auth/   │ /acteurs/│ /contrats/
                       │          │          │
┌──────────────┐ ┌─────▼────────┐ ┌──────────▼──────────┐
│ Auth Service │ │Acteurs Svc   │ │ Soumissions Svc     │
└──────┬───────┘ └──────┬───────┘ └─────────┬───────────┘
       │                │                    │
       │      ┌─────────┴────────────────────┘
       │      │   HTTP REST (validation FK)
       │      ▼
       │ ┌─────────────────────┐     ┌──────────────────┐
       └►│  CONTRATS SERVICE   │◄───►│ Documents Service │
         │  (ce microservice)  │     └──────────────────┘
         └────────┬────────────┘
                  │
         ┌────────┴─────────────────┐
         │  PgBouncer (pool conn.)  │
         └────────┬─────────────────┘
                  │
         ┌────────┴────────┐
         │  PostgreSQL DB  │
         │  + Redis Cache  │
         └─────────────────┘
```

> **Nouveauté v1.1 — Gateway centralisé :** Au lieu d'exposer chaque service individuellement, un **reverse proxy Nginx unique** (`gateway/`) route les requêtes vers les services en fonction du préfixe URL (`/contrats/` → contrats service). Chaque service conserve cependant son propre Nginx local pour l'accès direct en développement.

Le service Contrats communique avec :

- **Acteurs Service** — pour valider l'existence d'une organisation (`id_organisation`)
- **Soumissions Service** — pour valider l'existence d'une soumission (`id_soumission`)
- **Contractant Service** — pour valider l'existence d'un service contractant (`id_service_contractants`)
- **Documents Service** — pour valider et enrichir les documents attachés

---

## 2. Architecture du Microservice

### 2.1 Pattern Architectural

Le service suit le pattern **MVC adapté par Django REST Framework** :

```
                    ┌──────────────────┐
                    │  Gateway Nginx   │  (Reverse proxy centralisé)
                    └────────┬─────────┘
                             │  /contrats/
                    ┌────────▼─────────┐
   Requête HTTP ───►│  Nginx (local)   │  (Reverse Proxy du service)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │Gunicorn + Uvicorn│  (Serveur ASGI, 2 workers)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │      URLs        │  (Routage)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │      Views       │  (Contrôleurs / Logique)
                    └────────┬─────────┘
                             │
               ┌─────────────┼─────────────┐
               │             │             │
          ┌────▼───┐   ┌────▼────┐   ┌────▼──────────┐
          │Serializ│   │ Models  │   │ Remote API    │
          │  ers   │   │ (ORM)   │   │  Calls        │
          └────────┘   └────┬────┘   └───────────────┘
                            │
                    ┌───────▼────────┐
                    │   PgBouncer    │  (Connection Pooler)
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  PostgreSQL    │
                    └────────────────┘
```

> **Concept clé — ASGI vs WSGI :** L'ancienne architecture utilisait **WSGI** (synchrone). La nouvelle utilise **ASGI** (Asynchronous Server Gateway Interface) via **Uvicorn** comme worker de Gunicorn. ASGI permet de gérer des connexions asynchrones et WebSocket, même si ce service utilise actuellement des vues synchrones. C'est un choix d'architecture qui uniformise tous les services et prépare l'évolution future.

> **Concept clé — PgBouncer :** Au lieu de connecter Django directement à PostgreSQL, un **connection pooler** (PgBouncer) est interposé. Il maintient un pool de connexions ouvertes vers PostgreSQL et les réutilise, évitant le coût de création/destruction d'une connexion TCP+SSL à chaque requête. En mode `transaction`, une connexion est empruntée uniquement pour la durée d'une transaction, puis retournée au pool.

### 2.2 Couches du service

| Couche            | Fichier              | Responsabilité                                                             |
| ----------------- | -------------------- | -------------------------------------------------------------------------- |
| **Modèles**       | `models.py`          | Définition du schéma de données (ORM)                                      |
| **Sérialiseurs**  | `serializers.py`     | Validation des entrées, sérialisation/désérialisation JSON ↔ objets Python |
| **Vues**          | `views.py`           | Logique métier, traitement des requêtes HTTP                               |
| **URLs**          | `urls.py`            | Table de routage (URL → vue)                                               |
| **Configuration** | `config/settings.py` | Paramètres Django, BDD, cache, sécurité                                    |

---

## 3. Stack Technologique

| Technologie                 | Version       | Rôle                                                   |
| --------------------------- | ------------- | ------------------------------------------------------ |
| **Python**                  | 3.12          | Langage d'exécution                                    |
| **Django**                  | 5.1.6         | Framework web                                          |
| **Django REST Framework**   | 3.15.2        | Toolkit pour API REST                                  |
| **drf-spectacular**         | 0.28.0        | Génération automatique du schéma OpenAPI               |
| **PostgreSQL**              | 16 (Alpine)   | Base de données relationnelle                          |
| **PgBouncer**               | latest        | Connection pooler pour PostgreSQL (mode transaction)   |
| **Redis**                   | 7.4 (Alpine)  | Cache distribué                                        |
| **Gunicorn**                | 23.0.0        | Serveur d'application (process manager)                |
| **Uvicorn**                 | 0.35.0        | Worker ASGI pour Gunicorn                              |
| **Nginx**                   | 1.27 (Alpine) | Reverse proxy (local au service + gateway centralisé)  |
| **Docker / Docker Compose** | —             | Conteneurisation et orchestration                      |
| **psycopg**                 | 3.2.6         | Pilote PostgreSQL pour Python (version 3, async-ready) |
| **dj-database-url**         | 2.3.0         | Parsing d'URL de base de données (12-Factor)           |
| **django-cors-headers**     | 4.6.0         | Gestion des en-têtes CORS                              |
| **django-redis**            | 5.4.0         | Backend cache Django ↔ Redis                           |
| **requests**                | 2.32.3        | Client HTTP pour appels inter-services                 |

> **Pourquoi Gunicorn + Uvicorn ?** Gunicorn gère les processus (workers, redémarrage, supervision), tandis qu'Uvicorn fournit la boucle événementielle ASGI dans chaque worker. C'est la combinaison recommandée en production pour les applications Django ASGI.

---

## 4. Structure du Projet

```
services/contrats/
├── docker-compose.yml          # Orchestration des 5 conteneurs
├── Dockerfile                  # Image Docker (ENTRYPOINT + CMD ASGI)
├── entrypoint.sh               # Script de démarrage (wait PgBouncer + migrations)
├── manage.py                   # CLI Django
├── nginx.conf                  # Configuration Nginx locale du service
├── requirements.txt            # Dépendances Python (11 packages)
├── .env                        # Variables d'environnement (non versionné)
├── ENDPOINTS.md                # Exemples curl pour chaque endpoint
│
├── config/                     # Configuration Django
│   ├── __init__.py
│   ├── settings.py             # ⭐ Paramètres centraux (ASGI, PgBouncer, CORS, Logging)
│   ├── urls.py                 # Routes globales (health, ready, openapi, app)
│   └── asgi.py                 # Point d'entrée ASGI (remplace wsgi.py)
│
└── contrats_service/           # Application Django principale
    ├── __init__.py
    ├── apps.py                 # Configuration de l'app Django
    ├── models.py               # ⭐ Modèles de données
    ├── serializers.py          # ⭐ Sérialiseurs DRF
    ├── views.py                # ⭐ Vues (contrôleurs)
    ├── urls.py                 # ⭐ Routes de l'app
    └── migrations/
        ├── __init__.py
        └── 0001_initial.py     # Migration initiale
```

> **Note :** Les fichiers marqués ⭐ sont les fichiers les plus importants pour comprendre la logique du service.
>
> **Changement v1.1 :** Le fichier `wsgi.py` a été supprimé — le service utilise désormais exclusivement **ASGI** via `asgi.py`. Le `Dockerfile` sépare `ENTRYPOINT` (migrations) et `CMD` (serveur ASGI).

---

## 5. Modèles de Données (models.py)

Les modèles Django définissent la structure des tables de la base de données via l'**ORM (Object-Relational Mapping)**.

### 5.1 Modèle `Validation`

```python
class Validation(models.Model):
    id_validation  = models.AutoField(primary_key=True)
    id_organisation = models.IntegerField()
    id_soumission   = models.IntegerField()
    type            = models.CharField(max_length=20, choices=[...])
    is_validated    = models.BooleanField(default=False)
    commentaire     = models.TextField(blank=True, default="")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "validation"
```

**Explication champ par champ :**

| Champ             | Type SQL             | Description                                                |
| ----------------- | -------------------- | ---------------------------------------------------------- |
| `id_validation`   | `SERIAL PRIMARY KEY` | Identifiant auto-incrémenté                                |
| `id_organisation` | `INTEGER`            | Référence vers le service Acteurs (FK distante)            |
| `id_soumission`   | `INTEGER`            | Référence vers le service Soumissions (FK distante)        |
| `type`            | `VARCHAR(20)`        | Type de validation : `interne`, `externe`, ou `tutelle`    |
| `is_validated`    | `BOOLEAN`            | Statut de validation (`true` = approuvé)                   |
| `commentaire`     | `TEXT`               | Commentaire optionnel (vide par défaut)                    |
| `created_at`      | `TIMESTAMP`          | Date de création (rempli automatiquement)                  |
| `updated_at`      | `TIMESTAMP`          | Date de dernière modification (mis à jour automatiquement) |

> **Concept clé — FK distante (Remote Foreign Key) :** Dans une architecture microservices, on ne peut pas utiliser de `ForeignKey` Django classique car les entités référencées vivent dans une autre base de données. On stocke donc un simple `IntegerField` et on valide l'existence de la ressource via un appel HTTP au service distant.

### 5.2 Modèle `Contrat`

```python
class Contrat(models.Model):
    id_contrat              = models.AutoField(primary_key=True)
    id_soumission           = models.IntegerField()
    id_service_contractants = models.IntegerField()
    numero_contrat          = models.CharField(max_length=80, unique=True)
    date_signature          = models.DateTimeField(null=True, blank=True)
    statut                  = models.CharField(max_length=30, default="brouillon")
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contrats"
```

| Champ                     | Type SQL             | Description                                            |
| ------------------------- | -------------------- | ------------------------------------------------------ |
| `id_contrat`              | `SERIAL PRIMARY KEY` | Identifiant auto-incrémenté du contrat                 |
| `id_soumission`           | `INTEGER`            | FK distante vers la soumission retenue                 |
| `id_service_contractants` | `INTEGER`            | FK distante vers le service contractant                |
| `numero_contrat`          | `VARCHAR(80) UNIQUE` | Numéro officiel du contrat (ex: `CTR-2026-001`)        |
| `date_signature`          | `TIMESTAMP NULL`     | Date de signature (rempli lors de l'action "signer")   |
| `statut`                  | `VARCHAR(30)`        | Statut du contrat : `brouillon` → `en_cours` → `signe` |
| `created_at`              | `TIMESTAMP`          | Date de création                                       |
| `updated_at`              | `TIMESTAMP`          | Date de dernière modification                          |

**Cycle de vie du statut :**

```
brouillon ──► en_cours ──► signe
                 │
                 └──► (retour possible via PATCH)
```

### 5.3 Modèle `DocumentContrat`

```python
class DocumentContrat(models.Model):
    id_contrat  = models.ForeignKey(
        Contrat, on_delete=models.CASCADE,
        db_column="id_contrat", related_name="document_links",
    )
    id_document = models.IntegerField()

    class Meta:
        db_table = "documents_contrats"
        constraints = [
            models.UniqueConstraint(
                fields=["id_contrat", "id_document"],
                name="unique_contrat_document",
            ),
        ]
```

C'est une **table d'association (jointure)** qui réalise la relation **Many-to-Many** entre `Contrat` et les documents du service Documents.

| Champ         | Description                                                              |
| ------------- | ------------------------------------------------------------------------ |
| `id`          | Clé primaire auto (BigAutoField par défaut)                              |
| `id_contrat`  | FK locale vers `Contrat` (CASCADE = supprimé si le contrat est supprimé) |
| `id_document` | FK distante vers le service Documents (IntegerField)                     |

La contrainte `UniqueConstraint` garantit qu'un même document ne peut être associé qu'une seule fois à un même contrat.

### 5.4 Diagramme Entité-Relation

```
┌─────────────────────┐         ┌──────────────────────┐
│     Validation      │         │       Contrat         │
├─────────────────────┤         ├──────────────────────┤
│ PK id_validation    │         │ PK id_contrat        │
│    id_organisation ─┼── ► Acteurs Svc   id_soumission ─┼── ► Soumissions Svc
│    id_soumission ───┼── ► Soumissions   id_service_   │
│    type             │         │    contractants ──────┼── ► Contractant Svc
│    is_validated     │         │    numero_contrat     │
│    commentaire      │         │    date_signature     │
│    created_at       │         │    statut             │
│    updated_at       │         │    created_at         │
└─────────────────────┘         │    updated_at         │
                                └──────────┬───────────┘
                                           │ 1
                                           │
                                           │ N
                                ┌──────────▼───────────┐
                                │   DocumentContrat     │
                                ├──────────────────────┤
                                │ PK id                │
                                │ FK id_contrat        │
                                │    id_document ──────┼── ► Documents Svc
                                └──────────────────────┘
```

---

## 6. Sérialiseurs (serializers.py)

Les **sérialiseurs** (serializers) de Django REST Framework jouent un double rôle :

1. **Désérialisation** : Convertir le JSON entrant en objets Python et **valider** les données
2. **Sérialisation** : Convertir les objets Django (querysets) en JSON pour la réponse HTTP

### 6.1 Fonction utilitaire `_validate_remote_fk`

```python
def _validate_remote_fk(value, service_url_setting, path_template, field_label):
    base_url = getattr(settings, service_url_setting, "")
    if not base_url:
        return value  # skip si URL non configurée
    url = f"{base_url.rstrip('/')}/{path_template.format(value)}"
    timeout = getattr(settings, "REMOTE_SERVICE_TIMEOUT", 3)
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException:
        raise serializers.ValidationError(
            f"Unable to validate {field_label} at this time"
        )
    if response.status_code != 200:
        raise serializers.ValidationError(f"{field_label} does not exist")
    return value
```

**Fonctionnement :**

```
1. Récupère l'URL de base du service distant depuis settings.py
2. Construit l'URL complète : base_url + path_template (ex: /soumissions/42)
3. Effectue un GET HTTP avec un timeout de 3 secondes
4. Si le service est injoignable → ValidationError ("Unable to validate...")
5. Si status ≠ 200 → ValidationError ("... does not exist")
6. Si status = 200 → la valeur est valide, on la retourne
```

> **Pourquoi cette approche ?** En microservices, on ne peut pas utiliser de contrainte `FOREIGN KEY` SQL entre services. Cette fonction remplace le `ForeignKey` au niveau applicatif en vérifiant l'existence de la ressource via HTTP.

### 6.2 `ValidationSerializer` et `ValidationUpdateSerializer`

```python
class ValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Validation
        fields = ["id_validation", "id_organisation", "id_soumission",
                  "type", "is_validated", "commentaire", "created_at", "updated_at"]
        read_only_fields = ["id_validation", "created_at", "updated_at"]

    def validate_id_organisation(self, value):
        return _validate_remote_fk(value, "ACTEURS_SERVICE_URL",
                                   "organisations/{}", "id_organisation")

    def validate_id_soumission(self, value):
        return _validate_remote_fk(value, "SOUMISSIONS_SERVICE_URL",
                                   "soumissions/{}", "id_soumission")
```

**Points importants :**

- `read_only_fields` empêche le client de modifier `id_validation`, `created_at`, `updated_at`
- Les méthodes `validate_<field_name>` sont appelées **automatiquement** par DRF lors de la validation
- `ValidationUpdateSerializer` est identique mais sans `read_only_fields` (utilisé pour PATCH/PUT)

### 6.3 `ContratSerializer` et `ContratUpdateSerializer`

Même pattern que `ValidationSerializer`, avec validation distante vers :

- **Soumissions Service** pour `id_soumission`
- **Contractant Service** pour `id_service_contractants`

### 6.4 `DocumentContratSerializer`

```python
class DocumentContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentContrat
        fields = ["id", "id_contrat", "id_document"]
        read_only_fields = ["id"]
```

Sérialiseur simple pour la table d'association. Le champ `id` est en lecture seule.

---

## 7. Vues et Logique Métier (views.py)

### 7.1 Vues de Santé (`HealthView`, `ReadyView`)

#### `HealthView` — Vérification de disponibilité basique

```python
class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})
```

- **GET /health** → Retourne `{"status": "ok"}` (HTTP 200)
- Utilisé par les outils d'orchestration (Docker, Kubernetes) pour le **liveness probe**

#### `ReadyView` — Vérification de disponibilité complète

```python
class ReadyView(APIView):
    def get(self, request):
        # 1. Teste la connexion PostgreSQL
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        # 2. Teste la connexion Redis
        cache.set("contrats:ready", "1", timeout=5)
        cache.get("contrats:ready")
        # Retourne 200 si tout OK, 503 sinon
```

- **GET /ready** → Vérifie que la BDD **et** le cache sont opérationnels
- Utilisé pour le **readiness probe** : le service ne reçoit du trafic que s'il est réellement prêt

> **Concept clé — Health vs Ready :**
>
> - **Health** (liveness) : "Le processus tourne-t-il ?" → S'il échoue, on redémarre le conteneur
> - **Ready** (readiness) : "Le service peut-il traiter des requêtes ?" → S'il échoue, on arrête d'envoyer du trafic

### 7.2 CRUD Validations

#### `ValidationListCreateView`

| Méthode | URL            | Action                                                       |
| ------- | -------------- | ------------------------------------------------------------ |
| GET     | `/validations` | Liste toutes les validations (ordonnées par `id_validation`) |
| POST    | `/validations` | Crée une nouvelle validation                                 |

Hérite de `ListCreateAPIView` qui fournit automatiquement :

- `GET` → `list()` : Récupère le queryset, le sérialise et retourne une liste JSON
- `POST` → `create()` : Désérialise le JSON, valide, sauvegarde en BDD et retourne l'objet créé

#### `ValidationRetrieveUpdateDeleteView`

| Méthode | URL                 | Action                             |
| ------- | ------------------- | ---------------------------------- |
| GET     | `/validations/{id}` | Récupère une validation par son ID |
| PUT     | `/validations/{id}` | Mise à jour complète               |
| PATCH   | `/validations/{id}` | Mise à jour partielle              |
| DELETE  | `/validations/{id}` | Suppression                        |

Configuration importante :

```python
lookup_field = "id_validation"       # Champ du modèle utilisé pour la recherche
lookup_url_kwarg = "validation_id"   # Nom du paramètre dans l'URL
```

#### `ValidationApproveView` — Action métier d'approbation

```python
class ValidationApproveView(APIView):
    def post(self, request, validation_id):
        validation = Validation.objects.filter(id_validation=validation_id).first()
        if not validation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        validation.is_validated = True
        validation.save(update_fields=["is_validated", "updated_at"])
        return Response(ValidationSerializer(validation).data)
```

- **POST /validations/{id}/approuver**
- Met `is_validated = True`
- Utilise `update_fields` pour ne modifier que les colonnes nécessaires (optimisation SQL)

#### `ValidationRejectView` — Action métier de rejet

- **POST /validations/{id}/rejeter**
- Met `is_validated = False`
- Accepte un `commentaire` optionnel dans le body pour expliquer le rejet

### 7.3 CRUD Contrats

#### `ContratListCreateView` et `ContratRetrieveUpdateDeleteView`

Même pattern que les validations. Le `ContratUpdateSerializer` est utilisé pour les méthodes PUT/PATCH.

#### `ContratSignView` — Action métier de signature

```python
class ContratSignView(APIView):
    def post(self, request, contrat_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if contrat.statut == "signe":
            return Response(
                {"detail": "Le contrat est déjà signé."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contrat.statut = "signe"
        contrat.date_signature = timezone.now()
        contrat.save(update_fields=["statut", "date_signature", "updated_at"])
        return Response(ContratSerializer(contrat).data)
```

**Logique métier :**

1. Vérifie que le contrat existe (sinon 404)
2. Vérifie que le contrat n'est pas déjà signé (sinon 400)
3. Met le statut à `"signe"` et remplit `date_signature` avec l'heure courante
4. Retourne le contrat mis à jour

### 7.4 Gestion Documents ↔ Contrat

#### `ContratDocumentsListView` — GET /contrats/{id}/documents

```
1. Vérifie que le contrat existe
2. Récupère les liens DocumentContrat pour ce contrat
3. Pour chaque document, tente d'enrichir avec les détails du service Documents
4. Si le service Documents est indisponible, retourne juste {id_document: X}
```

> **Pattern d'enrichissement (Data Enrichment) :** Les données minimales (identifiants) sont stockées localement. Lors de la lecture, on appelle le service distant pour obtenir les détails complets. Si le service est indisponible, on retourne les données minimales — cela assure la **résilience**.

#### `ContratDocumentDetailView` — POST & DELETE

| Méthode | Action                         | Code retour                        |
| ------- | ------------------------------ | ---------------------------------- |
| POST    | Attache un document au contrat | 201 (créé) ou 200 (déjà existant)  |
| DELETE  | Détache un document du contrat | 204 (supprimé) ou 404 (non trouvé) |

Le POST utilise `get_or_create` pour être **idempotent** : appeler deux fois la même requête ne crée pas de doublon.

### 7.5 Recherche Croisée

#### `SoumissionContratView` — GET /soumissions/{id}/contrat

Permet de retrouver le contrat associé à une soumission donnée. C'est une **vue de commodité** qui évite aux clients de faire un filtre côté client.

---

## 8. Routage URL (urls.py)

### 8.1 Routes globales (`config/urls.py`)

```python
urlpatterns = [
    path("health",       HealthView.as_view()),      # Liveness probe
    path("ready",        ReadyView.as_view()),        # Readiness probe
    path("openapi.json", SpectacularAPIView.as_view()),  # Schéma OpenAPI auto-généré
    path("",             include("contrats_service.urls")),  # Routes de l'app
]
```

### 8.2 Routes de l'application (`contrats_service/urls.py`)

| Méthode(s)              | URL                                 | Vue                                  | Description            |
| ----------------------- | ----------------------------------- | ------------------------------------ | ---------------------- |
| GET, POST               | `/validations`                      | `ValidationListCreateView`           | Lister / Créer         |
| GET, PUT, PATCH, DELETE | `/validations/<id>`                 | `ValidationRetrieveUpdateDeleteView` | CRUD unitaire          |
| POST                    | `/validations/<id>/approuver`       | `ValidationApproveView`              | Approuver              |
| POST                    | `/validations/<id>/rejeter`         | `ValidationRejectView`               | Rejeter                |
| GET, POST               | `/contrats`                         | `ContratListCreateView`              | Lister / Créer         |
| GET, PUT, PATCH, DELETE | `/contrats/<id>`                    | `ContratRetrieveUpdateDeleteView`    | CRUD unitaire          |
| POST                    | `/contrats/<id>/signer`             | `ContratSignView`                    | Signer                 |
| GET                     | `/contrats/<id>/documents`          | `ContratDocumentsListView`           | Documents liés         |
| POST, DELETE            | `/contrats/<id>/documents/<doc_id>` | `ContratDocumentDetailView`          | Attacher/Détacher      |
| GET                     | `/soumissions/<id>/contrat`         | `SoumissionContratView`              | Contrat par soumission |

> **Convention de nommage des URLs :**
>
> - Pas de trailing slash (`/validations` et non `/validations/`)
> - Les actions métier sont des sous-ressources (`/signer`, `/approuver`, `/rejeter`)
> - Les paramètres d'URL utilisent `<int:xxx_id>` pour garantir un entier

---

## 9. Configuration Django (settings.py)

### 9.1 Fonctions Utilitaires d'Environnement

Le `settings.py` utilise trois fonctions pour lire les variables d'environnement de manière robuste :

```python
def env_bool(name, default=False):
    """Retourne True si la variable vaut '1', 'true', 'yes' ou 'on'."""

def env_str(name, default=""):
    """Retourne la variable, ou default si vide ou absente."""

def env_list(name, default=""):
    """Retourne une liste en splitant par virgule."""
```

> **Pourquoi `env_str` en plus de `os.getenv` ?** `os.getenv("VAR", "default")` retourne `""` (chaîne vide) si la variable est définie mais vide. `env_str` retourne le `default` dans ce cas — comportement plus intuitif.

### 9.2 Variables d'Environnement

Le service est entièrement configurable via des **variables d'environnement** (12-Factor App) :

**Variables principales :**

| Variable                  | Défaut                                | Description                                     |
| ------------------------- | ------------------------------------- | ----------------------------------------------- |
| `SECRET_KEY` / `DJANGO_SECRET_KEY` | `unsafe-dev-secret`          | Clé secrète Django (obligatoire en production)  |
| `DJANGO_ENV`              | `development`                         | Environnement (`development` / `production`)    |
| `DEBUG` / `DJANGO_DEBUG`  | `true` (dev) / `false` (prod)         | Mode debug (auto-détection par DJANGO_ENV)      |
| `ALLOWED_HOSTS`           | `localhost,127.0.0.1`                 | Hôtes autorisés (séparés par virgule)           |
| `CORS_ALLOWED_ORIGINS`    | `""`                                  | Origines CORS autorisées                        |
| `LOG_LEVEL`               | `INFO`                                | Niveau de logging (`DEBUG`, `INFO`, `WARNING`)  |

**Base de données (PgBouncer) :**

| Variable            | Défaut                | Description                               |
| ------------------- | --------------------- | ----------------------------------------- |
| `DB_NAME`           | `contrats_db`         | Nom de la base PostgreSQL                 |
| `DB_USER`           | `contrats_user`       | Utilisateur PostgreSQL                    |
| `DB_PASSWORD`       | `contrats_password`   | Mot de passe PostgreSQL                   |
| `DB_HOST`           | `pgbouncer_contrats`  | Hôte — pointe vers PgBouncer (pas la BDD directe) |
| `DB_PORT`           | `6432`                | Port PgBouncer (PostgreSQL natif = 5432)  |
| `DATABASE_URL`      | `""`                  | URL complète (prioritaire si définie)     |
| `CONN_MAX_AGE`      | `120`                 | Durée de vie d'une connexion (secondes)   |

> **Important :** Notez que `DB_HOST` par défaut pointe vers `pgbouncer_contrats` (port `6432`) et non vers `contrats_db` (port `5432`). Django ne communique **jamais** directement avec PostgreSQL — PgBouncer sert d'intermédiaire.

**Cache Redis :**

| Variable                | Défaut                                   | Description                 |
| ----------------------- | ---------------------------------------- | --------------------------- |
| `REDIS_URL`             | `redis://redis_contrats:6379/1`          | URL de connexion Redis      |
| `REDIS_PASSWORD`        | `contrats_redis_password`                | Mot de passe Redis          |
| `CACHE_TTL`             | `60`                                     | TTL par défaut du cache (s) |
| `REDIS_MAX_CONNECTIONS` | `200`                                    | Connexions max au pool      |

**Throttling (limitation de débit) :**

| Variable               | Défaut         | Description                        |
| ---------------------- | -------------- | ---------------------------------- |
| `THROTTLE_ANON_RATE`   | `240/minute`   | Requêtes max par minute (anonyme)  |
| `THROTTLE_USER_RATE`   | `1200/minute`  | Requêtes max par minute (authentifié) |

**Services distants :**

| Variable                  | Défaut | Description                                     |
| ------------------------- | ------ | ----------------------------------------------- |
| `SOUMISSIONS_SERVICE_URL` | `""`   | URL du service Soumissions                      |
| `CONTRACTANT_SERVICE_URL` | `""`   | URL du service Contractant                      |
| `ACTEURS_SERVICE_URL`     | `""`   | URL du service Acteurs                          |
| `DOCUMENTS_SERVICE_URL`   | `""`   | URL du service Documents                        |
| `REMOTE_SERVICE_TIMEOUT`  | `3`    | Timeout (en secondes) des appels inter-services |
| `GUNICORN_WORKERS`        | `2`    | Nombre de workers Gunicorn                      |
| `GUNICORN_TIMEOUT`        | `60`   | Timeout Gunicorn (secondes)                     |

### 9.3 Base de Données — Support `dj-database-url`

Le settings.py supporte deux modes de configuration de la BDD :

```python
# Mode 1 : Variables individuelles (défaut)
DB_NAME = env_str("DB_NAME", "contrats_db")
DB_HOST = env_str("DB_HOST", "pgbouncer_contrats")
DB_PORT = env_str("DB_PORT", "6432")

# Mode 2 : URL complète (prioritaire si défini)
DATABASE_URL = env_str("DATABASE_URL", "")
if DATABASE_URL:
    default_db = dj_database_url.parse(DATABASE_URL, ...)
```

Options importantes pour PgBouncer :

```python
default_db["DISABLE_SERVER_SIDE_CURSORS"] = True   # Obligatoire avec PgBouncer (mode transaction)
default_db["CONN_HEALTH_CHECKS"] = True            # Vérifie que la connexion est vivante
default_db["CONN_MAX_AGE"] = 120                   # Réutilise les connexions pendant 2 minutes
```

> **Pourquoi `DISABLE_SERVER_SIDE_CURSORS` ?** PgBouncer en mode `transaction` ne maintient pas de session côté serveur entre les transactions. Les curseurs côté serveur (utilisés par Django pour `iterator()`) ne fonctionnent donc pas. Ce flag force Django à utiliser des curseurs côté client.

### 9.4 CORS (Cross-Origin Resource Sharing)

```python
INSTALLED_APPS = [
    ...
    "corsheaders",       # Nouveau : gestion CORS
    ...
]
MIDDLEWARE = [
    ...
    "corsheaders.middleware.CorsMiddleware",   # Avant CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    ...
]
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)
```

> **Concept clé — CORS :** Quand un navigateur sur `http://frontend.example.com` appelle l'API sur `http://api.example.com`, le navigateur bloque la requête par sécurité (politique same-origin). Les en-têtes CORS autorisent explicitement ces appels cross-origin. Le middleware `corsheaders` ajoute automatiquement les headers `Access-Control-Allow-Origin` etc.

### 9.5 Sécurité

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
```

La sécurité s'adapte à l'environnement :

| Paramètre              | Développement | Production                  |
| ----------------------- | ------------- | --------------------------- |
| `SESSION_COOKIE_SECURE` | `False`       | `True` (auto via DJANGO_ENV) |
| `CSRF_COOKIE_SECURE`    | `False`       | `True` (auto via DJANGO_ENV) |
| `SECURE_SSL_REDIRECT`   | `False`       | Configurable                 |
| `SECRET_KEY`            | dev key OK    | Obligatoire (RuntimeError)   |

### 9.6 Cache avec Redis (amélioré)

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": CACHE_TTL,                           # TTL configurable (défaut 60s)
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 200,                  # Pool de connexions dédié
                "retry_on_timeout": True,                # Réessai automatique
            },
        },
    }
}
```

Améliorations par rapport à v1.0 :

- **Pool de connexions** avec limite configurable (évite l'épuisement sous forte charge)
- **Retry on timeout** : réessai automatique si Redis est momentanément lent
- **TTL configurable** via `CACHE_TTL`

### 9.7 Throttling (limitation de débit)

```python
REST_FRAMEWORK = {
    ...
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "240/minute",
        "user": "1200/minute",
    },
}
```

> **Concept clé — Throttling :** Le throttling limite le nombre de requêtes qu'un client peut faire dans un intervalle de temps. Cela protège l'API contre les abus et les attaques par déni de service (DDoS). `AnonRateThrottle` s'applique aux utilisateurs non authentifiés, `UserRateThrottle` aux authentifiés.

### 9.8 Logging structuré

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,          # Configurable via env var (défaut: INFO)
    },
}
```

Le logging est configuré pour écrire sur la sortie standard (stdout), ce qui est la bonne pratique pour les applications conteneurisées — Docker capture automatiquement les logs.

### 9.9 API Documentation (drf-spectacular)

```python
SPECTACULAR_SETTINGS = {
    "TITLE": "Al-Mizan Contrats Service API",
    "VERSION": "1.0.0",
}
```

Le schéma OpenAPI est disponible à **GET /openapi.json** et peut être importé dans Swagger UI ou Postman.

---

## 10. Communication Inter-Services

### 10.1 Principe

En architecture microservices, chaque service possède sa propre base de données (**Database per Service pattern**). Pour vérifier l'existence d'une entité gérée par un autre service, on effectue un **appel HTTP synchrone**.

### 10.2 Flux de Validation d'une FK Distante

```
Client                  Contrats Service           Soumissions Service
  │                           │                           │
  │  POST /contrats           │                           │
  │  {id_soumission: 42}      │                           │
  │──────────────────────────►│                           │
  │                           │  GET /soumissions/42      │
  │                           │──────────────────────────►│
  │                           │                           │
  │                           │  200 OK                   │
  │                           │◄──────────────────────────│
  │                           │                           │
  │                           │  (validation OK, save)    │
  │  201 Created              │                           │
  │◄──────────────────────────│                           │
```

### 10.3 Gestion des Erreurs

| Scénario                        | Comportement                      |
| ------------------------------- | --------------------------------- |
| Service distant indisponible    | `ValidationError` → HTTP 400      |
| Timeout dépassé (3s par défaut) | `ValidationError` → HTTP 400      |
| Ressource inexistante (404)     | `ValidationError` → HTTP 400      |
| URL du service non configurée   | Validation ignorée (mode dégradé) |

### 10.4 Tableau des Appels Inter-Services

| Depuis (champ)                     | Vers (service) | URL appelée                                                |
| ---------------------------------- | -------------- | ---------------------------------------------------------- |
| `Validation.id_organisation`       | Acteurs        | `GET {ACTEURS_SERVICE_URL}/organisations/{id}`             |
| `Validation.id_soumission`         | Soumissions    | `GET {SOUMISSIONS_SERVICE_URL}/soumissions/{id}`           |
| `Contrat.id_soumission`            | Soumissions    | `GET {SOUMISSIONS_SERVICE_URL}/soumissions/{id}`           |
| `Contrat.id_service_contractants`  | Contractant    | `GET {CONTRACTANT_SERVICE_URL}/services-contractants/{id}` |
| `DocumentContrat` (enrichissement) | Documents      | `GET {DOCUMENTS_SERVICE_URL}/documents/{id}`               |

---

## 11. Infrastructure Docker

### 11.1 Dockerfile — Construction de l'Image

```dockerfile
FROM python:3.12-slim                    # Image de base légère

ENV PYTHONDONTWRITEBYTECODE=1            # Pas de fichiers .pyc
ENV PYTHONUNBUFFERED=1                   # Logs en temps réel
ENV PIP_NO_CACHE_DIR=1                   # Pas de cache pip (image plus légère)

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app
RUN chmod +x /app/entrypoint.sh
RUN useradd -m appuser && chown -R appuser:appuser /app

USER appuser                             # Exécution en tant qu'utilisateur non-root
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --workers ${GUNICORN_WORKERS:-2} \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout ${GUNICORN_TIMEOUT:-60} \
    --keep-alive 5 \
    --access-logfile - --error-logfile -"]
```

**Bonnes pratiques appliquées :**

- `python:3.12-slim` → Image minimale (pas de compilateurs inutiles)
- `COPY requirements.txt` avant `COPY .` → **Cache Docker** : si les dépendances ne changent pas, la couche est réutilisée
- `useradd appuser` → Sécurité : le conteneur ne tourne pas en root
- **Séparation ENTRYPOINT / CMD** → `ENTRYPOINT` exécute le script d'initialisation (attente BDD, migrations), puis `exec "$@"` transmet le `CMD` comme processus principal

> **Concept clé — ENTRYPOINT vs CMD :** `ENTRYPOINT` est le programme qui s'exécute toujours. `CMD` fournit les arguments par défaut. Grâce à `exec "$@"` à la fin de l'entrypoint, le CMD est exécuté en PID 1, ce qui permet à Docker de gérer correctement les signaux (SIGTERM pour arrêt gracieux).

> **Concept clé — ASGI :** Le `CMD` lance Gunicorn avec le worker `UvicornWorker` et le point d'entrée `config.asgi:application`. Contrairement à WSGI (synchrone), **ASGI** (Asynchronous Server Gateway Interface) supporte les requêtes asynchrones, WebSockets et HTTP/2. Gunicorn gère les processus (workers), Uvicorn gère le protocole ASGI dans chaque worker.

### 11.2 Entrypoint — Script de Démarrage

```bash
#!/bin/sh
set -eu

# Défaults pointant vers PgBouncer (pas PostgreSQL directement)
DB_HOST="${DB_HOST:-pgbouncer_contrats}"
DB_PORT="${DB_PORT:-6432}"

# 1. Attend que PgBouncer soit prêt (jusqu'à 90 secondes)
python - <<PY
import os, socket, sys, time
host = os.getenv("DB_HOST", "pgbouncer_contrats")
port = int(os.getenv("DB_PORT", "6432"))
for _ in range(90):
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit(1)
PY

# 2. Applique les migrations de base de données
python manage.py migrate --noinput

# 3. Transfère le contrôle au CMD du Dockerfile
exec "$@"
```

**Différences clés avec la v1.0 :**

| Aspect          | v1.0                                         | v1.1 (actuel)                           |
| --------------- | -------------------------------------------- | --------------------------------------- |
| Host attendu    | `contrats-db:5432` (PostgreSQL direct)       | `pgbouncer_contrats:6432` (PgBouncer)   |
| Lancement       | `exec gunicorn config.wsgi:application ...`  | `exec "$@"` (délègue au CMD)            |
| Protocole       | WSGI                                         | ASGI (Uvicorn)                          |
| Workers default | 3                                            | 2                                       |

> **Pourquoi `exec "$@"` ?** Cette syntaxe shell exécute le `CMD` du Dockerfile en remplacement du processus shell actuel (via `exec`). `$@` représente tous les arguments passés au script — ici, le CMD complet de Gunicorn. Le processus Gunicorn devient PID 1, recevant directement les signaux Docker.

### 11.3 Docker Compose — Orchestration

Le fichier `docker-compose.yml` définit **5 services** (un de plus qu'en v1.0 — PgBouncer) :

```
┌─────────────────────────────────────────────────────────┐
│                    contrats-net (bridge)                  │
│                                                          │
│  ┌───────────────┐                                      │
│  │  contrats_db   │ (PostgreSQL 16)                     │
│  │  Port interne  │ 5432                                │
│  └───────┬────────┘                                     │
│          │ depends_on (healthy)                          │
│  ┌───────▼──────────────┐    ┌────────────────┐        │
│  │ pgbouncer_contrats   │    │ redis_contrats  │        │
│  │ Connection Pooler     │    │ (Redis 7.4)     │        │
│  │ Port: 6432           │    │ Port: 6379      │        │
│  └───────┬──────────────┘    └───────┬─────────┘        │
│          │                           │                   │
│          └──────────┬────────────────┘                   │
│                     │ depends_on (healthy × 3)           │
│          ┌──────────▼───────────┐                       │
│          │    contrats_api      │                       │
│          │ (Django + Gunicorn   │                       │
│          │  + Uvicorn ASGI)     │                       │
│          └──────────┬───────────┘                       │
│                     │ depends_on                         │
│          ┌──────────▼───────────┐     ┌──────────┐     │
│          │   contrats_nginx     │────►│ Port     │     │
│          │   (Reverse Proxy)    │     │ :18085   │     │
│          └──────────────────────┘     └──────────┘     │
└─────────────────────────────────────────────────────────┘
```

| Service               | Image                      | Rôle                      | Healthcheck      | Dépend de         |
| --------------------- | -------------------------- | ------------------------- | ---------------- | ----------------- |
| `contrats_db`         | `postgres:16-alpine`       | Base de données           | `pg_isready`     | —                 |
| `pgbouncer_contrats`  | `edoburu/pgbouncer:latest` | Connection pooler         | `pg_isready`     | `contrats_db`     |
| `redis_contrats`      | `redis:7.4-alpine`         | Cache + sessions          | `redis-cli ping` | —                 |
| `contrats_api`        | Build local (Dockerfile)   | Application Django (ASGI) | —                | db + pgb + redis  |
| `contrats_nginx`      | `nginx:1.27-alpine`        | Reverse proxy             | —                | `contrats_api`    |

> **Convention de nommage :** Les services utilisent des **underscores** (`contrats_api`, `redis_contrats`) au lieu de tirets (`contrats-api`). Ceci est une convention du projet Al-Mizan pour cohérence entre les services.

### 11.4 PgBouncer — Connection Pooler

PgBouncer est un **pooler de connexions léger** placé entre Django et PostgreSQL :

```
Django ──(N connexions)──► PgBouncer ──(M connexions)──► PostgreSQL
                            N >> M
```

**Configuration dans docker-compose.yml :**

| Variable                       | Défaut             | Description                             |
| ------------------------------ | ------------------ | --------------------------------------- |
| `PGBOUNCER_PORT`               | `6432`             | Port d'écoute de PgBouncer              |
| `PGBOUNCER_AUTH_TYPE`          | `scram-sha-256`    | Méthode d'authentification              |
| `PGBOUNCER_POOL_MODE`         | `transaction`      | Mode de pooling (voir ci-dessous)       |
| `PGBOUNCER_MAX_CLIENT_CONN`   | `500`              | Max connexions côté client              |
| `PGBOUNCER_DEFAULT_POOL_SIZE` | `40`               | Connexions maintenues vers PostgreSQL   |
| `PGBOUNCER_RESERVE_POOL_SIZE` | `10`               | Pool de réserve (pic de charge)         |

> **Concept clé — Modes de pooling :**
>
> - **session** : une connexion PG par session client (peu d'économie)
> - **transaction** : une connexion PG par transaction (optimal — utilisé ici)
> - **statement** : une connexion PG par requête SQL (trop restrictif pour Django)
>
> En mode `transaction`, 500 clients Django peuvent partager 40 connexions PostgreSQL réelles. C'est ce qui permet de servir beaucoup de requêtes simultanées sans épuiser les connexions PostgreSQL (max_connections par défaut = 100).

### 11.5 Nginx — Reverse Proxy (amélioré)

```nginx
worker_processes auto;

events {
    worker_connections 2048;
}

http {
    sendfile on;
    tcp_nopush on;                           # Optimise l'envoi réseau
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 1000;
    server_tokens off;                       # Cache la version Nginx

    # Compression GZIP — réduit le trafic JSON
    gzip on;
    gzip_comp_level 5;
    gzip_min_length 512;
    gzip_types application/json application/*+json;

    # Proxy — buffers optimisés
    proxy_connect_timeout 10s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    proxy_buffering on;
    proxy_buffers 32 16k;
    proxy_busy_buffers_size 64k;
    client_max_body_size 20m;

    upstream contrats_api {
        server contrats_api:8000;
        keepalive 64;                        # Pool de connexions persistantes
    }

    server {
        listen 80;
        location / {
            proxy_pass http://contrats_api;
            proxy_http_version 1.1;          # HTTP/1.1 pour keepalive
            proxy_set_header Connection "";   # Supprime "close" pour keepalive
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

**Améliorations par rapport à v1.0 :**

| Fonctionnalité         | v1.0            | v1.1 (actuel)                        |
| ---------------------- | --------------- | ------------------------------------ |
| Compression            | Aucune          | GZIP (JSON, level 5)                 |
| Keepalive upstream     | Aucun           | `keepalive 64` (pool de connexions)  |
| HTTP version           | 1.0 (défaut)   | 1.1 (keepalive possible)             |
| Worker connections     | 1024 (défaut)   | 2048                                 |
| Proxy buffers          | Défaut Nginx    | `32 × 16k` (optimisé pour JSON)     |
| `tcp_nopush`           | Non             | Oui (optimise l'envoi réseau)        |
| `server_tokens`        | Oui (défaut)    | `off` (cache la version Nginx)       |

> **Concept clé — `keepalive 64` :** Sans keepalive upstream, Nginx ouvre et ferme une connexion TCP pour chaque requête vers Gunicorn. Avec `keepalive 64`, il maintient un pool de 64 connexions persistantes, éliminant la latence du TCP handshake.

### 11.6 Gateway — Reverse Proxy Centralisé

En plus du Nginx propre à chaque service, le projet utilise une **Gateway centralisée** (dans `gateway/`) qui route les requêtes vers les différents microservices :

```
Client ──► Gateway (port 80/443)
              ├── /auth/     → auth_nginx:80
              ├── /acteurs/  → acteurs_nginx:80
              └── /contrats/ → contrats_nginx:80
```

Le routing est défini par des blocs `location` dans le Nginx gateway :

```nginx
location /contrats/ {
    proxy_pass http://contrats_backend/;
}
```

L'upstream `contrats_backend` pointe vers `contrats_nginx` à l'adresse `{CONTRATS_HOST}:{CONTRATS_PORT}` (configurable via variables d'environnement template).

---

## 12. Endpoints API — Référence Complète

**Base URL :** `http://localhost:18085`

### 12.1 Endpoints système

| Méthode | URL             | Description            | Réponse                      |
| ------- | --------------- | ---------------------- | ---------------------------- |
| GET     | `/health`       | Probe de vivacité      | `{"status": "ok"}`           |
| GET     | `/ready`        | Probe de disponibilité | `{"status": "ready"}` ou 503 |
| GET     | `/openapi.json` | Schéma OpenAPI         | Document JSON OpenAPI 3.0    |

### 12.2 Validations

#### Lister les validations

```http
GET /validations
```

**Réponse 200 :**

```json
[
  {
    "id_validation": 1,
    "id_organisation": 1,
    "id_soumission": 1,
    "type": "interne",
    "is_validated": false,
    "commentaire": "Validation initiale",
    "created_at": "2026-02-26T10:00:00Z",
    "updated_at": "2026-02-26T10:00:00Z"
  }
]
```

#### Créer une validation

```http
POST /validations
Content-Type: application/json

{
    "id_organisation": 1,
    "id_soumission": 1,
    "type": "interne",
    "commentaire": "Validation initiale"
}
```

| Champ             | Obligatoire | Type   | Valeurs possibles                  |
| ----------------- | ----------- | ------ | ---------------------------------- |
| `id_organisation` | Oui         | int    | ID existant dans Acteurs           |
| `id_soumission`   | Oui         | int    | ID existant dans Soumissions       |
| `type`            | Oui         | string | `interne`, `externe`, `tutelle`    |
| `is_validated`    | Non         | bool   | `true` / `false` (défaut: `false`) |
| `commentaire`     | Non         | string | Texte libre                        |

**Réponse 201 Created :**

```json
{
  "id_validation": 1,
  "id_organisation": 1,
  "id_soumission": 1,
  "type": "interne",
  "is_validated": false,
  "commentaire": "Validation initiale",
  "created_at": "2026-02-26T10:00:00Z",
  "updated_at": "2026-02-26T10:00:00Z"
}
```

#### Récupérer une validation

```http
GET /validations/{id}
```

#### Modifier une validation

```http
PATCH /validations/{id}
Content-Type: application/json

{
    "commentaire": "Mise à jour du commentaire"
}
```

#### Supprimer une validation

```http
DELETE /validations/{id}
```

**Réponse :** 204 No Content

#### Approuver une validation

```http
POST /validations/{id}/approuver
```

**Réponse 200 :** L'objet validation avec `is_validated: true`

#### Rejeter une validation

```http
POST /validations/{id}/rejeter
Content-Type: application/json

{
    "commentaire": "Motif du rejet"
}
```

**Réponse 200 :** L'objet validation avec `is_validated: false`

### 12.3 Contrats

#### Lister les contrats

```http
GET /contrats
```

#### Créer un contrat

```http
POST /contrats
Content-Type: application/json

{
    "id_soumission": 1,
    "id_service_contractants": 1,
    "numero_contrat": "CTR-2026-001"
}
```

| Champ                     | Obligatoire | Type     | Description                 |
| ------------------------- | ----------- | -------- | --------------------------- |
| `id_soumission`           | Oui         | int      | ID de la soumission retenue |
| `id_service_contractants` | Oui         | int      | ID du service contractant   |
| `numero_contrat`          | Oui         | string   | Numéro unique du contrat    |
| `date_signature`          | Non         | datetime | Date de signature           |
| `statut`                  | Non         | string   | Défaut: `brouillon`         |

**Réponse 201 Created :**

```json
{
  "id_contrat": 1,
  "id_soumission": 1,
  "id_service_contractants": 1,
  "numero_contrat": "CTR-2026-001",
  "date_signature": null,
  "statut": "brouillon",
  "created_at": "2026-02-26T10:00:00Z",
  "updated_at": "2026-02-26T10:00:00Z"
}
```

#### Modifier un contrat

```http
PATCH /contrats/{id}
Content-Type: application/json

{
    "statut": "en_cours"
}
```

#### Supprimer un contrat

```http
DELETE /contrats/{id}
```

#### Signer un contrat

```http
POST /contrats/{id}/signer
```

**Réponse 200 :**

```json
{
  "id_contrat": 1,
  "statut": "signe",
  "date_signature": "2026-02-26T14:30:00Z",
  "...": "..."
}
```

**Codes d'erreur :**

- `404` : Contrat non trouvé
- `400` : Contrat déjà signé (`{"detail": "Le contrat est déjà signé."}`)

### 12.4 Documents du Contrat

#### Lister les documents

```http
GET /contrats/{id}/documents
```

**Réponse 200 :** Array de documents (enrichis si le service Documents est disponible)

#### Attacher un document

```http
POST /contrats/{contrat_id}/documents/{document_id}
```

| Code | Signification                   |
| ---- | ------------------------------- |
| 201  | Lien créé                       |
| 200  | Lien déjà existant (idempotent) |
| 404  | Contrat ou document inexistant  |
| 503  | Service Documents indisponible  |

#### Détacher un document

```http
DELETE /contrats/{contrat_id}/documents/{document_id}
```

### 12.5 Recherche Croisée

```http
GET /soumissions/{soumission_id}/contrat
```

Retourne le contrat associé à la soumission, ou 404 si aucun contrat n'est trouvé.

---

## 13. Schéma de Base de Données

### 13.1 Table `validation`

```sql
CREATE TABLE validation (
    id_validation    SERIAL PRIMARY KEY,
    id_organisation  INTEGER NOT NULL,
    id_soumission    INTEGER NOT NULL,
    type             VARCHAR(20) NOT NULL CHECK (type IN ('interne','externe','tutelle')),
    is_validated     BOOLEAN NOT NULL DEFAULT FALSE,
    commentaire      TEXT NOT NULL DEFAULT '',
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### 13.2 Table `contrats`

```sql
CREATE TABLE contrats (
    id_contrat              SERIAL PRIMARY KEY,
    id_soumission           INTEGER NOT NULL,
    id_service_contractants INTEGER NOT NULL,
    numero_contrat          VARCHAR(80) NOT NULL UNIQUE,
    date_signature          TIMESTAMP WITH TIME ZONE,
    statut                  VARCHAR(30) NOT NULL DEFAULT 'brouillon',
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### 13.3 Table `documents_contrats`

```sql
CREATE TABLE documents_contrats (
    id          BIGSERIAL PRIMARY KEY,
    id_contrat  INTEGER NOT NULL REFERENCES contrats(id_contrat) ON DELETE CASCADE,
    id_document INTEGER NOT NULL,
    CONSTRAINT unique_contrat_document UNIQUE (id_contrat, id_document)
);
```

---

## 14. Diagramme de Flux

### 14.1 Flux de Création d'un Contrat

```
Client                    Contrats API               Soumissions Svc        Contractant Svc
  │                           │                           │                       │
  │  POST /contrats           │                           │                       │
  │  {id_soumission: 42,     │                           │                       │
  │   id_service_contractants │                           │                       │
  │   : 7, numero_contrat:   │                           │                       │
  │   "CTR-2026-001"}        │                           │                       │
  │──────────────────────────►│                           │                       │
  │                           │                           │                       │
  │                           │  validate_id_soumission   │                       │
  │                           │  GET /soumissions/42      │                       │
  │                           │──────────────────────────►│                       │
  │                           │  200 OK                   │                       │
  │                           │◄──────────────────────────│                       │
  │                           │                           │                       │
  │                           │  validate_id_service_contractants                 │
  │                           │  GET /services-contractants/7                     │
  │                           │──────────────────────────────────────────────────►│
  │                           │  200 OK                                           │
  │                           │◄──────────────────────────────────────────────────│
  │                           │                           │                       │
  │                           │  INSERT INTO contrats ... │                       │
  │                           │  (PostgreSQL)             │                       │
  │                           │                           │                       │
  │  201 Created              │                           │                       │
  │  {id_contrat: 1, ...}    │                           │                       │
  │◄──────────────────────────│                           │                       │
```

### 14.2 Flux de Signature d'un Contrat

```
Client                    Contrats API
  │                           │
  │  POST /contrats/1/signer  │
  │──────────────────────────►│
  │                           │
  │                           │  SELECT * FROM contrats WHERE id_contrat = 1
  │                           │
  │                           │  statut == "signe" ?
  │                           │  ├── Oui → 400 "Le contrat est déjà signé"
  │                           │  └── Non → continuer
  │                           │
  │                           │  UPDATE contrats
  │                           │    SET statut = 'signe',
  │                           │        date_signature = NOW()
  │                           │    WHERE id_contrat = 1
  │                           │
  │  200 OK                   │
  │  {statut: "signe", ...}  │
  │◄──────────────────────────│
```

---

## 15. Guide de Déploiement

### 15.1 Prérequis

- Docker Engine ≥ 20.10
- Docker Compose ≥ 2.0

### 15.2 Fichier `.env`

Créer un fichier `.env` à la racine du service (`services/contrats/.env`) :

```env
# ──────── Django ────────
DJANGO_SECRET_KEY=une_cle_secrete_longue_et_aleatoire
DJANGO_ENV=production                          # development | production
ALLOWED_HOSTS=localhost,127.0.0.1,api.example.com
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com
LOG_LEVEL=INFO

# ──────── Base de données ────────
DB_NAME=contrats_db
DB_USER=contrats_user
DB_PASSWORD=un_mot_de_passe_securise
DB_HOST=pgbouncer_contrats                     # PgBouncer (pas la BDD directe)
DB_PORT=6432                                   # Port PgBouncer (pas 5432)
CONN_MAX_AGE=120

# ──────── PgBouncer ────────
PGBOUNCER_PORT=6432
PGBOUNCER_AUTH_TYPE=scram-sha-256
PGBOUNCER_POOL_MODE=transaction
PGBOUNCER_MAX_CLIENT_CONN=500
PGBOUNCER_DEFAULT_POOL_SIZE=40
PGBOUNCER_RESERVE_POOL_SIZE=10

# ──────── Redis ────────
REDIS_URL=redis://:redis_password@redis_contrats:6379/1
REDIS_PASSWORD=redis_password
CACHE_TTL=60
REDIS_MAX_CONNECTIONS=200

# ──────── Gunicorn / ASGI ────────
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=60
PORT=8000

# ──────── Throttling ────────
THROTTLE_ANON_RATE=240/minute
THROTTLE_USER_RATE=1200/minute

# ──────── Nginx ────────
CONTRATS_NGINX_PORT=18085

# ──────── Services distants (optionnel) ────────
SOUMISSIONS_SERVICE_URL=http://soumissions_nginx:80
CONTRACTANT_SERVICE_URL=http://contractant_nginx:80
ACTEURS_SERVICE_URL=http://acteurs_nginx:80
DOCUMENTS_SERVICE_URL=http://documents_nginx:80
REMOTE_SERVICE_TIMEOUT=3
```

> **Points importants :**
>
> - `DB_HOST` pointe vers `pgbouncer_contrats` (port `6432`), pas vers `contrats_db` (port `5432`)
> - `REDIS_URL` utilise `redis_contrats` (avec underscore, pas tiret)
> - `DJANGO_ENV=production` active automatiquement les cookies sécurisés et lève une erreur si `DJANGO_SECRET_KEY` est la valeur par défaut
> - Les URLs des services distants utilisent des underscores (`soumissions_nginx`, pas `soumissions-nginx`)

### 15.3 Lancement

```bash
cd services/contrats
docker compose up -d --build
```

Les 5 conteneurs démarrent dans l'ordre suivant (grâce aux `depends_on` + healthchecks) :

```
1. contrats_db (PostgreSQL)        ← démarre en premier
2. pgbouncer_contrats + redis_contrats  ← attendent que la BDD soit healthy
3. contrats_api (Django)           ← attend que PgBouncer + Redis soient healthy
4. contrats_nginx (Nginx)          ← attend que l'API soit lancée
```

### 15.4 Vérifications

```bash
# Vérifier que les 5 conteneurs tournent
docker compose ps

# Tester la santé
curl http://localhost:18085/health
# → {"status":"ok"}

curl http://localhost:18085/ready
# → {"status":"ready"}

# Consulter les logs
docker compose logs -f contrats_api

# Vérifier PgBouncer
docker compose exec pgbouncer_contrats pg_isready -h 127.0.0.1 -p 6432
```

### 15.5 Arrêt

```bash
docker compose down          # Arrêter les conteneurs
docker compose down -v       # Arrêter + supprimer les volumes (données)
```

---

## 16. Bonnes Pratiques et Concepts Clés

### 16.1 Patterns Utilisés

| Pattern                       | Où                                 | Explication                                                   |
| ----------------------------- | ---------------------------------- | ------------------------------------------------------------- |
| **Database per Service**      | Architecture globale               | Chaque microservice a sa propre BDD pour l'isolation          |
| **Remote FK Validation**      | `serializers.py`                   | Vérification d'existence par appel HTTP plutôt que FK SQL     |
| **Data Enrichment**           | `ContratDocumentsListView`         | Données minimales locales, détails récupérés à la lecture     |
| **Graceful Degradation**      | `_validate_remote_fk()`            | Si l'URL n'est pas configurée, la validation est ignorée      |
| **Idempotency**               | `ContratDocumentDetailView.post()` | `get_or_create` évite les doublons sur appels répétés         |
| **Health/Ready Probes**       | `HealthView`, `ReadyView`          | Séparation liveness vs readiness pour l'orchestration         |
| **12-Factor App**             | `settings.py`                      | Configuration via variables d'environnement                   |
| **Least Privilege**           | `Dockerfile`                       | Le conteneur s'exécute en tant qu'utilisateur non-root        |
| **Connection Pooling**        | PgBouncer                          | Mutualisation des connexions PostgreSQL (500 → 40)            |
| **ASGI**                      | Gunicorn + Uvicorn                 | Serveur asynchrone supportant HTTP/2 et WebSockets            |
| **ENTRYPOINT/CMD Separation** | Dockerfile                         | Init (migrations) séparé du processus principal (Gunicorn)    |
| **Centralized Gateway**       | `gateway/nginx.conf`               | Point d'entrée unique pour tous les microservices             |
| **Rate Limiting (Throttling)**| DRF throttle classes               | Protection contre les abus et DDoS                            |
| **Structured Logging**        | `LOGGING` dict                     | Logs formatés sur stdout pour capture Docker                  |

### 16.2 Sécurité

1. **Pas de root dans les conteneurs** — `USER appuser` dans le Dockerfile
2. **Secret Key obligatoire** en production — RuntimeError si `DJANGO_ENV=production` et clé par défaut
3. **Headers de sécurité** — X-Frame-Options (`DENY`), Content-Type-Nosniff, Referrer-Policy (`same-origin`)
4. **Cookies sécurisés** — `SESSION_COOKIE_SECURE` et `CSRF_COOKIE_SECURE` activés automatiquement en production (via `DJANGO_ENV`)
5. **Nginx** → `server_tokens off` (pas de version divulguée)
6. **Timeouts** sur tous les appels inter-services (3 secondes par défaut)
7. **CORS explicite** — Origines autorisées listées (pas de wildcard `*` en production)
8. **Throttling** — Limitation de débit par utilisateur et par IP anonyme
9. **PgBouncer** → `scram-sha-256` (authentification forte, pas `trust`)

### 16.3 Performance

| Technique                 | Composant     | Impact                                                      |
| ------------------------- | ------------- | ----------------------------------------------------------- |
| PgBouncer connection pool | Base de données | 500 clients Django partagent 40 connexions PostgreSQL       |
| Redis connection pool     | Cache         | Pool de 200 connexions avec retry on timeout                |
| Nginx keepalive 64        | Reverse proxy | Connexions persistantes → pas de TCP handshake par requête  |
| Gzip compression          | Nginx         | Trafic JSON réduit (~60-80% sur les grosses réponses)       |
| Proxy buffers 32×16k      | Nginx         | Lit la réponse complète avant de l'envoyer au client        |
| ASGI (Uvicorn)            | Application   | Traitement asynchrone, meilleure utilisation des workers    |
| `CONN_MAX_AGE=120`        | Django ORM    | Réutilise les connexions pendant 2 minutes                  |
| `tcp_nopush`              | Nginx         | Combine les petits paquets en un seul envoi réseau          |

### 16.4 Django REST Framework — Rappels

**`ModelSerializer`** :

- Génère automatiquement les champs à partir du modèle Django
- `read_only_fields` empêche la modification par le client
- Les méthodes `validate_<nom_du_champ>(self, value)` sont appelées automatiquement

**`ListCreateAPIView`** :

- Combine `ListModelMixin` (GET → liste) + `CreateModelMixin` (POST → création)
- `get_serializer_class()` permet d'utiliser un sérialiseur différent selon la méthode HTTP

**`RetrieveUpdateDestroyAPIView`** :

- Combine GET (détail), PUT/PATCH (modification), DELETE (suppression)
- `lookup_field` + `lookup_url_kwarg` configurent la recherche en BDD

**`APIView`** :

- Vue de base pour les actions custom (signer, approuver, rejeter)
- On écrit manuellement les méthodes `get()`, `post()`, `delete()`, etc.

### 16.5 Conventions de Code

- **Pas de trailing slash** dans les URLs
- **Noms de tables explicites** via `db_table` dans `Meta`
- **`update_fields`** dans `save()` pour optimiser les requêtes SQL
- **`filter().first()`** plutôt que `get()` pour éviter les exceptions non contrôlées
- **Codes HTTP sémantiques** : 200, 201, 204, 400, 404, 503
- **Noms de services avec underscores** : `contrats_api`, `redis_contrats`, `pgbouncer_contrats` (pas de tirets)

---

## 17. Glossaire

| Terme                       | Définition                                                                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **API REST**                | Interface de programmation utilisant les méthodes HTTP (GET, POST, PUT, PATCH, DELETE) sur des ressources identifiées par des URLs |
| **ASGI**                    | Asynchronous Server Gateway Interface — successeur de WSGI, supporte l'asynchrone, WebSockets et HTTP/2                           |
| **Connection Pooler**       | Composant qui mutualise un pool de connexions BDD entre de nombreux clients (ex: PgBouncer)                                        |
| **CORS**                    | Cross-Origin Resource Sharing — mécanisme HTTP permettant à un serveur d'autoriser les requêtes depuis d'autres origines           |
| **CRUD**                    | Create, Read, Update, Delete — les quatre opérations de base sur les données                                                       |
| **dj-database-url**         | Bibliothèque Python qui parse une URL de BDD (`postgres://user:pass@host/db`) en dict Django                                      |
| **Django ORM**              | Object-Relational Mapping — couche d'abstraction qui permet de manipuler la BDD via des objets Python                              |
| **DRF**                     | Django REST Framework — bibliothèque pour construire des APIs REST avec Django                                                     |
| **FK (Foreign Key)**        | Clé étrangère — référence vers une autre entité                                                                                    |
| **Gateway**                 | Reverse proxy centralisé qui route les requêtes vers les différents microservices selon l'URL                                      |
| **Gunicorn**                | Green Unicorn — serveur WSGI/ASGI de production pour Python, gère plusieurs workers (processus)                                    |
| **Idempotent**              | Une opération qui, exécutée plusieurs fois, produit le même résultat qu'une seule exécution                                        |
| **Microservice**            | Service indépendant avec sa propre BDD, communiquant via des API                                                                   |
| **Migration**               | Fichier Python décrivant les changements de schéma de BDD (géré par Django)                                                        |
| **Nginx**                   | Serveur web/reverse proxy performant                                                                                               |
| **OpenAPI**                 | Standard de description d'APIs REST (anciennement Swagger)                                                                         |
| **PgBouncer**               | Connection pooler léger pour PostgreSQL — mutualise les connexions entre les workers Django et la BDD                              |
| **Probe (Health/Ready)**    | Endpoint utilisé par un orchestrateur pour vérifier l'état d'un service                                                            |
| **Throttling**              | Limitation du nombre de requêtes par client dans un intervalle de temps — protège contre les abus et DDoS                          |
| **12-Factor App**           | Méthodologie de développement d'applications cloud-native (config par env vars, logs sur stdout, etc.)                             |
| **Uvicorn**                 | Serveur ASGI ultra-rapide basé sur `uvloop` — utilisé comme worker dans Gunicorn pour le support asynchrone                        |
| **Sérialiseur**          | Composant qui convertit des données entre format JSON et objets Python                                                             |
| **WSGI**                 | Web Server Gateway Interface — standard Python pour communiquer entre un serveur web et une application                            |
| **12-Factor App**        | Méthodologie de développement de services cloud-natifs (configuration via env vars, etc.)                                          |

---

> **Document rédigé dans le cadre du projet Al-Mizan — Module Marchés Publics**
> **Service :** Contrats | **Port par défaut :** 18085 | **Version API :** 1.0.0
