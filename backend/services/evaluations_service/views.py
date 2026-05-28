from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg

from .models import (
    ComissionEvaluation, MembresCommissionEvaluation, Evaluation,
    RegistreReception, RegistreIntegriteConfirmation,
    SeanceOuverture, PliOuverture, ParapheMembre,
    ConformiteOffer, CapacitesOffer,
    EvalTechniqueOffer, EvalFinanciereOffer,AssignationCT, RapportCT,
    ClassementEntry, ProcesVerbal, SignaturePV, SCDecision,
)
from .serializers import (
    ComissionEvaluationSerializer, EvaluationSerializer,
    RegistreReceptionSerializer, ConfirmerIntegriteSerializer,
    SeanceOuvertureSerializer, OuvrirPliSerializer, ParapheSerializer,
    ConformiteOfferSerializer, DemandeComplementSerializer,
    CapacitesOfferSerializer,
    EvalTechniqueOfferSerializer, LockTechniqueSerializer,
    EvalFinanciereOfferSerializer,
    RapportCTSerializer,
    ClassementEntrySerializer, EcarterProvisionalSerializer,
    ProcesVerbalSerializer, SignerPVSerializer,
    SCDecisionSerializer, SCDecisionCreateSerializer,
)


def _get_commission_or_404(id_comission):
    try:
        return ComissionEvaluation.objects.get(pk=id_comission)
    except ComissionEvaluation.DoesNotExist:
        return None


# ── Health ────────────────────────────────────────────────────────────────────

class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


# ── Commission ────────────────────────────────────────────────────────────────

class CommissionDetailView(APIView):
    """GET /commissions/{id_comission}/ — returns commission + members with role_label."""
    def get(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ComissionEvaluationSerializer(c).data)


# ── Step 1: Registre de réception ────────────────────────────────────────────

