import datetime
from django.utils import timezone
from appels_service.models import AppelOffres
from contractant_service.models import MembresCommissionExterne
from rest_framework.exceptions import PermissionDenied


def normalize_membre_id(membre_id):
    if membre_id is None:
        return None
    try:
        from uuid import UUID
        if isinstance(membre_id, UUID):
            return membre_id
    except Exception:
        pass
    if isinstance(membre_id, str) and '-' in membre_id:
        try:
            from uuid import UUID
            return UUID(membre_id)
        except Exception:
            return membre_id
    return membre_id


def get_commission_externe_dashboard_data(membre_id):
    """
    Récupère et catégorise les appels d'offres pour le responsable d'une commission externe.
    Applique les règles métier décrites dans la spécification: la visibilité est limitée
    aux appels dont `commission_id` correspond à `Membres_Commission_Externe.id_comission_externe`.
    """
    membre_id = normalize_membre_id(membre_id)

    # Adapter la valeur de requête au type de champ de la table des membres
    def _adapt_for_model(val, model):
        field = model._meta.get_field('id_membre')
        ftype = field.get_internal_type()
        try:
            from uuid import UUID
        except Exception:
            UUID = None

        if val is None:
            return None

        if ftype == 'UUIDField':
            if UUID and isinstance(val, str) and '-' in val:
                try:
                    return UUID(val)
                except Exception:
                    return val
            if UUID and hasattr(val, 'hex'):
                return val
            return val

        if ftype in ('IntegerField', 'AutoField', 'BigIntegerField', 'SmallIntegerField'):
            if isinstance(val, str) and '-' in val:
                try:
                    return int(val.split('-')[-1], 16)
                except Exception:
                    pass
            try:
                return int(val)
            except Exception:
                return val

        return val

    adapted = _adapt_for_model(membre_id, MembresCommissionExterne)

    # Try a safe ORM lookup first (may raise on incompatible types)
    membre_link = None
    try:
        membre_link = MembresCommissionExterne.objects.filter(id_membre=adapted).first()
    except Exception:
        membre_link = None

    # If not found, avoid further ORM type coercion errors by iterating rows
    # and comparing multiple representations (str, int last-hex, UUID).
    if not membre_link:
        from uuid import UUID

        candidates = set()
        if membre_id is not None:
            candidates.add(str(membre_id))
            try:
                candidates.add(int(str(membre_id).split('-')[-1], 16))
            except Exception:
                pass
            try:
                candidates.add(UUID(str(membre_id)))
            except Exception:
                pass

        for m in MembresCommissionExterne.objects.all():
            try:
                val = m.id_membre
            except Exception:
                continue
            # direct Python-level comparisons
            if val is None:
                continue
            if isinstance(val, int) and any(isinstance(c, int) and c == val for c in candidates):
                membre_link = m
                break
            if str(val) in candidates:
                membre_link = m
                break
            try:
                if hasattr(val, 'hex') and str(val) in candidates:
                    membre_link = m
                    break
            except Exception:
                pass

    if not membre_link:
        raise PermissionDenied("Vous n'êtes pas assigné à une commission externe.")

    # commission externe référencée (objet acteurs_service.CommissionExterne)
    commission_obj = membre_link.id_comission_externe

    # Récupérer les appels d'offres où commission_id correspond
    from django.db.models import Q
    appels = (
        AppelOffres.objects.filter(
            Q(commission_id=str(commission_obj.organisation_id)) | Q(commission_id=commission_obj.organisation_id)
        )
        .prefetch_related('suivis', 'operateurs_invites')
    )

    DELAI_VALIDATION_DAYS = 7
    now = timezone.now()

    result_appels = []
    stats = {"enAttente": 0, "enCours": 0, "enRetard": 0, "pret": 0}

    for appel in appels:
        economic_operator = str(appel.id_operateur_choisi) if appel.id_operateur_choisi else "Non spécifié"
        if not appel.id_operateur_choisi and appel.operateurs_invites.exists():
            economic_operator = f"Multiple ({appel.operateurs_invites.count()} invités)"

        suivis = list(appel.suivis.all())
        suivi_created_at = suivis[0].created_at if suivis else None

        # Prefer explicit deadline fields on appel if present
        validation_deadline = None
        for attr in ('date_limite_validation', 'validation_deadline', 'date_limite_validation_at', 'date_limite_validation_dt'):
            val = getattr(appel, attr, None)
            if val:
                validation_deadline = val
                break

        if not validation_deadline and suivi_created_at:
            validation_deadline = suivi_created_at + datetime.timedelta(days=DELAI_VALIDATION_DAYS)

        computed_status = 'Inconnu'
        delay_days = 0

        statut_val = (appel.statut or '').lower()

        # Prêt: statut in (valide, refuse, ferme)
        if statut_val in ('valide', 'refuse', 'ferme'):
            computed_status = 'Prêt'
            stats['pret'] += 1
        elif statut_val == 'non_valide':
            if not suivis and (appel.validated_by is None or appel.validated_by == ''):
                computed_status = 'En Attente'
                stats['enAttente'] += 1
            elif suivis and validation_deadline and now <= validation_deadline:
                computed_status = 'En Cours'
                stats['enCours'] += 1
            elif suivis and validation_deadline and now > validation_deadline:
                computed_status = 'En Retard'
                delay_days = (now - validation_deadline).days
                stats['enRetard'] += 1
            else:
                if suivis or (appel.validated_by is not None and appel.validated_by != ''):
                    computed_status = 'En Cours'
                    stats['enCours'] += 1
                else:
                    computed_status = 'En Attente'
                    stats['enAttente'] += 1
        else:
            computed_status = 'Inconnu'

        result_appels.append({
            "id": f"ID-{appel.id_appel_offres}",
            "rawId": appel.id_appel_offres,
            "reference": appel.reference,
            "economicOperator": economic_operator,
            "submissionDate": appel.created_at.date().isoformat(),
            "validationDeadline": validation_deadline.date().isoformat() if validation_deadline else "-",
            "status": computed_status,
            "etape": appel.etat_execution.replace('_', ' ').capitalize(),
            "delayDays": delay_days,
            "validator": appel.validated_by if appel.validated_by else "Non assigné",
            "has_suivi": bool(suivis),
            "suivi_count": len(suivis),
            "suivis": [
                {"id_utilisateur": s.id_utilisateur, "created_at": s.created_at.isoformat()} for s in suivis
            ]
        })

    total = sum(stats.values())
    pct = lambda n: round((n / total) * 100) if total > 0 else 0
    stats.update({
        "enAttentePct": pct(stats["enAttente"]),
        "enCoursPct": pct(stats["enCours"]),
        "enRetardPct": pct(stats["enRetard"]),
        "pretPct": pct(stats["pret"]),
    })

    return {"stats": stats, "appels": result_appels}
