from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from apps.common.exceptions import ApplicationException
from apps.recours.domain.exceptions import RecoursException
from apps.recours.application.dto.recours_dto import (
    RecoursCreateDTO,
    RecoursDecisionDTO,
    RecoursUpdateDTO,
)
from apps.recours.application.services.recours_service import RecoursService
from apps.recours.presentation.serializers.recours_serializers import (
    RecoursCreateSerializer,
    RecoursDecisionSerializer,
    RecoursResponseSerializer,
    RecoursUpdateSerializer,
)


class BaseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    service: RecoursService | None = None

    def _audit_recours_change(self, request, action: str, recours_id: int, details_action: dict | None = None):
        utilisateur_id = self._request_user_id(request)
        if utilisateur_id is None:
            return None

        payload = {
            "utilisateur_id": utilisateur_id,
            "action": action,
            "entite_type": "recours",
            "entite_id": recours_id,
            "adresse_ip": self._client_ip(request),
            "details_action": {
                "method": request.method,
                "path": request.path,
                **(details_action or {}),
            },
        }

        try:
            return self.service.audit_client.log_action(payload)
        except Exception:
            return None

    def _request_user_id(self, request):
        user = getattr(request, "user", None)
        for attr in ("id_utilisateur", "pk", "id"):
            value = getattr(user, attr, None)
            if value is not None:
                return int(value)

        token_payload = request.auth if isinstance(request.auth, dict) else {}
        for key in ("id_utilisateur", "user_id", "id", "sub"):
            value = token_payload.get(key)
            if value is not None:
                return int(value)

        return None

    def _client_ip(self, request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def handle_exception(self, exc):
        if isinstance(exc, (ApplicationException, RecoursException)):
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().handle_exception(exc)


class RecoursListCreateView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def get(self, request):
        filters = request.query_params.dict()
        result = self.service.list_recours(filters)
        data = [RecoursResponseSerializer(r.__dict__).data for r in result]
        return Response(data)

    def post(self, request):
        serializer = RecoursCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = RecoursCreateDTO(**serializer.validated_data)
        result = self.service.create_recours(dto)
        self._audit_recours_change(
            request,
            "CREATE_RECOURS",
            result.id_recours,
            {
                "id_soumission": result.id_soumission,
                "id_operateur_economique": result.id_operateur_economique,
                "statut": result.statut,
            },
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data,
            status=status.HTTP_201_CREATED
        )


class RecoursCreateView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request):
        serializer = RecoursCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = RecoursCreateDTO(**serializer.validated_data)

        result = self.service.create_recours(dto)
        self._audit_recours_change(
            request,
            "CREATE_RECOURS",
            result.id_recours,
            {
                "id_soumission": result.id_soumission,
                "id_operateur_economique": result.id_operateur_economique,
                "statut": result.statut,
            },
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data,
            status=status.HTTP_201_CREATED
        )


class RecoursListView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def get(self, request):
        filters = request.query_params.dict()

        result = self.service.list_recours(filters)

        data = [RecoursResponseSerializer(r.__dict__).data for r in result]

        return Response(data)


class RecoursDetailView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def get(self, request, recours_id: int):
        result = self.service.get_recours(recours_id)

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )

    def patch(self, request, recours_id: int):
        serializer = RecoursUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        dto = RecoursUpdateDTO(**serializer.validated_data)
        result = self.service.update_recours(recours_id, dto)
        self._audit_recours_change(
            request,
            "UPDATE_RECOURS",
            result.id_recours,
            {"updated_fields": list(serializer.validated_data.keys()), "statut": result.statut},
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )

    def delete(self, request, recours_id: int):
        self.service.delete_recours(recours_id)
        self._audit_recours_change(
            request,
            "CANCEL_RECOURS",
            recours_id,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------
# WORKFLOW VIEWS
# ---------------------------

class RecoursInstruireView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        result = self.service.instruire_recours(recours_id)
        self._audit_recours_change(
            request,
            "INSTRUIRE_RECOURS",
            result.id_recours,
            {"statut": result.statut},
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )


class RecoursDecisionView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        serializer = RecoursDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = RecoursDecisionDTO(**serializer.validated_data)

        result = self.service.prendre_decision(recours_id, dto)
        self._audit_recours_change(
            request,
            "DECISION_RECOURS",
            result.id_recours,
            {
                "statut": result.statut,
                "traite_par": result.traite_par,
                "decision": result.decision,
            },
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )


class RecoursAccepterView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        result = self.service.accepter_recours(recours_id)
        self._audit_recours_change(
            request,
            "ACCEPTER_RECOURS",
            result.id_recours,
            {"statut": result.statut},
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )


class RecoursRejeterView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        result = self.service.rejeter_recours(recours_id)
        self._audit_recours_change(
            request,
            "REJETER_RECOURS",
            result.id_recours,
            {"statut": result.statut},
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )


class RecoursCloturerView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        result = self.service.cloturer_recours(recours_id)
        self._audit_recours_change(
            request,
            "CLOTURE_RECOURS",
            result.id_recours,
            {"statut": result.statut},
        )

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )
