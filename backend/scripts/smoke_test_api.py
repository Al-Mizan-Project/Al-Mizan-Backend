#!/usr/bin/env python
import io
import os
import re
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import django
import requests

BASE_DIR = Path(__file__).resolve().parents[1]
for path in (BASE_DIR, BASE_DIR / "services"):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.urls import Resolver404, URLPattern, URLResolver, get_resolver, resolve
from django.utils import timezone

from acteurs_service.models import Membre, OperateurEconomique, Organisation, Tutelle
from appels_service.models import AppelOffres, DocumentsAppel
from apps.recours.infrastructure.models.document_recours_model import DocumentRecoursModel
from apps.recours.infrastructure.models.recours_model import RecoursModel
from auth_service.models import Permission, PermissionRole, Role, Utilisateur
from auth_service.serializers import store_password_reset_token
from contractant_service.models import (
    CommissionEvaluation as ContractantCommissionEvaluation,
    CommissionExterne,
    CommissionInterne,
    MembresCommissionEvaluation as ContractantMembresCommissionEvaluation,
    MembresCommissionInterne,
    ServiceContractant,
)
from contrats_service.models import Contrat, DocumentContrat, Validation
from documents_service.models import Document
from evaluations_service.models import ComissionEvaluation as EvaluationCommission
from evaluations_service.models import Evaluation, MembresCommissionEvaluation as EvaluationCommissionMember
from ia_service.models import DetectionAnomalieIA
from ledger.models import AuditLog, OutboxEvent
from notifications_service.models import Notification
from readstore.models import AuditLogRead
from soumissions_app.models import Soumission


BASE_URL = os.getenv("BASE_URL", "http://nginx").rstrip("/")
TIMEOUT = int(os.getenv("SMOKE_TIMEOUT", "60"))
PREFIX = f"smoke-{uuid.uuid4().hex[:6]}"
NOW = timezone.now()


class SmokeFailure(Exception):
    pass


def log(message):
    print(message, flush=True)


def fail(message):
    raise SmokeFailure(message)


