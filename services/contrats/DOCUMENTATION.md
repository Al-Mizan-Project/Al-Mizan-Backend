# Documentation Complète — Service Contrats (Al-Mizan)

> **Audience :** Étudiants en 4ᵉ année d'informatique
> **Dernière mise à jour :** 26 février 2026
> **Version :** 1.0.0

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
10. [Communication Inter-Services](#10-communication-inter-services)
11. [Infrastructure Docker](#11-infrastructure-docker)
12. [Endpoints API — Référence Complète](#12-endpoints-api--référence-complète)
13. [Schéma de Base de Données](#13-schéma-de-base-de-données)
14. [Diagramme de Flux](#14-diagramme-de-flux)
15. [Guide de Déploiement](#15-guide-de-déploiement)
16. [Bonnes Pratiques et Concepts Clés](#16-bonnes-pratiques-et-concepts-clés)
17. [Glossaire](#17-glossaire)

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
┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐
│ Auth Service │    │ Acteurs Service  │    │ Soumissions Svc   │
└──────┬───────┘    └────────┬─────────┘    └─────────┬─────────┘
       │                     │                        │
       │         ┌───────────┴────────────────────────┘
       │         │   HTTP REST (validation FK)
       │         ▼
       │    ┌─────────────────────┐     ┌──────────────────┐
       └───►│  CONTRATS SERVICE   │◄───►│ Documents Service │
            │  (ce microservice)  │     └──────────────────┘
            └────────┬────────────┘
                     │
            ┌────────┴────────┐
            │  PostgreSQL DB  │
            │  + Redis Cache  │
            └─────────────────┘
```

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
                    ┌─────────┐
   Requête HTTP ───►│  Nginx  │  (Reverse Proxy)
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │Gunicorn │  (Serveur WSGI, 3 workers)
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │  URLs   │  (Routage)
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │  Views  │  (Contrôleurs / Logique)
                    └────┬────┘
                         │
               ┌─────────┼─────────┐
               │         │         │
          ┌────▼───┐ ┌───▼────┐ ┌──▼──────────┐
          │Serializ│ │ Models │ │ Remote API  │
          │  ers   │ │ (ORM)  │ │  Calls      │
          └────────┘ └───┬────┘ └─────────────┘
                         │
                    ┌────▼────┐
                    │PostgreSQL│
                    └─────────┘
```

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

| Technologie                 | Version       | Rôle                                     |
| --------------------------- | ------------- | ---------------------------------------- |
| **Python**                  | 3.12          | Langage d'exécution                      |
| **Django**                  | 5.1.6         | Framework web                            |
| **Django REST Framework**   | 3.15.2        | Toolkit pour API REST                    |
| **drf-spectacular**         | 0.28.0        | Génération automatique du schéma OpenAPI |
| **PostgreSQL**              | 16 (Alpine)   | Base de données relationnelle            |
| **Redis**                   | 7.4 (Alpine)  | Cache distribué                          |
| **Gunicorn**                | 23.0.0        | Serveur WSGI en production               |
| **Nginx**                   | 1.27 (Alpine) | Reverse proxy                            |
| **Docker / Docker Compose** | —             | Conteneurisation et orchestration        |
| **psycopg**                 | 3.2.6         | Pilote PostgreSQL pour Python            |
| **django-redis**            | 5.4.0         | Backend cache Django ↔ Redis             |
| **requests**                | 2.32.3        | Client HTTP pour appels inter-services   |

---

## 4. Structure du Projet

```
services/contrats/
├── docker-compose.yml          # Orchestration des conteneurs
├── Dockerfile                  # Image Docker du service
├── entrypoint.sh               # Script de démarrage (migrations + Gunicorn)
├── manage.py                   # CLI Django
├── nginx.conf                  # Configuration Nginx
├── requirements.txt            # Dépendances Python
├── ENDPOINTS.md                # Exemples curl pour chaque endpoint
│
├── config/                     # Configuration Django
│   ├── __init__.py
│   ├── settings.py             # ⭐ Paramètres centraux
│   ├── urls.py                 # Routes globales (health, ready, openapi, app)
│   ├── asgi.py                 # Point d'entrée ASGI
│   └── wsgi.py                 # Point d'entrée WSGI
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

### 9.1 Variables d'Environnement

Le service est entièrement configurable via des **variables d'environnement** (12-Factor App) :

| Variable                  | Défaut                                          | Description                                     |
| ------------------------- | ----------------------------------------------- | ----------------------------------------------- |
| `DJANGO_SECRET_KEY`       | `unsafe-dev-secret`                             | Clé secrète Django (obligatoire en production)  |
| `DJANGO_DEBUG`            | `False`                                         | Mode debug                                      |
| `DJANGO_ALLOWED_HOSTS`    | `localhost,127.0.0.1`                           | Hôtes autorisés                                 |
| `DB_NAME`                 | `contrats_db`                                   | Nom de la base PostgreSQL                       |
| `DB_USER`                 | `contrats_user`                                 | Utilisateur PostgreSQL                          |
| `DB_PASSWORD`             | `contrats_password`                             | Mot de passe PostgreSQL                         |
| `DB_HOST`                 | `contrats-db`                                   | Hôte PostgreSQL                                 |
| `DB_PORT`                 | `5432`                                          | Port PostgreSQL                                 |
| `REDIS_URL`               | `redis://:redis_password@contrats-redis:6379/1` | URL de connexion Redis                          |
| `SOUMISSIONS_SERVICE_URL` | `""`                                            | URL du service Soumissions                      |
| `CONTRACTANT_SERVICE_URL` | `""`                                            | URL du service Contractant                      |
| `ACTEURS_SERVICE_URL`     | `""`                                            | URL du service Acteurs                          |
| `DOCUMENTS_SERVICE_URL`   | `""`                                            | URL du service Documents                        |
| `REMOTE_SERVICE_TIMEOUT`  | `3`                                             | Timeout (en secondes) des appels inter-services |
| `GUNICORN_WORKERS`        | `3`                                             | Nombre de workers Gunicorn                      |
| `GUNICORN_TIMEOUT`        | `60`                                            | Timeout Gunicorn (secondes)                     |

### 9.2 Sécurité

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

- **HSTS** : Configurable via `DJANGO_SECURE_HSTS_SECONDS`
- **SSL Redirect** : Configurable via `DJANGO_SECURE_SSL_REDIRECT`
- Le service fait confiance au header `X-Forwarded-Proto` de Nginx pour détecter HTTPS

### 9.3 Cache avec Redis

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
```

Redis est utilisé pour :

- Le **readiness check** (vérification de la connexion cache)
- Potentiellement du caching de requêtes (extensible)

### 9.4 API Documentation (drf-spectacular)

```python
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
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
```

**Bonnes pratiques appliquées :**

- `python:3.12-slim` → Image minimale (pas de compilateurs inutiles)
- `COPY requirements.txt` avant `COPY .` → **Cache Docker** : si les dépendances ne changent pas, la couche est réutilisée
- `useradd appuser` → Sécurité : le conteneur ne tourne pas en root

### 11.2 Entrypoint — Script de Démarrage

```bash
#!/bin/sh
set -eu

# 1. Attend que PostgreSQL soit prêt (jusqu'à 90 secondes)
python - <<PY
import socket, sys, time, os
host = os.getenv("DB_HOST", "contrats-db")
port = int(os.getenv("DB_PORT", "5432"))
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

# 3. Lance Gunicorn
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - --error-logfile -
```

> **Pourquoi attendre la BDD ?** Docker Compose démarre les conteneurs en parallèle. Même avec `depends_on`, le conteneur PostgreSQL peut ne pas être prêt à accepter des connexions. Le script attend activement via un test TCP.

### 11.3 Docker Compose — Orchestration

Le fichier `docker-compose.yml` définit **4 services** :

```
┌─────────────────────────────────────────────────────┐
│                  contrats-net (bridge)               │
│                                                      │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ contrats-db  │    │contrats-redis│               │
│  │ (PostgreSQL) │    │   (Redis)    │               │
│  └──────┬───────┘    └──────┬───────┘               │
│         │                   │                        │
│         └───────┬───────────┘                        │
│                 │ depends_on                         │
│         ┌───────▼──────────┐                        │
│         │  contrats-api    │                        │
│         │  (Django+Gunicorn)│                        │
│         └───────┬──────────┘                        │
│                 │ depends_on                         │
│         ┌───────▼──────────┐     ┌─────────┐       │
│         │  contrats-nginx  │────►│ Port    │       │
│         │  (Reverse Proxy) │     │ exposé  │       │
│         └──────────────────┘     └─────────┘       │
└─────────────────────────────────────────────────────┘
```

| Service          | Image                    | Rôle               | Healthcheck      |
| ---------------- | ------------------------ | ------------------ | ---------------- |
| `contrats-db`    | `postgres:16-alpine`     | Base de données    | `pg_isready`     |
| `contrats-redis` | `redis:7.4-alpine`       | Cache              | `redis-cli ping` |
| `contrats-api`   | Build local (Dockerfile) | Application Django | —                |
| `contrats-nginx` | `nginx:1.27-alpine`      | Reverse proxy      | —                |

### 11.4 Nginx — Reverse Proxy

```nginx
upstream contrats_api {
    server contrats-api:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://contrats_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Rôle de Nginx ici :**

- Gère les connexions statiques et les headers
- Transmet les headers `X-Real-IP` et `X-Forwarded-For` pour le logging
- Limite la taille des requêtes à 20 Mo (`client_max_body_size 20m`)
- Cache les connexions (`keepalive_timeout 65`)

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
# Base de données
DB_NAME=contrats_db
DB_USER=contrats_user
DB_PASSWORD=un_mot_de_passe_securise

# Redis
REDIS_URL=redis://:redis_password@contrats-redis:6379/1
REDIS_PASSWORD=redis_password

# Django
DJANGO_SECRET_KEY=une_cle_secrete_longue_et_aleatoire
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:18085

# Gunicorn
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=60

# Nginx
CONTRATS_NGINX_PORT=18085

# Services distants (optionnel)
SOUMISSIONS_SERVICE_URL=http://soumissions-nginx:80
CONTRACTANT_SERVICE_URL=http://contractant-nginx:80
ACTEURS_SERVICE_URL=http://acteurs-nginx:80
DOCUMENTS_SERVICE_URL=http://documents-nginx:80
REMOTE_SERVICE_TIMEOUT=3
```

### 15.3 Lancement

```bash
cd services/contrats
docker compose up -d --build
```

### 15.4 Vérifications

```bash
# Vérifier que tous les conteneurs tournent
docker compose ps

# Tester la santé
curl http://localhost:18085/health
# → {"status":"ok"}

curl http://localhost:18085/ready
# → {"status":"ready"}

# Consulter les logs
docker compose logs -f contrats-api
```

### 15.5 Arrêt

```bash
docker compose down          # Arrêter les conteneurs
docker compose down -v       # Arrêter + supprimer les volumes (données)
```

---

## 16. Bonnes Pratiques et Concepts Clés

### 16.1 Patterns Utilisés

| Pattern                  | Où                                 | Explication                                               |
| ------------------------ | ---------------------------------- | --------------------------------------------------------- |
| **Database per Service** | Architecture globale               | Chaque microservice a sa propre BDD pour l'isolation      |
| **Remote FK Validation** | `serializers.py`                   | Vérification d'existence par appel HTTP plutôt que FK SQL |
| **Data Enrichment**      | `ContratDocumentsListView`         | Données minimales locales, détails récupérés à la lecture |
| **Graceful Degradation** | `_validate_remote_fk()`            | Si l'URL n'est pas configurée, la validation est ignorée  |
| **Idempotency**          | `ContratDocumentDetailView.post()` | `get_or_create` évite les doublons sur appels répétés     |
| **Health/Ready Probes**  | `HealthView`, `ReadyView`          | Séparation liveness vs readiness pour l'orchestration     |
| **12-Factor App**        | `settings.py`                      | Configuration via variables d'environnement               |
| **Least Privilege**      | `Dockerfile`                       | Le conteneur s'exécute en tant qu'utilisateur non-root    |

### 16.2 Sécurité

1. **Pas de root dans les conteneurs** — `USER appuser` dans le Dockerfile
2. **Secret Key obligatoire** en production — RuntimeError si `DEBUG=False` et clé par défaut
3. **Headers de sécurité** — HSTS, X-Frame-Options, Content-Type-Nosniff
4. **Cookies sécurisés** — `SESSION_COOKIE_SECURE` et `CSRF_COOKIE_SECURE` activés par défaut
5. **Nginx** → `server_tokens off` (pas de version divulguée)
6. **Timeouts** sur tous les appels inter-services (3 secondes par défaut)

### 16.3 Django REST Framework — Rappels

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

### 16.4 Conventions de Code

- **Pas de trailing slash** dans les URLs
- **Noms de tables explicites** via `db_table` dans `Meta`
- **`update_fields`** dans `save()` pour optimiser les requêtes SQL
- **`filter().first()`** plutôt que `get()` pour éviter les exceptions non contrôlées
- **Codes HTTP sémantiques** : 200, 201, 204, 400, 404, 503

---

## 17. Glossaire

| Terme                    | Définition                                                                                                                         |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| **API REST**             | Interface de programmation utilisant les méthodes HTTP (GET, POST, PUT, PATCH, DELETE) sur des ressources identifiées par des URLs |
| **CRUD**                 | Create, Read, Update, Delete — les quatre opérations de base sur les données                                                       |
| **Django ORM**           | Object-Relational Mapping — couche d'abstraction qui permet de manipuler la BDD via des objets Python                              |
| **DRF**                  | Django REST Framework — bibliothèque pour construire des APIs REST avec Django                                                     |
| **FK (Foreign Key)**     | Clé étrangère — référence vers une autre entité                                                                                    |
| **Gunicorn**             | Green Unicorn — serveur WSGI (Web Server Gateway Interface) en production pour Python                                              |
| **Idempotent**           | Une opération qui, exécutée plusieurs fois, produit le même résultat qu'une seule exécution                                        |
| **Microservice**         | Service indépendant avec sa propre BDD, communiquant via des API                                                                   |
| **Migration**            | Fichier Python décrivant les changements de schéma de BDD (géré par Django)                                                        |
| **Nginx**                | Serveur web/reverse proxy performant                                                                                               |
| **OpenAPI**              | Standard de description d'APIs REST (anciennement Swagger)                                                                         |
| **Probe (Health/Ready)** | Endpoint utilisé par un orchestrateur pour vérifier l'état d'un service                                                            |
| **Sérialiseur**          | Composant qui convertit des données entre format JSON et objets Python                                                             |
| **WSGI**                 | Web Server Gateway Interface — standard Python pour communiquer entre un serveur web et une application                            |
| **12-Factor App**        | Méthodologie de développement de services cloud-natifs (configuration via env vars, etc.)                                          |

---

> **Document rédigé dans le cadre du projet Al-Mizan — Module Marchés Publics**
> **Service :** Contrats | **Port par défaut :** 18085 | **Version API :** 1.0.0