class RegistreReceptionListView(APIView):
    """
    GET  /commissions/{id_comission}/registre/   — list reception entries
    POST /commissions/{id_comission}/registre/   — add a reception entry (called on OE submission)
    """
    def get(self, request, id_comission):
        entries = RegistreReception.objects.filter(id_comission=id_comission).order_by('numero_ordre')
        return Response(RegistreReceptionSerializer(entries, many=True).data)

    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data['id_comission'] = id_comission
        serializer = RegistreReceptionSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConfirmerIntegriteView(APIView):
    """
    POST /commissions/{id_comission}/registre/confirmer-integrite/
    Locks the register — irréversible. Generates the confirmation record.
    """
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        if RegistreIntegriteConfirmation.objects.filter(id_comission=id_comission).exists():
            return Response({"error": "Intégrité déjà confirmée — registre verrouillé."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ConfirmerIntegriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        confirmation = RegistreIntegriteConfirmation.objects.create(
            id_comission=c,
            confirmed_by=serializer.validated_data['confirmed_by']
        )
        return Response({"confirmed_at": confirmation.confirmed_at, "confirmed_by": confirmation.confirmed_by}, status=status.HTTP_201_CREATED)


# ── Step 2: Séance d'ouverture ────────────────────────────────────────────────

class SeanceOuvertureView(APIView):
    """
    GET  /commissions/{id_comission}/seance/   — get session state
    POST /commissions/{id_comission}/seance/demarrer/  — start session (timestamps, anomaly log)
    """
    def get(self, request, id_comission):
        try:
            seance = SeanceOuverture.objects.get(id_comission=id_comission)
            return Response(SeanceOuvertureSerializer(seance).data)
        except SeanceOuverture.DoesNotExist:
            return Response({"statut": "not_started"})


class DemarrerSeanceView(APIView):
    """POST /commissions/{id_comission}/seance/demarrer/"""
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        # Must confirm register integrity first
        if not RegistreIntegriteConfirmation.objects.filter(id_comission=id_comission).exists():
            return Response({"error": "Confirmer l'intégrité du registre avant de démarrer la séance."}, status=status.HTTP_400_BAD_REQUEST)

        seance, created = SeanceOuverture.objects.get_or_create(id_comission=c)
        if seance.statut != 'not_started':
            return Response({"error": "Séance déjà démarrée."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        # Check timing against published date — anomaly if > 15 min off
        # date_ouverture_plis comes from AppelOffres via the front (passed in body)
        date_publiee_str = request.data.get('date_ouverture_plis')
        anomalie = ""
        if date_publiee_str:
            from django.utils.dateparse import parse_datetime
            date_publiee = parse_datetime(str(date_publiee_str))
            if date_publiee:
                if timezone.is_naive(date_publiee):
                    date_publiee = timezone.make_aware(date_publiee)
                diff_min = round((now - date_publiee).total_seconds() / 60)
                if abs(diff_min) > 15:
                    anomalie = f"Séance démarrée avec un écart de {diff_min:+d} min par rapport à l'heure publiée — anomalie légale enregistrée."

        seance.statut = 'in_progress'
        seance.started_at = now
        seance.anomalie = anomalie
        seance.save()
        # Auto-create PliOuverture stubs from registre entries
        from .models import RegistreReception
        entries = RegistreReception.objects.filter(id_comission=id_comission, hors_delai=False).order_by('numero_ordre')
        for entry in entries:
         PliOuverture.objects.get_or_create(
         seance=seance,
         id_soumission=entry.id_soumission,
     )
        return Response(SeanceOuvertureSerializer(seance).data, status=status.HTTP_201_CREATED)


class CloturerSeanceView(APIView):
    """POST /commissions/{id_comission}/seance/cloturer/"""
    def post(self, request, id_comission):
        try:
            seance = SeanceOuverture.objects.get(id_comission=id_comission)
        except SeanceOuverture.DoesNotExist:
            return Response({"error": "Séance introuvable"}, status=status.HTTP_404_NOT_FOUND)

        if seance.statut != 'in_progress':
            return Response({"error": "Séance non en cours."}, status=status.HTTP_400_BAD_REQUEST)

        seance.statut = 'closed'
        seance.closed_at = timezone.now()
        seance.save()
        # After seance.save() in CloturerSeanceView.post:
        ProcesVerbal.objects.get_or_create(
         id_comission=id_comission,
         type_pv='ouverture',
         defaults={'locked': False}
)
        return Response(SeanceOuvertureSerializer(seance).data)


class OuvrirPliView(APIView):
    """POST /commissions/{id_comission}/seance/ouvrir-pli/"""
    def post(self, request, id_comission):
        try:
            seance = SeanceOuverture.objects.get(id_comission=id_comission, statut='in_progress')
        except SeanceOuverture.DoesNotExist:
            return Response({"error": "Séance non en cours."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OuvrirPliSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pli, created = PliOuverture.objects.get_or_create(
         seance=seance,
         id_soumission=serializer.validated_data['id_soumission'],
         defaults={
          'opened_at': timezone.now(),
          'montant_declare': serializer.validated_data.get('montant_declare'),
    }
)
        
        if not created:
         if pli.opened_at is not None:
          return Response({"error": "Pli déjà ouvert."}, status=status.HTTP_400_BAD_REQUEST)
    # stub exists but not yet opened — open it now
         pli.opened_at = timezone.now()
         if not pli.montant_declare:
           from soumissions_app.models import Soumission
           try:
            s = Soumission.objects.get(id_soumission=pli.id_soumission)
            pli.montant_declare = s.montant_financier
           except Soumission.DoesNotExist:
            pass
         pli.save()
        return Response({
            "id_soumission": pli.id_soumission,
            "opened_at": pli.opened_at,
            "montant_declare": pli.montant_declare,
        }, status=status.HTTP_201_CREATED)


class ParapherPliView(APIView):
    """POST /commissions/{id_comission}/seance/plis/{id_soumission}/parapher/"""
    def post(self, request, id_comission, id_soumission):
        try:
            seance = SeanceOuverture.objects.get(id_comission=id_comission)
            pli = PliOuverture.objects.get(seance=seance, id_soumission=id_soumission)
        except (SeanceOuverture.DoesNotExist, PliOuverture.DoesNotExist):
            return Response({"error": "Pli introuvable"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ParapheSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        paraphe, created = ParapheMembre.objects.get_or_create(
            pli=pli,
            id_utilisateur=serializer.validated_data['id_utilisateur']
        )
        return Response({"paraphed": True, "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ── Step 3: Conformité ────────────────────────────────────────────────────────

class ConformiteView(APIView):
    """
    GET  /commissions/{id_comission}/conformite/
    POST /commissions/{id_comission}/conformite/   — create or update conformity record
    """
    def get(self, request, id_comission):
        entries = ConformiteOffer.objects.filter(id_comission=id_comission)
        return Response(ConformiteOfferSerializer(entries, many=True).data)

    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        id_soumission = request.data.get('id_soumission')
        if not id_soumission:
            return Response({"error": "id_soumission requis"}, status=status.HTTP_400_BAD_REQUEST)

        obj, _ = ConformiteOffer.objects.get_or_create(id_comission=c, id_soumission=id_soumission)

        # Update only provided fields
        updatable = ['enveloppe_anonyme', 'documents_corrects', 'pas_prix_technique',
                     'eligible_art75', 'complement_demande', 'complement_motif',
                     'resultat', 'motif_ecart']
        for field in updatable:
            if field in request.data:
                setattr(obj, field, request.data[field])
        obj.save()
        return Response(ConformiteOfferSerializer(obj).data)


# ── Step 4: Capacités ─────────────────────────────────────────────────────────

class CapacitesView(APIView):
    """GET + POST /commissions/{id_comission}/capacites/"""
    def get(self, request, id_comission):
        entries = CapacitesOffer.objects.filter(id_comission=id_comission)
        return Response(CapacitesOfferSerializer(entries, many=True).data)

    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        id_soumission = request.data.get('id_soumission')
        if not id_soumission:
            return Response({"error": "id_soumission requis"}, status=status.HTTP_400_BAD_REQUEST)

        obj, _ = CapacitesOffer.objects.get_or_create(id_comission=c, id_soumission=id_soumission)
        for field in ['items_results', 'justification', 'resultat', 'motif']:
            if field in request.data:
                setattr(obj, field, request.data[field])
        obj.save()
        return Response(CapacitesOfferSerializer(obj).data)


# ── Step 5: Évaluation technique ─────────────────────────────────────────────

class EvalTechniqueView(APIView):
    """GET + POST /commissions/{id_comission}/eval-technique/"""
    def get(self, request, id_comission):
        entries = EvalTechniqueOffer.objects.filter(id_comission=id_comission)
        return Response(EvalTechniqueOfferSerializer(entries, many=True).data)

    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        id_soumission = request.data.get('id_soumission')
        if not id_soumission:
            return Response({"error": "id_soumission requis"}, status=status.HTTP_400_BAD_REQUEST)

        obj, _ = EvalTechniqueOffer.objects.get_or_create(id_comission=c, id_soumission=id_soumission)

        if obj.locked:
            return Response({"error": "Scores verrouillés — aucune modification rétroactive possible."}, status=status.HTTP_400_BAD_REQUEST)

        for field in ['scores', 'justifications', 'score_total']:
            if field in request.data:
                setattr(obj, field, request.data[field])
        obj.save()
        return Response(EvalTechniqueOfferSerializer(obj).data)


class LockEvalTechniqueView(APIView):
    """
    POST /commissions/{id_comission}/eval-technique/lock/
    Locks scores for one soumission — sets qualifie based on score vs threshold.
    threshold comes from AppelOffres (passed by front in body).
    """
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        id_soumission = request.data.get('id_soumission')
        threshold = request.data.get('threshold', 70)  # SC-defined, passed by front

        try:
            obj = EvalTechniqueOffer.objects.get(id_comission=c, id_soumission=id_soumission)
        except EvalTechniqueOffer.DoesNotExist:
            return Response({"error": "Évaluation introuvable"}, status=status.HTTP_404_NOT_FOUND)

        if obj.locked:
            return Response({"error": "Déjà verrouillé"}, status=status.HTTP_400_BAD_REQUEST)

        obj.qualifie = float(obj.score_total) >= float(threshold)
        obj.locked = True
        obj.save()
        return Response(EvalTechniqueOfferSerializer(obj).data)


# ── Step 6: Évaluation financière ────────────────────────────────────────────

class EvalFinanciereView(APIView):
    """GET + POST /commissions/{id_comission}/eval-financiere/"""
    def get(self, request, id_comission):
        # Only returns data for technically qualified offers
        qualified_ids = list(
            EvalTechniqueOffer.objects.filter(id_comission=id_comission, qualifie=True)
            .values_list('id_soumission', flat=True)
        )
        entries = EvalFinanciereOffer.objects.filter(id_comission=id_comission, id_soumission__in=qualified_ids)
        return Response(EvalFinanciereOfferSerializer(entries, many=True).data)

    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        id_soumission = request.data.get('id_soumission')
        if not id_soumission:
            return Response({"error": "id_soumission requis"}, status=status.HTTP_400_BAD_REQUEST)

        # Gate: only technically qualified offers can proceed
        tech = EvalTechniqueOffer.objects.filter(id_comission=id_comission, id_soumission=id_soumission, qualifie=True).first()
        if not tech:
            return Response({"error": "Offre non qualifiée techniquement — enveloppe financière non accessible."}, status=status.HTTP_403_FORBIDDEN)

        obj, _ = EvalFinanciereOffer.objects.get_or_create(id_comission=c, id_soumission=id_soumission)

        if obj.locked:
            return Response({"error": "Évaluation financière verrouillée."}, status=status.HTTP_400_BAD_REQUEST)

        for field in ['montant_declare', 'montant_bpu_calcule', 'correction_rule',
                      'montant_corrige', 'marge_appliquee', 'montant_evaluation',
                      'refuse_correction', 'refuse_motif']:
            if field in request.data:
                setattr(obj, field, request.data[field])
        obj.save()
        return Response(EvalFinanciereOfferSerializer(obj).data)


class LockEvalFinanciereView(APIView):
    """POST /commissions/{id_comission}/eval-financiere/lock/"""
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        id_soumission = request.data.get('id_soumission')
        try:
            obj = EvalFinanciereOffer.objects.get(id_comission=c, id_soumission=id_soumission)
        except EvalFinanciereOffer.DoesNotExist:
            return Response({"error": "Évaluation financière introuvable"}, status=status.HTTP_404_NOT_FOUND)

        obj.locked = True
        obj.save()
        return Response(EvalFinanciereOfferSerializer(obj).data)


# ── Step 7: Classement ────────────────────────────────────────────────────────

class ClassementView(APIView):
    """
    GET  /commissions/{id_comission}/classement/   — get current ranking
    POST /commissions/{id_comission}/classement/calculer/  — compute and store ranking
    """
    def get(self, request, id_comission):
        entries = ClassementEntry.objects.filter(id_comission=id_comission).order_by('rang')
        return Response(ClassementEntrySerializer(entries, many=True).data)


class CalculerClassementView(APIView):
    """
    POST /commissions/{id_comission}/classement/calculer/
    Applies SC methodology (passed by front) to compute ranking.
    Body: { methodology: 'price_only'|'weighted', poids_technique: int, poids_financier: int }
    """
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        methodology = request.data.get('methodology', 'weighted')
        poids_tech = int(request.data.get('poids_technique', 60))
        poids_fin = int(request.data.get('poids_financier', 40))

        tech_evals = EvalTechniqueOffer.objects.filter(id_comission=id_comission, qualifie=True, locked=True)
        if not tech_evals.exists():
            return Response({"error": "Aucune offre techniquement qualifiée et verrouillée."}, status=status.HTTP_400_BAD_REQUEST)

        fin_evals = {
            e.id_soumission: e for e in
            EvalFinanciereOffer.objects.filter(id_comission=id_comission, locked=True)
        }

        # Financial score: (min_amount / eval_amount) * 100
        amounts = [e.montant_evaluation for e in fin_evals.values() if e.montant_evaluation]
        min_amount = min(amounts) if amounts else None

        entries = []
        for te in tech_evals:
            sid = te.id_soumission
            fe = fin_evals.get(sid)
            fin_score = 0
            if fe and fe.montant_evaluation and min_amount:
                fin_score = round(float(min_amount) / float(fe.montant_evaluation) * 100, 2)

            if methodology == 'price_only':
                combined = fin_score
            else:
                combined = round(float(te.score_total) * poids_tech / 100 + fin_score * poids_fin / 100, 2)

            entries.append({
                'id_soumission': sid,
                'score_technique': float(te.score_total),
                'score_financier': fin_score,
                'score_combine': combined,
            })

        entries.sort(key=lambda x: x['score_combine'], reverse=True)

        # Persist ranking
        ClassementEntry.objects.filter(id_comission=id_comission).delete()
        for rank, e in enumerate(entries, start=1):
            ClassementEntry.objects.create(
                id_comission=c,
                id_soumission=e['id_soumission'],
                rang=rank,
                score_technique=e['score_technique'],
                score_financier=e['score_financier'],
                score_combine=e['score_combine'],
            )

        return Response({"classement": entries}, status=status.HTTP_201_CREATED)


class EcarterProvisionalView(APIView):
    """POST /commissions/{id_comission}/classement/ecarter-provisional/"""
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        serializer = EcarterProvisionalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            entry = ClassementEntry.objects.get(id_comission=c, id_soumission=serializer.validated_data['id_soumission'])
        except ClassementEntry.DoesNotExist:
            return Response({"error": "Entrée de classement introuvable"}, status=status.HTTP_404_NOT_FOUND)

        entry.ecarte_provisoire = True
        entry.motif_ecart = serializer.validated_data['motif']
        entry.save()

        # Re-rank remaining entries
        remaining = ClassementEntry.objects.filter(id_comission=id_comission, ecarte_provisoire=False).order_by('rang')
        for rank, e in enumerate(remaining, start=1):
            if e.rang != rank:
                e.rang = rank
                e.save()

        return Response(ClassementEntrySerializer(
            ClassementEntry.objects.filter(id_comission=id_comission).order_by('rang'), many=True
        ).data)


# ── Step 8: PV & SC decision ─────────────────────────────────────────────────

class PVView(APIView):
    """GET + POST /commissions/{id_comission}/pv/{type_pv}/"""
    def get(self, request, id_comission, type_pv):
        try:
            pv = ProcesVerbal.objects.get(id_comission=id_comission, type_pv=type_pv)
            return Response(ProcesVerbalSerializer(pv).data)
        except ProcesVerbal.DoesNotExist:
            return Response({"error": "PV introuvable"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, id_comission, type_pv):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)
        pv, created = ProcesVerbal.objects.get_or_create(id_comission=c, type_pv=type_pv)
        return Response(ProcesVerbalSerializer(pv).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class SignerPVView(APIView):
    """
    POST /commissions/{id_comission}/pv/{type_pv}/signer/
    No member can be blocked from signing — reserve mechanism is the outlet for disagreement.
    """
    def post(self, request, id_comission, type_pv):
        try:
            pv = ProcesVerbal.objects.get(id_comission=id_comission, type_pv=type_pv)
        except ProcesVerbal.DoesNotExist:
            return Response({"error": "PV introuvable"}, status=status.HTTP_404_NOT_FOUND)

        if pv.locked:
            return Response({"error": "PV déjà verrouillé."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SignerPVSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reserve_text = serializer.validated_data.get('reserve', '')
        sig, created = SignaturePV.objects.get_or_create(
            pv=pv,
            id_utilisateur=serializer.validated_data['id_utilisateur'],
            defaults={'signed_at': timezone.now(), 'reserve': reserve_text, 'has_reserve': bool(reserve_text)}
        )
        if not created:
            # Already signed — idempotent
            return Response({"already_signed": True})

        return Response({"signed": True, "has_reserve": sig.has_reserve, "signed_at": sig.signed_at}, status=status.HTTP_201_CREATED)


class LockPVView(APIView):
    """POST /commissions/{id_comission}/pv/{type_pv}/verrouiller/"""
    def post(self, request, id_comission, type_pv):
        try:
            pv = ProcesVerbal.objects.get(id_comission=id_comission, type_pv=type_pv)
        except ProcesVerbal.DoesNotExist:
            return Response({"error": "PV introuvable"}, status=status.HTTP_404_NOT_FOUND)

        # Verify all commission members have signed
        member_ids = list(
            MembresCommissionEvaluation.objects.filter(id_comission=id_comission)
            .values_list('id_utilisateur', flat=True)
        )
        signed_ids = list(pv.signatures.values_list('id_utilisateur', flat=True))
        unsigned = [m for m in member_ids if m not in signed_ids]
        if unsigned:
            return Response({"error": f"Membres n'ayant pas signé : {unsigned}"}, status=status.HTTP_400_BAD_REQUEST)

        pv.locked = True
        pv.save()
        return Response(ProcesVerbalSerializer(pv).data)


class SoumettreAuSCView(APIView):
    """
    POST /commissions/{id_comission}/soumettre-sc/
    Both PVs must be locked before submitting to SC.
    """
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        pv_ouv = ProcesVerbal.objects.filter(id_comission=id_comission, type_pv='ouverture', locked=True).first()
        pv_eval = ProcesVerbal.objects.filter(id_comission=id_comission, type_pv='evaluation', locked=True).first()

        if not pv_ouv or not pv_eval:
            return Response({"error": "Les deux PVs doivent être verrouillés et signés avant soumission au SC."}, status=status.HTTP_400_BAD_REQUEST)

        ProcesVerbal.objects.filter(id_comission=id_comission).update(sent_to_sc=True)
        return Response({"submitted": True})


class SCDecisionView(APIView):
    """
    POST /commissions/{id_comission}/sc-decision/
    SC accepts, rejects (mandatory motif), or requests more info.
    Rejection motif is logged and auditable.
    """
    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SCDecisionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        decision = SCDecision.objects.create(
            id_comission=c,
            decision=serializer.validated_data['decision'],
            motif_rejet=serializer.validated_data.get('motif_rejet', ''),
            decided_by=serializer.validated_data['decided_by'],
        )
        return Response(SCDecisionSerializer(decision).data, status=status.HTTP_201_CREATED)

# ── Comité Technique ──────────────────────────────────────────────────────────

class CTCommissionView(APIView):
    """GET /ct/commission/?utilisateur=<id> — CT fetches their assigned commission."""
    def get(self, request):
        id_utilisateur = request.query_params.get('utilisateur')
        if not id_utilisateur:
            return Response({"error": "utilisateur param required"}, status=status.HTTP_400_BAD_REQUEST)
        assignation = AssignationCT.objects.filter(
            id_utilisateur=id_utilisateur
        ).select_related('id_comission').first()
        if not assignation:
            return Response({"error": "Aucune assignation CT trouvée"}, status=status.HTTP_404_NOT_FOUND)
        c = assignation.id_comission
        return Response({
            'id_comission': c.id_comission,
            'nom_comission': c.nom_comission,
            'categorie': c.categorie,
        })


class RapportCTView(APIView):
    """
    GET  /commissions/<id>/rapport-ct/         — COPEO reads the CT report
    POST /commissions/<id>/rapport-ct/         — CT saves/submits their report
    """
    def get(self, request, id_comission):
        rapport = RapportCT.objects.filter(id_comission=id_comission).first()
        if not rapport:
            return Response(None)
        return Response(RapportCTSerializer(rapport).data)

    def post(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)
        id_utilisateur = request.data.get('submitted_by')
        if not id_utilisateur:
            return Response({"error": "submitted_by requis"}, status=status.HTTP_400_BAD_REQUEST)
        rapport, _ = RapportCT.objects.get_or_create(
            id_comission=c,
            submitted_by=id_utilisateur,
        )
        for field in ['methodologie', 'equipe', 'materiels', 'anomalies', 'avis_global']:
            if field in request.data:
                setattr(rapport, field, request.data[field])
        if request.data.get('submitted'):
            rapport.submitted = True
            from django.utils import timezone
            rapport.submitted_at = timezone.now()
        rapport.save()
        return Response(RapportCTSerializer(rapport).data)
# ── Legacy endpoints kept for backward compat ────────────────────────────────

class EvaluationView(APIView):
    def get(self, request):
        evaluations = Evaluation.objects.all()
        return Response(EvaluationSerializer(evaluations, many=True).data)

    def post(self, request):
        serializer = EvaluationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EvaluationDetailView(APIView):
    def get_object(self, evaluation_id):
        try:
            return Evaluation.objects.get(id_evalution=evaluation_id)
        except Evaluation.DoesNotExist:
            return None

    def get(self, request, evaluation_id):
        e = self.get_object(evaluation_id)
        if not e:
            return Response({"error": "Évaluation non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        return Response(EvaluationSerializer(e).data)

    def patch(self, request, evaluation_id):
        e = self.get_object(evaluation_id)
        if not e:
            return Response({"error": "Évaluation non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        serializer = EvaluationSerializer(e, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, evaluation_id):
        e = self.get_object(evaluation_id)
        if not e:
            return Response({"error": "Évaluation non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        e.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
class CommissionStateView(APIView):
    """
    GET /commissions/<id_comission>/state/
    Aggregates full commission state into one payload for frontend polling.
    """
    def get(self, request, id_comission):
        c = _get_commission_or_404(id_comission)
        rapport_ct = RapportCT.objects.filter(id_comission=id_comission).first()
        if not c:
            return Response({"error": "Commission introuvable"}, status=status.HTTP_404_NOT_FOUND)
        from appels_service.models import AppelOffres
        appel = AppelOffres.objects.filter(commission_id=str(id_comission)).first()
        registre = RegistreReception.objects.filter(id_comission=id_comission).order_by('numero_ordre')
        integrite = RegistreIntegriteConfirmation.objects.filter(id_comission=id_comission).first()

        seance = SeanceOuverture.objects.filter(id_comission=id_comission).first()
        plis = list(PliOuverture.objects.filter(seance=seance)) if seance else []
        all_paraphes = list(ParapheMembre.objects.filter(pli__seance=seance)) if seance else []

        conformites = ConformiteOffer.objects.filter(id_comission=id_comission)
        capacites = CapacitesOffer.objects.filter(id_comission=id_comission)
        evals_tech = EvalTechniqueOffer.objects.filter(id_comission=id_comission)
        evals_fin = EvalFinanciereOffer.objects.filter(id_comission=id_comission)
        classement = ClassementEntry.objects.filter(id_comission=id_comission).order_by('rang')

        pv_ouverture = ProcesVerbal.objects.filter(id_comission=id_comission, type_pv='ouverture').first()
        pv_evaluation = ProcesVerbal.objects.filter(id_comission=id_comission, type_pv='evaluation').first()
        sc_decision = SCDecision.objects.filter(id_comission=id_comission).order_by('-decided_at').first()

        membres = MembresCommissionEvaluation.objects.filter(id_comission=id_comission)

        from soumissions_app.models import Soumission as SoumissionModel

        soumission_map = {
            s.id_soumission: s
            for s in SoumissionModel.objects.filter(
            id_soumission__in=[p.id_soumission for p in plis]
      )
}
        registre_map = {r.id_soumission: r for r in registre}

        plis_data = []
        for p in plis:
          s = soumission_map.get(p.id_soumission)
          r = registre_map.get(p.id_soumission)
          plis_data.append({
        'id': p.id,
        'id_soumission': p.id_soumission,
        'nom_oe': r.nom_oe if r else None,
        'opened_at': p.opened_at,
        'montant_declare': str(p.montant_declare) if p.montant_declare else (
            str(s.montant_financier) if s and s.montant_financier else None
        ),
        'document_ids': s.document_ids if s else [],
        'paraphes': [
            {'id_utilisateur': ph.id_utilisateur, 'paraphed_at': ph.paraphed_at}
            for ph in all_paraphes if ph.pli_id == p.id
        ],
    })

        payload = {
            'commission': ComissionEvaluationSerializer(c).data,
            'rapport_ct': RapportCTSerializer(rapport_ct).data if rapport_ct else None,
            'membres': [
                {'id': m.id, 'id_utilisateur': m.id_utilisateur, 'role_label': m.role_label}
                for m in membres
            ],
            'registre': {
                'entries': RegistreReceptionSerializer(registre, many=True).data,
                'integrite_confirmed': integrite is not None,
                'integrite_confirmed_at': integrite.confirmed_at if integrite else None,
            },
            'seance': {
                'data': SeanceOuvertureSerializer(seance).data if seance else None,
                'plis': plis_data,
            },
            'conformites': ConformiteOfferSerializer(conformites, many=True).data,
            'capacites': CapacitesOfferSerializer(capacites, many=True).data,
            'evals_technique': EvalTechniqueOfferSerializer(evals_tech, many=True).data,
            'evals_financiere': EvalFinanciereOfferSerializer(evals_fin, many=True).data,
            'classement': ClassementEntrySerializer(classement, many=True).data,
            'pvs': {
                'ouverture': ProcesVerbalSerializer(pv_ouverture).data if pv_ouverture else None,
                'evaluation': ProcesVerbalSerializer(pv_evaluation).data if pv_evaluation else None,
            },
            'sc_decision': SCDecisionSerializer(sc_decision).data if sc_decision else None,
            'appel': {
             'methodology': appel.methodology if appel else 'weighted',
             'poids_technique': int(appel.poids_technique) if appel else 60,
             'poids_financier': int(appel.poids_financier) if appel else 40,
             'seuil_technique': int(appel.seuil_technique) if appel else 70,
             'montant_estime': float(appel.montant_estime) if appel else None,
} if appel else None,
        }

        return Response(payload)
    
class CommissionByMembreView(APIView):
    """
    GET /commissions/?membre=<id_utilisateur>
    Returns the commission the logged-in member belongs to.
    """
    def get(self, request):
        id_utilisateur = request.query_params.get('membre')
        if not id_utilisateur:
            return Response({"error": "membre param required"}, status=status.HTTP_400_BAD_REQUEST)
        
        membership = MembresCommissionEvaluation.objects.filter(
            id_utilisateur=id_utilisateur
        ).select_related('id_comission').first()
        
        if not membership:
            return Response({"error": "Aucune commission trouvée pour ce membre"}, status=status.HTTP_404_NOT_FOUND)
        
        commission = membership.id_comission
        return Response({
            'id_comission': commission.id_comission,
            'nom_comission': commission.nom_comission,
            'categorie': commission.categorie,
            'role_label': membership.role_label,
        })