class ApiSmokeRunner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.tokens = {}
        self.ids = {}
        self.covered_methods = {}

    def url(self, path):
        return f"{BASE_URL}/{path.lstrip('/')}"

    def wait_for_api(self):
        for attempt in range(60):
            try:
                response = self.session.get(self.url("/health"), timeout=5)
                if response.status_code == 200:
                    log("API health check passed")
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        fail("API did not become healthy in time")

    def request(self, method, path, expected, token=None, **kwargs):
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.session.request(
            method=method,
            url=self.url(path),
            headers=headers,
            timeout=TIMEOUT,
            **kwargs,
        )
        if response.status_code not in expected:
            body = response.text[:1000]
            fail(f"{method} {path} -> {response.status_code}, expected {sorted(expected)}\n{body}")
        self.record_coverage(method, path)
        return response

    def json(self, method, path, expected, token=None, **kwargs):
        response = self.request(method, path, expected, token=token, **kwargs)
        if not response.content:
            return None
        return response.json()

    def reset_database(self):
        default_tables = [
            DocumentContrat._meta.db_table,
            Contrat._meta.db_table,
            Validation._meta.db_table,
            Evaluation._meta.db_table,
            EvaluationCommissionMember._meta.db_table,
            EvaluationCommission._meta.db_table,
            Soumission._meta.db_table,
            DocumentsAppel._meta.db_table,
            AppelOffres._meta.db_table,
            ContractantMembresCommissionEvaluation._meta.db_table,
            MembresCommissionInterne._meta.db_table,
            ContractantCommissionEvaluation._meta.db_table,
            CommissionInterne._meta.db_table,
            CommissionExterne._meta.db_table,
            ServiceContractant._meta.db_table,
            Notification._meta.db_table,
            DetectionAnomalieIA._meta.db_table,
            DocumentRecoursModel._meta.db_table,
            RecoursModel._meta.db_table,
            Document._meta.db_table,
            Utilisateur._meta.db_table,
            PermissionRole._meta.db_table,
            Permission._meta.db_table,
            Role._meta.db_table,
            Membre._meta.db_table,
            OperateurEconomique._meta.db_table,
            Organisation._meta.db_table,
            Tutelle._meta.db_table,
            "django_session",
        ]
        ledger_tables = [
            OutboxEvent._meta.db_table,
            AuditLog._meta.db_table,
        ]
        read_tables = [
            AuditLogRead._meta.db_table,
        ]

        self._truncate_tables("default", default_tables)
        self._truncate_tables("ledger", ledger_tables)
        self._truncate_tables("read", read_tables)
        cache.clear()
        log("Database and cache reset")

    def _truncate_tables(self, alias, tables):
        connection = connections[alias]
        existing_tables = set(connection.introspection.table_names())
        available_tables = [table for table in tables if table in existing_tables]
        if not available_tables:
            return
        quoted = ", ".join(connection.ops.quote_name(table) for table in available_tables)
        with connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")

    def seed_admin(self):
        admin_role = Role.objects.create(nom_role="admin")
        admin_user = Utilisateur(id_role=admin_role, id_membre=0, email=f"{PREFIX}-admin@example.com")
        admin_user.set_password("AdminPassword123!")
        admin_user.save()
        self.ids["admin_user_id"] = admin_user.id_utilisateur
        self.ids["admin_role_id"] = admin_role.id_role
        log("Seeded admin user")

    def auth_setup(self):
        admin_login = self.json(
            "POST",
            "/auth/login",
            {200},
            json={"email": f"{PREFIX}-admin@example.com", "password": "AdminPassword123!"},
        )
        self.tokens["admin_access"] = admin_login["access"]
        self.tokens["admin_refresh"] = admin_login["refresh"]

        permission_a = self.json(
            "POST",
            "/permissions",
            {201},
            token=self.tokens["admin_access"],
            json={"nom_permission": "perm_a"},
        )
        permission_b = self.json(
            "POST",
            "/permissions",
            {201},
            token=self.tokens["admin_access"],
            json={"nom_permission": "perm_b"},
        )
        permission_delete = self.json(
            "POST",
            "/permissions",
            {201},
            token=self.tokens["admin_access"],
            json={"nom_permission": "perm_del"},
        )
        self.ids["permission_id"] = permission_a["id_permission"]
        self.ids["permission_b_id"] = permission_b["id_permission"]
        self.ids["permission_delete_id"] = permission_delete["id_permission"]

        role_main = self.json(
            "POST",
            "/roles",
            {201},
            token=self.tokens["admin_access"],
            json={"nom_role": "manager"},
        )
        role_delete = self.json(
            "POST",
            "/roles",
            {201},
            token=self.tokens["admin_access"],
            json={"nom_role": "temp_role"},
        )
        self.ids["role_id"] = role_main["id_role"]
        self.ids["role_delete_id"] = role_delete["id_role"]

        self.json("GET", "/permissions", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/permissions/{self.ids['permission_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"nom_permission": "perm_a1"},
        )
        self.json("GET", f"/permissions/{self.ids['permission_id']}", {200}, token=self.tokens["admin_access"])
        self.request("DELETE", f"/permissions/{self.ids['permission_delete_id']}", {204}, token=self.tokens["admin_access"])

        self.json("GET", "/roles", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/roles/{self.ids['role_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PUT",
            f"/roles/{self.ids['role_id']}/permissions",
            {200},
            token=self.tokens["admin_access"],
            json={"permission_ids": [self.ids["permission_id"]]},
        )
        self.json("GET", f"/roles/{self.ids['role_id']}/permissions", {200}, token=self.tokens["admin_access"])
        self.request(
            "POST",
            f"/roles/{self.ids['role_id']}/permissions/{self.ids['permission_b_id']}",
            {201},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/roles/{self.ids['role_id']}/permissions/{self.ids['permission_b_id']}",
            {204},
            token=self.tokens["admin_access"],
        )

    def acteurs_setup(self):
        organisation = self.json(
            "POST",
            "/organisations",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nom_officiel": "OrgMain",
                "adresse_siege": "Alger",
                "email_contact": f"{PREFIX}-org@example.com",
                "type_entite": "publique",
            },
        )
        organisation_delete = self.json(
            "POST",
            "/organisations",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nom_officiel": "OrgTemp",
                "adresse_siege": "Oran",
                "email_contact": f"{PREFIX}-org2@example.com",
                "type_entite": "publique",
            },
        )
        acteurs_service_org = self.json(
            "POST",
            "/acteurs/services-contractants",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nom_officiel": "OrgSC",
                "adresse_siege": "Setif",
                "email_contact": f"{PREFIX}-sc@example.com",
                "type_entite": "service_contractant",
            },
        )
        self.ids["organisation_id"] = organisation["id_organisation"]
        self.ids["organisation_delete_id"] = organisation_delete["id_organisation"]
        self.ids["acteurs_service_contractant_id"] = acteurs_service_org["id_organisation"]

        self.json("GET", "/organisations", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/organisations/{self.ids['organisation_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/organisations/{self.ids['organisation_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"adresse_siege": "Blida"},
        )
        self.request("DELETE", f"/organisations/{self.ids['organisation_delete_id']}", {204}, token=self.tokens["admin_access"])

        membre_main = self.json(
            "POST",
            "/membres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_organisation": self.ids["organisation_id"],
                "prenom": "Ali",
                "nom": "Main",
                "telephone": "0550000000",
                "fonction": "Gestionnaire",
            },
        )
        membre_service = self.json(
            "POST",
            "/membres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_organisation": self.ids["acteurs_service_contractant_id"],
                "prenom": "Sara",
                "nom": "Service",
                "telephone": "0550000001",
                "fonction": "Agent",
            },
        )
        membre_delete = self.json(
            "POST",
            "/membres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_organisation": self.ids["organisation_id"],
                "prenom": "Temp",
                "nom": "Delete",
                "telephone": "0550000002",
                "fonction": "Temp",
            },
        )
        self.ids["membre_id"] = membre_main["id_membre"]
        self.ids["service_membre_id"] = membre_service["id_membre"]
        self.ids["membre_delete_id"] = membre_delete["id_membre"]

        self.json("GET", "/membres", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/membres/{self.ids['membre_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/membres/{self.ids['membre_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"telephone": "0660000000"},
        )
        self.request("DELETE", f"/membres/{self.ids['membre_delete_id']}", {204}, token=self.tokens["admin_access"])
        self.json("GET", f"/organisations/{self.ids['organisation_id']}/membres", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/acteurs/services-contractants/{self.ids['acteurs_service_contractant_id']}/membres",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json("GET", "/acteurs/services-contractants", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/acteurs/services-contractants/{self.ids['acteurs_service_contractant_id']}",
            {200},
            token=self.tokens["admin_access"],
        )

        operateur = self.json(
            "POST",
            "/operateurs-economiques",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nif": "123456789012345",
                "registre_commerce_num": "RC-001",
                "casnos_vrt": "CAS-001",
                "cnas_vrt": "CNA-001",
                "rib_bancaire": "00799999000000000001",
            },
        )
        operateur_delete = self.json(
            "POST",
            "/operateurs-economiques",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nif": "999999999999999",
                "registre_commerce_num": "RC-999",
                "casnos_vrt": "CAS-999",
                "cnas_vrt": "CNA-999",
                "rib_bancaire": "00799999000000000099",
            },
        )
        self.ids["operateur_id"] = operateur["id_operateur_economique"]
        self.ids["operateur_delete_id"] = operateur_delete["id_operateur_economique"]
        self.ids["operateur_nif"] = operateur["nif"]

        self.json("GET", "/operateurs-economiques", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/operateurs-economiques/{self.ids['operateur_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/operateurs-economiques/{self.ids['operateur_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"rib_bancaire": "00799999000000000077"},
        )
        self.json(
            "GET",
            f"/operateurs-economiques/by-nif/{self.ids['operateur_nif']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/operateurs-economiques/{self.ids['operateur_delete_id']}",
            {204},
            token=self.tokens["admin_access"],
        )

        tutelle = self.json(
            "POST",
            "/tutelles",
            {201},
            token=self.tokens["admin_access"],
            json={"nom_tutelle": "TutelleA", "identite_autorite": "Autorite A"},
        )
        tutelle_delete = self.json(
            "POST",
            "/tutelles",
            {201},
            token=self.tokens["admin_access"],
            json={"nom_tutelle": "TutelleB", "identite_autorite": "Autorite B"},
        )
        self.ids["tutelle_id"] = tutelle["id_tutelle"]
        self.ids["tutelle_delete_id"] = tutelle_delete["id_tutelle"]

        self.json("GET", "/tutelles", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/tutelles/{self.ids['tutelle_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/tutelles/{self.ids['tutelle_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"identite_autorite": "Autorite A+"},
        )
        self.request("DELETE", f"/tutelles/{self.ids['tutelle_delete_id']}", {204}, token=self.tokens["admin_access"])

    def user_setup(self):
        user_main = self.json(
            "POST",
            "/users",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_role": self.ids["role_id"],
                "id_membre": self.ids["membre_id"],
                "email": f"{PREFIX}-user@example.com",
                "password": "UserPassword123!",
            },
        )
        user_delete = self.json(
            "POST",
            "/users",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_role": self.ids["role_delete_id"],
                "id_membre": self.ids["service_membre_id"],
                "email": f"{PREFIX}-delete@example.com",
                "password": "DeletePassword123!",
            },
        )
        self.ids["user_id"] = user_main["id_utilisateur"]
        self.ids["user_delete_id"] = user_delete["id_utilisateur"]

        self.json("GET", "/users", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/users/{self.ids['user_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/users/{self.ids['user_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"email": f"{PREFIX}-user2@example.com"},
        )
        self.json(
            "PATCH",
            f"/users/{self.ids['user_id']}/role",
            {200},
            token=self.tokens["admin_access"],
            json={"id_role": self.ids["role_id"]},
        )
        self.json("GET", f"/users/{self.ids['user_id']}/permissions", {200}, token=self.tokens["admin_access"])

        user_login = self.json(
            "POST",
            "/auth/login",
            {200},
            json={"email": f"{PREFIX}-user2@example.com", "password": "UserPassword123!"},
        )
        self.tokens["user_access"] = user_login["access"]
        self.tokens["user_refresh"] = user_login["refresh"]

        self.request(
            "POST",
            "/auth/change-password",
            {204},
            token=self.tokens["user_access"],
            json={"old_password": "UserPassword123!", "new_password": "UserPassword456!"},
        )
        self.json(
            "POST",
            "/auth/forgot-password",
            {200},
            json={"email": f"{PREFIX}-user2@example.com"},
        )
        reset_token = f"{PREFIX}-reset-token"
        store_password_reset_token(reset_token, self.ids["user_id"])
        self.request(
            "POST",
            "/auth/reset-password",
            {204},
            json={"token": reset_token, "new_password": "UserPassword789!"},
        )
        refresh_payload = self.json(
            "POST",
            "/auth/refresh",
            {200},
            json={"refresh": self.tokens["user_refresh"]},
        )
        self.tokens["user_access"] = refresh_payload["access"]
        self.request("POST", "/auth/logout", {204}, json={"refresh": self.tokens["user_refresh"]})

        self.request("DELETE", f"/users/{self.ids['user_delete_id']}", {204}, token=self.tokens["admin_access"])
        self.request("DELETE", f"/roles/{self.ids['role_delete_id']}", {204}, token=self.tokens["admin_access"])

    def contractant_setup(self):
        service_main = self.json(
            "POST",
            "/services-contractants",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_tutelle": self.ids["tutelle_id"],
                "categorie": "centrale",
                "code_ordonnateur": "ORD-001",
            },
        )
        service_delete = self.json(
            "POST",
            "/services-contractants",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_tutelle": self.ids["tutelle_id"],
                "categorie": "temporaire",
                "code_ordonnateur": "ORD-DELETE",
            },
        )
        self.ids["service_id"] = service_main["id_service"]
        self.ids["service_delete_id"] = service_delete["id_service"]

        self.json("GET", f"/services-contractants/{self.ids['service_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/services-contractants/{self.ids['service_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"categorie": "centrale-updated"},
        )

        commission_eval = self.json(
            "POST",
            "/commissions-evaluation",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service": self.ids["service_id"],
                "nom_comission": "CE Main",
                "categorie": "technique",
            },
        )
        commission_eval_delete = self.json(
            "POST",
            "/commissions-evaluation",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service": self.ids["service_id"],
                "nom_comission": "CE Temp",
                "categorie": "administrative",
            },
        )
        self.ids["commission_id"] = commission_eval["id_comission"]
        self.ids["commission_delete_id"] = commission_eval_delete["id_comission"]

        self.json("GET", "/commissions-evaluation", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/commissions-evaluation/{self.ids['commission_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PATCH",
            f"/commissions-evaluation/{self.ids['commission_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"categorie": "finance"},
        )
        self.request(
            "POST",
            f"/commissions-evaluation/{self.ids['commission_id']}/membres/{self.ids['membre_id']}",
            {201},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/commissions-evaluation/{self.ids['commission_id']}/membres",
            {200},
            token=self.tokens["admin_access"],
        )

        commission_interne = self.json(
            "POST",
            "/commissions-internes",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service": self.ids["service_id"],
                "nom_comission": "CI Main",
                "type_comission": "adhoc",
            },
        )
        commission_interne_delete = self.json(
            "POST",
            "/commissions-internes",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service": self.ids["service_id"],
                "nom_comission": "CI Temp",
                "type_comission": "parmanante",
            },
        )
        self.ids["commission_interne_id"] = commission_interne["id_comission_interne"]
        self.ids["commission_interne_delete_id"] = commission_interne_delete["id_comission_interne"]

        self.json("GET", "/commissions-internes", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/commissions-internes/{self.ids['commission_interne_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PATCH",
            f"/commissions-internes/{self.ids['commission_interne_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"type_comission": "parmanante"},
        )
        self.request(
            "POST",
            f"/commissions-internes/{self.ids['commission_interne_id']}/membres/{self.ids['service_membre_id']}",
            {201},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/commissions-internes/{self.ids['commission_interne_id']}/membres",
            {200},
            token=self.tokens["admin_access"],
        )

        commission_externe = self.json(
            "POST",
            "/commissions-externes",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nom_comission": "CExt Main",
                "niveau_competance": "Communale",
                "seuils_competence_financiere": "1000000",
            },
        )
        commission_externe_delete = self.json(
            "POST",
            "/commissions-externes",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nom_comission": "CExt Temp",
                "niveau_competance": "de Wilaya",
                "seuils_competence_financiere": "2000000",
            },
        )
        self.ids["commission_externe_id"] = commission_externe["id_comission_externe"]
        self.ids["commission_externe_delete_id"] = commission_externe_delete["id_comission_externe"]

        self.json("GET", "/commissions-externes", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/commissions-externes/{self.ids['commission_externe_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PATCH",
            f"/commissions-externes/{self.ids['commission_externe_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"seuils_competence_financiere": "3000000"},
        )

        self.json(
            "GET",
            f"/services-contractants/{self.ids['service_id']}/membres",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/services-contractants/{self.ids['service_id']}/commissions",
            {200},
            token=self.tokens["admin_access"],
        )

        self.request(
            "DELETE",
            f"/commissions-evaluation/{self.ids['commission_delete_id']}",
            {204},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/commissions-internes/{self.ids['commission_interne_delete_id']}",
            {204},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/commissions-externes/{self.ids['commission_externe_delete_id']}",
            {204},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/services-contractants/{self.ids['service_delete_id']}",
            {204},
            token=self.tokens["admin_access"],
        )

        self.ids["evaluation_commission_id"] = EvaluationCommission.objects.create(
            id_service=self.ids["service_id"],
            nom_comission="Eval Main",
            categorie="technique",
        ).id_comission

    def documents_setup(self):
        main_doc = self.json(
            "POST",
            "/api/documents/",
            {201},
            token=self.tokens["admin_access"],
            files={"file": ("rc.pdf", b"registre de commerce", "application/pdf")},
            data={"related_type": "soumission", "is_encrypted": "false"},
        )
        bulk_response = self.request(
            "POST",
            "/api/documents/",
            {201, 207},
            token=self.tokens["admin_access"],
            files=[
                ("files", ("extra.pdf", b"extra document", "application/pdf")),
                ("files", ("delete.pdf", b"delete document", "application/pdf")),
            ],
            data={"related_type": "appel", "is_encrypted": "false"},
        )
        bulk_docs = bulk_response.json()
        if isinstance(bulk_docs, dict):
            bulk_docs = bulk_docs.get("documents", [])

        self.ids["document_id"] = main_doc["id_document"]
        self.ids["document_extra_id"] = bulk_docs[0]["id_document"]
        self.ids["document_delete_id"] = bulk_docs[1]["id_document"]

        self.json("GET", "/documents", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/documents/{self.ids['document_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/documents/{self.ids['document_id']}/download-url",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/api/documents/search/?ids={self.ids['document_id']},{self.ids['document_extra_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request(
            "GET",
            f"/api/documents/{self.ids['document_id']}/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PATCH",
            f"/api/documents/{self.ids['document_id']}/ia-metadata/",
            {200},
            token=self.tokens["admin_access"],
            json={"ia_verif_statut": "VALID", "ia_verif_details": '{"status":"ok"}'},
        )
        self.request(
            "GET",
            f"/api/documents/zip/?ids={self.ids['document_id']},{self.ids['document_extra_id']}",
            {200},
            token=self.tokens["admin_access"],
        )

    def appels_setup(self):
        base_payload = {
            "id_service_contractant": self.ids["service_id"],
            "description": "Smoke appel",
            "type_procedure": "ouverte",
            "montant_estime": "100000.00",
            "date_publication": NOW.isoformat(),
            "date_limite_soumission": (NOW + timedelta(days=3)).isoformat(),
            "date_ouverture_plis": NOW.isoformat(),
            "poids_technique": 60,
            "poids_financier": 40,
        }
        appel_main = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={**base_payload, "reference": f"{PREFIX}-AO-1", "titre": "Appel Main"},
        )
        appel_cancel = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={**base_payload, "reference": f"{PREFIX}-AO-2", "titre": "Appel Cancel"},
        )
        appel_withdraw = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={**base_payload, "reference": f"{PREFIX}-AO-3", "titre": "Appel Withdraw"},
        )
        self.ids["appel_id"] = appel_main["id_appel_offres"]
        self.ids["appel_cancel_id"] = appel_cancel["id_appel_offres"]
        self.ids["appel_withdraw_id"] = appel_withdraw["id_appel_offres"]

        self.json("GET", "/appels-offres", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/appels-offres/{self.ids['appel_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/appels-offres/{self.ids['appel_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"titre": "Appel Main Updated"},
        )

        self.request(
            "POST",
            f"/appels-offres/{self.ids['appel_id']}/documents/{self.ids['document_id']}",
            {201},
            token=self.tokens["admin_access"],
        )
        self.request(
            "POST",
            f"/appels-offres/{self.ids['appel_cancel_id']}/documents/{self.ids['document_extra_id']}",
            {201},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/appels-offres/{self.ids['appel_id']}/documents",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/appels-offres/{self.ids['appel_cancel_id']}/documents/{self.ids['document_extra_id']}",
            {204},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/services-contractants/{self.ids['service_id']}/appels-offres",
            {200},
            token=self.tokens["admin_access"],
        )

        self.json("POST", f"/appels-offres/{self.ids['appel_id']}/publier", {200}, token=self.tokens["admin_access"])
        self.json(
            "POST",
            f"/appels-offres/{self.ids['appel_id']}/cloturer-depot",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json("POST", f"/appels-offres/{self.ids['appel_id']}/ouvrir-plis", {200}, token=self.tokens["admin_access"])
        self.json(
            "POST",
            f"/appels-offres/{self.ids['appel_cancel_id']}/publier",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/appels-offres/{self.ids['appel_cancel_id']}/annuler",
            {200},
            token=self.tokens["admin_access"],
        )

    def soumissions_and_evaluations_setup(self):
        main_soumission = self.json(
            "POST",
            "/api/soumissions/",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": self.ids["appel_id"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_id']}.pdf.enc",
                "cle_dechiffrement_hash": "not-a-real-key",
                "document_ids": [self.ids["document_id"]],
            },
        )
        withdraw_soumission = self.json(
            "POST",
            "/api/soumissions/",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": self.ids["appel_withdraw_id"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_extra_id']}.pdf.enc",
                "cle_dechiffrement_hash": "withdraw-key",
                "document_ids": [self.ids["document_extra_id"]],
            },
        )
        recours_soumission = self.json(
            "POST",
            "/api/soumissions/",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": self.ids["appel_withdraw_id"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_id']}.pdf.enc",
                "cle_dechiffrement_hash": "recours-key",
                "document_ids": [self.ids["document_id"]],
            },
        )
        delete_recours_soumission = self.json(
            "POST",
            "/api/soumissions/",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": self.ids["appel_withdraw_id"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_id']}.pdf.enc",
                "cle_dechiffrement_hash": "recours-delete-key",
                "document_ids": [self.ids["document_id"]],
            },
        )
        self.ids["soumission_id"] = main_soumission["id"]
        self.ids["soumission_withdraw_id"] = withdraw_soumission["id"]
        self.ids["soumission_recours_id"] = recours_soumission["id"]
        self.ids["soumission_recours_delete_id"] = delete_recours_soumission["id"]

        self.json("GET", "/api/soumissions/", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/api/soumissions/{self.ids['soumission_id']}/", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/api/soumissions/{self.ids['soumission_id']}/",
            {200},
            token=self.tokens["admin_access"],
            json={"conformite_statut": "A_REVOIR"},
        )
        self.json(
            "POST",
            f"/soumissions/{self.ids['appel_id']}/open-bids",
            {200},
            token=self.tokens["admin_access"],
        )
        evaluation_created = self.json(
            "POST",
            f"/soumissions/{self.ids['soumission_id']}/evaluate",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_comission": self.ids["evaluation_commission_id"],
                "id_utilisateur": self.ids["admin_user_id"],
                "type": "technique",
                "note": 88,
                "commentaire": "Smoke evaluation",
            },
        )
        self.ids["evaluation_id"] = evaluation_created["id_evalution"]
        self.json(
            "GET",
            f"/soumissions/{self.ids['soumission_id']}/evaluate",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PATCH",
            f"/soumissions/{self.ids['soumission_id']}/conformite",
            {200},
            token=self.tokens["admin_access"],
            json={"conformite_statut": "CONFORME", "conformite_rapport": {"ok": True}},
        )
        self.json(
            "POST",
            f"/soumissions/{self.ids['soumission_id']}/terminer-evaluation",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/soumissions/{self.ids['soumission_withdraw_id']}/retirer",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/appels-offres/{self.ids['appel_id']}/soumissions",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/operateurs-economiques/{self.ids['operateur_id']}/soumissions",
            {200},
            token=self.tokens["admin_access"],
        )

        extra_evaluation = self.json(
            "POST",
            "/evaluations",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_comission": self.ids["evaluation_commission_id"],
                "id_soumission": self.ids["soumission_id"],
                "id_utilisateur": self.ids["user_id"],
                "type": "administrative",
                "note": 75,
                "commentaire": "Secondary evaluation",
            },
        )
        self.ids["evaluation_delete_id"] = extra_evaluation["id_evalution"]
        self.json("GET", "/evaluations", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/evaluations/{self.ids['evaluation_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/evaluations/{self.ids['evaluation_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"commentaire": "Updated evaluation"},
        )
        self.json(
            "GET",
            f"/soumissions/{self.ids['soumission_id']}/evaluations",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/appels-offres/{self.ids['appel_id']}/evaluations?id_comission={self.ids['evaluation_commission_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/appels-offres/{self.ids['appel_id']}/calculer-classement",
            {200},
            token=self.tokens["admin_access"],
            json={"id_comission": self.ids["evaluation_commission_id"]},
        )
        self.json(
            "GET",
            f"/appels-offres/{self.ids['appel_id']}/classement?id_comission={self.ids['evaluation_commission_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/appels-offres/{self.ids['appel_id']}/valider-notes",
            {200},
            token=self.tokens["admin_access"],
            json={"id_comission": self.ids["evaluation_commission_id"]},
        )
        self.request("DELETE", f"/evaluations/{self.ids['evaluation_delete_id']}", {204}, token=self.tokens["admin_access"])

    def contrats_setup(self):
        validation_main = self.json(
            "POST",
            "/validations",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_utilisateur": self.ids["user_id"],
                "id_soumission": self.ids["soumission_id"],
                "type": "interne",
                "commentaire": "Validation main",
            },
        )
        validation_reject = self.json(
            "POST",
            "/validations",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_utilisateur": self.ids["user_id"],
                "id_soumission": self.ids["soumission_withdraw_id"],
                "type": "externe",
                "commentaire": "Validation reject",
            },
        )
        validation_delete = self.json(
            "POST",
            "/validations",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_utilisateur": self.ids["user_id"],
                "id_soumission": self.ids["soumission_recours_delete_id"],
                "type": "tutelle",
                "commentaire": "Validation delete",
            },
        )
        self.ids["validation_id"] = validation_main["id_validation"]
        self.ids["validation_reject_id"] = validation_reject["id_validation"]
        self.ids["validation_delete_id"] = validation_delete["id_validation"]

        self.json("GET", "/validations", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/validations/{self.ids['validation_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/validations/{self.ids['validation_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"commentaire": "Validation updated"},
        )
        self.json(
            "POST",
            f"/validations/{self.ids['validation_id']}/approuver",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/validations/{self.ids['validation_reject_id']}/rejeter",
            {200},
            token=self.tokens["admin_access"],
            json={"commentaire": "Rejected"},
        )
        self.request("DELETE", f"/validations/{self.ids['validation_delete_id']}", {204}, token=self.tokens["admin_access"])

        contrat_main = self.json(
            "POST",
            "/contrats",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_soumission": self.ids["soumission_id"],
                "id_service_contractants": self.ids["service_id"],
                "numero_contrat": f"{PREFIX}-CTR-1",
                "statut": "brouillon",
            },
        )
        contrat_delete = self.json(
            "POST",
            "/contrats",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_soumission": self.ids["soumission_withdraw_id"],
                "id_service_contractants": self.ids["service_id"],
                "numero_contrat": f"{PREFIX}-CTR-2",
                "statut": "brouillon",
            },
        )
        self.ids["contrat_id"] = contrat_main["id_contrat"]
        self.ids["contrat_delete_id"] = contrat_delete["id_contrat"]

        self.json("GET", "/contrats", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/contrats/{self.ids['contrat_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/contrats/{self.ids['contrat_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"statut": "pret"},
        )
        self.json(
            "POST",
            f"/contrats/{self.ids['contrat_id']}/signer",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request(
            "POST",
            f"/contrats/{self.ids['contrat_id']}/documents/{self.ids['document_id']}",
            {200, 201},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/contrats/{self.ids['contrat_id']}/documents",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/contrats/{self.ids['contrat_id']}/documents/{self.ids['document_id']}",
            {204},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/soumissions/{self.ids['soumission_id']}/contrat",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request("DELETE", f"/contrats/{self.ids['contrat_delete_id']}", {204}, token=self.tokens["admin_access"])

    def notifications_setup(self):
        notification_main = self.json(
            "POST",
            "/notifications",
            {201},
            token=self.tokens["admin_access"],
            json={
                "utilisateur_id": self.ids["user_id"],
                "type_notification": "alerte",
                "titre": "Notif main",
                "message": "Main notification",
                "priorite": "haute",
                "categorie": "general",
                "entite_liee_type": "soumission",
                "entite_liee_id": self.ids["soumission_id"],
                "statut": "cree",
            },
        )
        notification_delete = self.json(
            "POST",
            "/notifications",
            {201},
            token=self.tokens["admin_access"],
            json={
                "utilisateur_id": self.ids["user_id"],
                "type_notification": "info",
                "titre": "Notif delete",
                "message": "Delete notification",
                "priorite": "basse",
                "categorie": "general",
                "entite_liee_type": "contrat",
                "entite_liee_id": self.ids["contrat_id"],
                "statut": "cree",
            },
        )
        self.ids["notification_id"] = notification_main["id"]
        self.ids["notification_delete_id"] = notification_delete["id"]

        self.json("GET", "/notifications", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/notifications/{self.ids['notification_id']}", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/notifications/{self.ids['notification_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"titre": "Notif main updated"},
        )
        self.json(
            "GET",
            f"/users/{self.ids['user_id']}/notifications",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/notifications/{self.ids['notification_id']}/envoyer",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/notifications/{self.ids['notification_id']}/marquer-lu",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            "/notifications/envoi-masse",
            {201, 207},
            token=self.tokens["admin_access"],
            json={
                "notifications": [
                    {
                        "utilisateur_id": self.ids["user_id"],
                        "type_notification": "batch",
                        "titre": "Batch 1",
                        "message": "Batch notification 1",
                        "priorite": "moyenne",
                        "categorie": "batch",
                        "entite_liee_type": "appel",
                        "entite_liee_id": self.ids["appel_id"],
                    },
                    {
                        "utilisateur_id": self.ids["user_id"],
                        "type_notification": "batch",
                        "titre": "Batch 2",
                        "message": "Batch notification 2",
                        "priorite": "moyenne",
                        "categorie": "batch",
                        "entite_liee_type": "appel",
                        "entite_liee_id": self.ids["appel_id"],
                    },
                ]
            },
        )
        self.json(
            "POST",
            f"/users/{self.ids['user_id']}/notifications/marquer-tout-lu",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request(
            "DELETE",
            f"/notifications/{self.ids['notification_delete_id']}",
            {204},
            token=self.tokens["admin_access"],
        )

    def ia_setup(self):
        detect_manual = self.json(
            "POST",
            "/ia/anomalies/detecter",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": self.ids["appel_id"],
                "montant_estime": "100000.00",
                "soumissions": [
                    {"id_soumission": self.ids["soumission_id"], "montant_financier": 95000, "documents_hash": "abc"},
                    {"id_soumission": self.ids["soumission_withdraw_id"], "montant_financier": 95100, "documents_hash": "abc"},
                ],
            },
        )
        self.json(
            "POST",
            "/ia/anomalies/detecter-auto",
            {200, 201},
            token=self.tokens["admin_access"],
            json={"id_appel_offre": self.ids["appel_id"], "montant_estime": "100000.00"},
        )
        anomalies = detect_manual.get("items", [])
        if anomalies:
            self.ids["anomalie_id"] = anomalies[0]["id_detection_anomalie_ia"]
        else:
            anomaly = DetectionAnomalieIA.objects.create(
                id_appel_offre=self.ids["appel_id"],
                id_soumission=self.ids["soumission_id"],
                type_anomalie="SIMILARITE_PRIX",
                niveau_severite="MOYEN",
                score_confiance="75.00",
                details="Fallback anomaly",
                statut_examen="A_REVOIR",
            )
            self.ids["anomalie_id"] = anomaly.id_detection_anomalie_ia

        self.json("GET", "/ia/anomalies", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/ia/anomalies/{self.ids['anomalie_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/ia/anomalies/appel/{self.ids['appel_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/ia/anomalies/appel/{self.ids['appel_id']}/summary",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/ia/anomalies/soumission/{self.ids['soumission_id']}",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PATCH",
            f"/ia/anomalies/{self.ids['anomalie_id']}/statut-examen",
            {200},
            token=self.tokens["admin_access"],
            json={"statut_examen": "EN_COURS", "commentaire_examen": "Checked"},
        )
        self.json(
            "POST",
            "/ia/saucissonnage/detecter",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service_contractant": self.ids["service_id"],
                "appels": [
                    {
                        "id_appel_offre": self.ids["appel_id"],
                        "id_service_contractant": self.ids["service_id"],
                        "titre": "Appel Main Updated",
                        "description": "Smoke appel",
                        "montant_estime": "100000.00",
                        "date_publication": NOW.date().isoformat(),
                        "type_procedure": "ouverte",
                    },
                    {
                        "id_appel_offre": self.ids["appel_cancel_id"],
                        "id_service_contractant": self.ids["service_id"],
                        "titre": "Appel Cancel",
                        "description": "Smoke appel",
                        "montant_estime": "99000.00",
                        "date_publication": NOW.date().isoformat(),
                        "type_procedure": "ouverte",
                    },
                ],
            },
        )
        self.json(
            "POST",
            "/ia/saucissonnage/detecter-auto",
            {200, 201},
            token=self.tokens["admin_access"],
            json={"id_service_contractant": self.ids["service_id"]},
        )
        self.json(
            "POST",
            f"/ia/conformite/verifier-soumission/{self.ids['soumission_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "required_documents": ["rc"],
                "provided_documents": [
                    {"id_document": self.ids["document_id"], "type_document": "rc", "is_valid": True}
                ],
            },
        )
        self.json(
            "POST",
            f"/ia/conformite/verifier-soumission-auto/{self.ids['soumission_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": self.ids["appel_id"],
                "provided_document_ids": [self.ids["document_id"]],
                "required_document_ids": [self.ids["document_id"]],
                "perform_ocr": False,
                "enforce_validity_checks": False,
            },
        )
        self.json(
            "POST",
            "/ia/cdc/rediger",
            {200},
            token=self.tokens["admin_access"],
            json={
                "besoin": "Acquisition de serveurs",
                "type_procedure": "ouverte",
                "contraintes": ["livraison rapide", "garantie"],
            },
        )
        self.json(
            "POST",
            "/ia/cdc/reviser",
            {200},
            token=self.tokens["admin_access"],
            json={"texte": "Ce cahier des charges doit etre revise et clarifie."},
        )

    def recours_setup(self):
        self.json(
            "PATCH",
            f"/soumissions/{self.ids['soumission_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"statut": "REJETEE"},
        )
        self.json(
            "PATCH",
            f"/soumissions/{self.ids['soumission_recours_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"statut": "REJETEE"},
        )
        self.json(
            "PATCH",
            f"/soumissions/{self.ids['soumission_recours_delete_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"statut": "REJETEE"},
        )

        recours_accept = self.json(
            "POST",
            "/api/recours/",
            {200, 201},
            token=self.tokens["admin_access"],
            json={
                "id_operateur_economique": self.ids["operateur_id"],
                "id_validation": self.ids["validation_id"],
                "id_soumission": self.ids["soumission_id"],
                "motif": "Motif accept",
            },
        )
        recours_reject = self.json(
            "POST",
            "/api/recours/",
            {200, 201},
            token=self.tokens["admin_access"],
            json={
                "id_operateur_economique": self.ids["operateur_id"],
                "id_validation": self.ids["validation_id"],
                "id_soumission": self.ids["soumission_recours_id"],
                "motif": "Motif reject",
            },
        )
        recours_delete = self.json(
            "POST",
            "/api/recours/",
            {200, 201},
            token=self.tokens["admin_access"],
            json={
                "id_operateur_economique": self.ids["operateur_id"],
                "id_validation": self.ids["validation_id"],
                "id_soumission": self.ids["soumission_recours_delete_id"],
                "motif": "Motif delete",
            },
        )
        self.ids["recours_id"] = recours_accept["id_recours"]
        self.ids["recours_reject_id"] = recours_reject["id_recours"]
        self.ids["recours_delete_id"] = recours_delete["id_recours"]

        self.json("GET", "/api/recours/", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/api/recours/{self.ids['recours_id']}/", {200}, token=self.tokens["admin_access"])
        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_id']}/instruire/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_id']}/decision/",
            {200},
            token=self.tokens["admin_access"],
            json={"decision": "Favorable", "traite_par": self.ids["admin_user_id"]},
        )
        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_id']}/accepter/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_id']}/cloturer/",
            {200},
            token=self.tokens["admin_access"],
        )

        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_reject_id']}/instruire/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_reject_id']}/decision/",
            {200},
            token=self.tokens["admin_access"],
            json={"decision": "Defavorable", "traite_par": self.ids["admin_user_id"]},
        )
        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_reject_id']}/rejeter/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "POST",
            f"/api/recours/{self.ids['recours_reject_id']}/cloturer/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request("DELETE", f"/api/recours/{self.ids['recours_delete_id']}/", {204}, token=self.tokens["admin_access"])

    def audit_setup(self):
        audit = self.json(
            "POST",
            "/journaux-audit/create/",
            {201},
            token=self.tokens["admin_access"],
            json={
                "utilisateur_id": self.ids["admin_user_id"],
                "action": "SMOKE_TEST",
                "entite_type": "smoke",
                "entite_id": 123,
                "details_action": {"status": "ok"},
            },
        )
        self.ids["log_id"] = audit["log_id"]
        self.ids["record_id"] = audit["log_id"]
        self.json("GET", "/journaux-audit/list/", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/journaux-audit/{self.ids['log_id']}/", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/journaux-audit/user/{self.ids['admin_user_id']}/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            "/journaux-audit/entity/smoke/123/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json("GET", "/journaux-audit/verifier-integrite/", {200}, token=self.tokens["admin_access"])
        self.json(
            "GET",
            f"/journaux-audit/verifier-integrite/record/{self.ids['record_id']}/",
            {200},
            token=self.tokens["admin_access"],
        )

    def route_coverage_extensions(self):
        self.json(
            "PUT",
            f"/users/{self.ids['user_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_role": self.ids["role_id"],
                "id_membre": self.ids["membre_id"],
                "email": f"{PREFIX}-user-put@example.com",
            },
        )
        self.json(
            "PATCH",
            f"/roles/{self.ids['role_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"nom_role": "manager-patch"},
        )
        self.json(
            "PUT",
            f"/roles/{self.ids['role_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"nom_role": "manager-final"},
        )
        self.json(
            "PUT",
            f"/permissions/{self.ids['permission_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"nom_permission": "perm_a_final"},
        )

        self.json(
            "PUT",
            f"/organisations/{self.ids['organisation_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "nom_officiel": "OrgMainFinal",
                "adresse_siege": "Tipaza",
                "email_contact": f"{PREFIX}-org-final@example.com",
                "type_entite": "publique",
            },
        )
        acteurs_temp = self.json(
            "POST",
            "/acteurs/services-contractants",
            {201},
            token=self.tokens["admin_access"],
            json={
                "nom_officiel": "OrgSC Temp",
                "adresse_siege": "Tizi",
                "email_contact": f"{PREFIX}-sc-temp@example.com",
                "type_entite": "service_contractant",
            },
        )
        acteurs_temp_id = acteurs_temp["id_organisation"]
        self.json(
            "PATCH",
            f"/acteurs/services-contractants/{acteurs_temp_id}",
            {200},
            token=self.tokens["admin_access"],
            json={"adresse_siege": "Tizi Updated"},
        )
        self.json(
            "PUT",
            f"/acteurs/services-contractants/{acteurs_temp_id}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "nom_officiel": "OrgSC Temp Final",
                "adresse_siege": "Tizi Final",
                "email_contact": f"{PREFIX}-sc-temp-final@example.com",
                "type_entite": "service_contractant",
            },
        )
        self.request(
            "DELETE",
            f"/acteurs/services-contractants/{acteurs_temp_id}",
            {204},
            token=self.tokens["admin_access"],
        )

        self.json(
            "PUT",
            f"/operateurs-economiques/{self.ids['operateur_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "nif": self.ids["operateur_nif"],
                "registre_commerce_num": "RC-001-PUT",
                "casnos_vrt": "CAS-001-PUT",
                "cnas_vrt": "CNA-001-PUT",
                "rib_bancaire": "00799999000000000111",
            },
        )
        self.json(
            "PUT",
            f"/membres/{self.ids['membre_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_organisation": self.ids["organisation_id"],
                "prenom": "Ali",
                "nom": "Main Final",
                "telephone": "0777000000",
                "fonction": "Gestionnaire Principal",
            },
        )
        self.json(
            "PUT",
            f"/tutelles/{self.ids['tutelle_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"nom_tutelle": "TutelleA-Final", "identite_autorite": "Autorite Finale"},
        )

        self.json(
            "PUT",
            f"/commissions-evaluation/{self.ids['commission_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_service": self.ids["service_id"],
                "nom_comission": "CE Main Final",
                "categorie": "conformite",
            },
        )
        self.request(
            "DELETE",
            f"/commissions-evaluation/{self.ids['commission_id']}/membres/{self.ids['membre_id']}",
            {204},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PUT",
            f"/commissions-internes/{self.ids['commission_interne_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_service": self.ids["service_id"],
                "nom_comission": "CI Main Final",
                "type_comission": "adhoc",
            },
        )
        self.request(
            "DELETE",
            f"/commissions-internes/{self.ids['commission_interne_id']}/membres/{self.ids['service_membre_id']}",
            {204},
            token=self.tokens["admin_access"],
        )
        self.json(
            "PUT",
            f"/services-contractants/{self.ids['service_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_tutelle": self.ids["tutelle_id"],
                "categorie": "centrale-finale",
                "code_ordonnateur": "ORD-001-FINAL",
            },
        )
        self.json(
            "PUT",
            f"/commissions-externes/{self.ids['commission_externe_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "nom_comission": "CExt Main Final",
                "niveau_competance": "Nationale",
                "seuils_competence_financiere": "5000000",
            },
        )

        self.json(
            "PUT",
            f"/appels-offres/{self.ids['appel_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_service_contractant": self.ids["service_id"],
                "reference": f"{PREFIX}-AO-1",
                "titre": "Appel Main Final",
                "description": "Smoke appel final",
                "type_procedure": "ouverte",
                "montant_estime": "120000.00",
                "date_publication": NOW.isoformat(),
                "date_limite_soumission": (NOW + timedelta(days=5)).isoformat(),
                "date_ouverture_plis": NOW.isoformat(),
                "poids_technique": 55,
                "poids_financier": 45,
            },
        )
        appel_delete = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service_contractant": self.ids["service_id"],
                "reference": f"{PREFIX}-AO-DELETE",
                "titre": "Appel Delete",
                "description": "Delete me",
                "type_procedure": "restreinte",
                "montant_estime": "50000.00",
                "date_publication": NOW.isoformat(),
                "date_limite_soumission": (NOW + timedelta(days=2)).isoformat(),
                "date_ouverture_plis": NOW.isoformat(),
                "poids_technique": 50,
                "poids_financier": 50,
            },
        )
        self.request(
            "DELETE",
            f"/appels-offres/{appel_delete['id_appel_offres']}",
            {204},
            token=self.tokens["admin_access"],
        )

        self.json(
            "PUT",
            f"/validations/{self.ids['validation_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_utilisateur": self.ids["user_id"],
                "id_soumission": self.ids["soumission_id"],
                "type": "interne",
                "is_validated": True,
                "commentaire": "Validation put finale",
            },
        )
        self.json(
            "PUT",
            f"/contrats/{self.ids['contrat_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={
                "id_soumission": self.ids["soumission_id"],
                "id_service_contractants": self.ids["service_id"],
                "numero_contrat": f"{PREFIX}-CTR-1",
                "date_signature": NOW.isoformat(),
                "statut": "actif",
            },
        )

        compat_doc = self.json(
            "POST",
            "/documents",
            {201},
            token=self.tokens["admin_access"],
            files={"file": ("compat.pdf", b"compat document", "application/pdf")},
            data={"related_type": "compat", "is_encrypted": "false"},
        )
        self.ids["compat_document_id"] = compat_doc["id_document"]
        self.json(
            "PATCH",
            f"/documents/{self.ids['compat_document_id']}",
            {200},
            token=self.tokens["admin_access"],
            json={"ia_verif_statut": "VALID", "ia_verif_details": "compat-patch"},
        )
        self.json(
            "PUT",
            f"/api/documents/{self.ids['compat_document_id']}/ia-metadata/",
            {200},
            token=self.tokens["admin_access"],
            json={"ia_verif_statut": "ANOMALY", "ia_verif_details": "compat-put"},
        )
        compat_delete_doc = self.json(
            "POST",
            "/documents",
            {201},
            token=self.tokens["admin_access"],
            files={"file": ("compat-delete.pdf", b"compat delete", "application/pdf")},
            data={"related_type": "compat-delete", "is_encrypted": "false"},
        )
        self.request(
            "DELETE",
            f"/api/documents/{compat_delete_doc['id_document']}/delete/",
            {204},
            token=self.tokens["admin_access"],
        )

        alias_appel = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service_contractant": self.ids["service_id"],
                "reference": f"{PREFIX}-AO-API-1",
                "titre": "Appel API Alias",
                "description": "Alias flow",
                "type_procedure": "ouverte",
                "montant_estime": "70000.00",
                "date_publication": NOW.isoformat(),
                "date_limite_soumission": (NOW + timedelta(days=4)).isoformat(),
                "date_ouverture_plis": NOW.isoformat(),
                "poids_technique": 60,
                "poids_financier": 40,
            },
        )
        alias_appel_id = alias_appel["id_appel_offres"]
        self.json("POST", f"/appels-offres/{alias_appel_id}/publier", {200}, token=self.tokens["admin_access"])
        self.json("POST", f"/appels-offres/{alias_appel_id}/cloturer-depot", {200}, token=self.tokens["admin_access"])

        alias_soumission = self.json(
            "POST",
            "/soumissions",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": alias_appel_id,
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_id']}-alias.pdf.enc",
                "cle_dechiffrement_hash": "alias-key",
                "document_ids": [self.ids["document_id"]],
            },
        )
        alias_soumission_id = alias_soumission["id"]
        self.json("GET", "/soumissions", {200}, token=self.tokens["admin_access"])
        self.json("GET", f"/soumissions/{alias_soumission_id}", {200}, token=self.tokens["admin_access"])
        self.json("POST", f"/api/soumissions/{alias_appel_id}/open-bids/", {200}, token=self.tokens["admin_access"])
        self.json(
            "POST",
            f"/api/soumissions/{alias_soumission_id}/evaluate/",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_comission": self.ids["evaluation_commission_id"],
                "id_utilisateur": self.ids["admin_user_id"],
                "type": "technique",
                "note": 91,
                "commentaire": "Alias evaluation",
            },
        )
        self.json("GET", f"/api/soumissions/{alias_soumission_id}/evaluate/", {200}, token=self.tokens["admin_access"])
        self.json(
            "PATCH",
            f"/api/soumissions/{alias_soumission_id}/conformite/",
            {200},
            token=self.tokens["admin_access"],
            json={"conformite_statut": "CONFORME", "conformite_rapport": {"alias": True}},
        )
        self.json(
            "POST",
            f"/api/soumissions/{alias_soumission_id}/terminer-evaluation/",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/api/appels-offres/{alias_appel_id}/soumissions",
            {200},
            token=self.tokens["admin_access"],
        )
        self.json(
            "GET",
            f"/api/operateurs-economiques/{self.ids['operateur_id']}/soumissions",
            {200},
            token=self.tokens["admin_access"],
        )

        withdraw_appel = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service_contractant": self.ids["service_id"],
                "reference": f"{PREFIX}-AO-API-2",
                "titre": "Appel Withdraw API",
                "description": "Withdraw alias flow",
                "type_procedure": "ouverte",
                "montant_estime": "71000.00",
                "date_publication": NOW.isoformat(),
                "date_limite_soumission": (NOW + timedelta(days=4)).isoformat(),
                "date_ouverture_plis": NOW.isoformat(),
                "poids_technique": 60,
                "poids_financier": 40,
            },
        )
        withdraw_soumission = self.json(
            "POST",
            "/soumissions",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": withdraw_appel["id_appel_offres"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_extra_id']}-withdraw.pdf.enc",
                "cle_dechiffrement_hash": "withdraw-alias-key",
                "document_ids": [self.ids["document_extra_id"]],
            },
        )
        self.json(
            "POST",
            f"/api/soumissions/{withdraw_soumission['id']}/retirer/",
            {200},
            token=self.tokens["admin_access"],
        )

        api_delete_appel = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service_contractant": self.ids["service_id"],
                "reference": f"{PREFIX}-AO-API-3",
                "titre": "Appel API Delete",
                "description": "Delete via api route",
                "type_procedure": "ouverte",
                "montant_estime": "72000.00",
                "date_publication": NOW.isoformat(),
                "date_limite_soumission": (NOW + timedelta(days=4)).isoformat(),
                "date_ouverture_plis": NOW.isoformat(),
                "poids_technique": 60,
                "poids_financier": 40,
            },
        )
        api_delete_soumission = self.json(
            "POST",
            "/soumissions",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": api_delete_appel["id_appel_offres"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_id']}-api-delete.pdf.enc",
                "cle_dechiffrement_hash": "api-delete-key",
                "document_ids": [self.ids["document_id"]],
            },
        )
        self.request(
            "DELETE",
            f"/api/soumissions/{api_delete_soumission['id']}/",
            {204},
            token=self.tokens["admin_access"],
        )

        nonapi_delete_appel = self.json(
            "POST",
            "/appels-offres",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_service_contractant": self.ids["service_id"],
                "reference": f"{PREFIX}-AO-API-4",
                "titre": "Appel Non API Delete",
                "description": "Delete via non api route",
                "type_procedure": "ouverte",
                "montant_estime": "73000.00",
                "date_publication": NOW.isoformat(),
                "date_limite_soumission": (NOW + timedelta(days=4)).isoformat(),
                "date_ouverture_plis": NOW.isoformat(),
                "poids_technique": 60,
                "poids_financier": 40,
            },
        )
        nonapi_delete_soumission = self.json(
            "POST",
            "/soumissions",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": nonapi_delete_appel["id_appel_offres"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": f"https://example.com/documents/{self.ids['document_id']}-nonapi-delete.pdf.enc",
                "cle_dechiffrement_hash": "nonapi-delete-key",
                "document_ids": [self.ids["document_id"]],
            },
        )
        self.json("GET", f"/soumissions/{nonapi_delete_soumission['id']}", {200}, token=self.tokens["admin_access"])
        self.request(
            "DELETE",
            f"/soumissions/{nonapi_delete_soumission['id']}",
            {204},
            token=self.tokens["admin_access"],
        )

    def negative_cases(self):
        self.request("GET", "/users", {401})
        self.request(
            "POST",
            "/auth/login",
            {401},
            json={"email": f"{PREFIX}-admin@example.com", "password": "WrongPassword123!"},
        )
        self.request(
            "POST",
            "/documents",
            {400},
            token=self.tokens["admin_access"],
            data={"related_type": "invalid", "is_encrypted": "false"},
        )
        self.request(
            "POST",
            "/api/soumissions/",
            {400},
            token=self.tokens["admin_access"],
            json={
                "id_appel_offre": self.ids["appel_id"],
                "id_soumissionnaire": self.ids["operateur_id"],
                "offre_financiere_chiffree_url": "https://example.com/documents/invalid.pdf.enc",
                "cle_dechiffrement_hash": "invalid-doc-key",
                "document_ids": [999999],
            },
        )
        self.request(
            "POST",
            "/api/recours/",
            {400},
            token=self.tokens["admin_access"],
            json={
                "id_operateur_economique": self.ids["operateur_id"],
                "id_validation": self.ids["validation_id"],
                "id_soumission": self.ids["soumission_id"],
                "motif": "Duplicate recours",
            },
        )
        self.request(
            "POST",
            f"/notifications/{self.ids['notification_id']}/marquer-lu",
            {400},
            token=self.tokens["admin_access"],
        )
        self.request(
            "GET",
            "/notifications/999999",
            {404},
            token=self.tokens["admin_access"],
        )
        self.request("GET", "/appels-offres/999999", {404}, token=self.tokens["admin_access"])
        duplicate_sign_contrat = self.json(
            "POST",
            "/contrats",
            {201},
            token=self.tokens["admin_access"],
            json={
                "id_soumission": self.ids["soumission_withdraw_id"],
                "id_service_contractants": self.ids["service_id"],
                "numero_contrat": f"{PREFIX}-CTR-DUP",
                "statut": "brouillon",
            },
        )
        self.json(
            "POST",
            f"/contrats/{duplicate_sign_contrat['id_contrat']}/signer",
            {200},
            token=self.tokens["admin_access"],
        )
        self.request(
            "POST",
            f"/contrats/{duplicate_sign_contrat['id_contrat']}/signer",
            {400},
            token=self.tokens["admin_access"],
        )
        self.request("GET", "/notifications/999999", {404}, token=self.tokens["admin_access"])
        self.request(
            "DELETE",
            f"/contrats/{duplicate_sign_contrat['id_contrat']}",
            {204},
            token=self.tokens["admin_access"],
        )

    def document_delete(self):
        self.request(
            "DELETE",
            f"/documents/{self.ids['document_delete_id']}",
            {204},
            token=self.tokens["admin_access"],
        )

    def public_routes(self):
        self.request("GET", "/health", {200})
        self.request("GET", "/ready", {200})
        self.request("GET", "/openapi.json", {200})
        self.request("GET", "/docs/swagger/", {200}, headers={"Accept": "text/html"})
        self.request("GET", "/docs/redoc/", {200}, headers={"Accept": "text/html"})

    def walk_routes(self, patterns, prefix=""):
        for pattern in patterns:
            if isinstance(pattern, URLPattern):
                callback = pattern.callback
                view_class = getattr(callback, "view_class", None)
                route = prefix + str(pattern.pattern)
                yield route, view_class
            elif isinstance(pattern, URLResolver):
                yield from self.walk_routes(pattern.url_patterns, prefix + str(pattern.pattern))

    def record_coverage(self, method, path):
        concrete_path = urlsplit(path).path or path
        try:
            match = resolve(concrete_path)
        except Resolver404:
            return
        route = getattr(match, "route", None) or concrete_path.lstrip("/")
        self.covered_methods.setdefault(route, set()).add(method.upper())

    def concrete_path(self, route):
        replacements = {
            "user_id": str(self.ids.get("user_id", 1)),
            "role_id": str(self.ids.get("role_id", 1)),
            "permission_id": str(self.ids.get("permission_id", 1)),
            "organisation_id": str(self.ids.get("organisation_id", 1)),
            "service_id": str(self.ids.get("service_id", 1)),
            "operateur_id": str(self.ids.get("operateur_id", 1)),
            "membre_id": str(self.ids.get("membre_id", 1)),
            "tutelle_id": str(self.ids.get("tutelle_id", 1)),
            "commission_id": str(self.ids.get("commission_id", 1)),
            "commission_interne_id": str(self.ids.get("commission_interne_id", 1)),
            "commission_externe_id": str(self.ids.get("commission_externe_id", 1)),
            "appel_id": str(self.ids.get("appel_id", 1)),
            "document_id": str(self.ids.get("document_id", 1)),
            "soumission_id": str(self.ids.get("soumission_id", 1)),
            "evaluation_id": str(self.ids.get("evaluation_id", 1)),
            "validation_id": str(self.ids.get("validation_id", 1)),
            "contrat_id": str(self.ids.get("contrat_id", 1)),
            "notification_id": str(self.ids.get("notification_id", 1)),
            "anomalie_id": str(self.ids.get("anomalie_id", 1)),
            "recours_id": str(self.ids.get("recours_id", 1)),
            "log_id": str(self.ids.get("log_id", 1)),
            "record_id": str(self.ids.get("record_id", 1)),
            "nif": self.ids.get("operateur_nif", "123456789012345"),
            "entite_type": "smoke",
            "entite_id": "123",
            "content_type_id": "1",
            "object_id": "1",
            "url": "",
            "app_label": "auth",
        }

        def replace(match):
            inner = match.group(1)
            converter, name = inner.split(":", 1)
            if name not in replacements:
                if converter == "int":
                    return "1"
                if converter == "str":
                    return "sample"
                return "sample"
            return replacements[name]

        concrete = re.sub(r"<([^>]+)>", replace, route)
        if "(?P<" in concrete or "^" in concrete or "$" in concrete:
            return None
        return "/" + concrete.lstrip("/")

    def options_sweep(self):
        checked = 0
        for route, view_class in self.walk_routes(get_resolver().url_patterns):
            if route.startswith("admin/"):
                continue
            path = self.concrete_path(route)
            if not path:
                continue
            if path.startswith("/docs/") or path == "/openapi.json":
                continue
            response = self.request("OPTIONS", path, {200}, token=self.tokens["admin_access"])
            if response.status_code != 200:
                fail(f"OPTIONS failed for {path}")
            checked += 1
        log(f"OPTIONS sweep passed for {checked} API routes")

    def assert_non_options_coverage(self):
        missing = []
        ignored_prefixes = ("admin/",)
        for route, _view_class in self.walk_routes(get_resolver().url_patterns):
            if route.startswith(ignored_prefixes):
                continue
            expected_methods = set()
            path = self.concrete_path(route)
            if not path:
                continue
            try:
                match = resolve(path)
            except Resolver404:
                continue
            view_class = getattr(match.func, "view_class", None)
            if not view_class:
                continue
            expected_methods = {
                method.upper()
                for method in getattr(view_class, "http_method_names", [])
                if method not in {"head", "options"} and hasattr(view_class, method)
            }
            if not expected_methods:
                continue
            covered = self.covered_methods.get(route, set()) | self.covered_methods.get(match.route or "", set())
            route_missing = sorted(expected_methods - covered)
            if route_missing:
                missing.append((route, route_missing))

        if missing:
            details = "\n".join(f"{route}: {', '.join(methods)}" for route, methods in missing)
            fail(f"Missing non-OPTIONS coverage for:\n{details}")

    def run(self):
        self.wait_for_api()
        self.reset_database()
        self.seed_admin()
        self.public_routes()
        self.auth_setup()
        self.acteurs_setup()
        self.user_setup()
        self.contractant_setup()
        self.documents_setup()
        self.appels_setup()
        self.soumissions_and_evaluations_setup()
        self.contrats_setup()
        self.notifications_setup()
        self.ia_setup()
        self.recours_setup()
        self.audit_setup()
        self.route_coverage_extensions()
        self.negative_cases()
        self.document_delete()
        self.assert_non_options_coverage()
        self.options_sweep()
        log("Smoke suite completed successfully")


if __name__ == "__main__":
    try:
        ApiSmokeRunner().run()
    except SmokeFailure as exc:
        log(f"SMOKE TEST FAILED: {exc}")
        sys.exit(1)
    except Exception as exc:
        log(f"UNEXPECTED FAILURE: {exc}")
        raise
