from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import AuditLedgerService


class CreateAuditLogView(APIView):
    """
    POST /journaux-audit
    Internal service endpoint.
    """

    # permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AuditLedgerService()

    def post(self, request):
        required_fields = [
            "utilisateur_id",
            "action",
            "entite_type",
            "entite_id",
        ]

        for field in required_fields:
            if field not in request.data:
                return Response(
                    {"error": f"{field} is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        log_id = self.service.log_event(request.data)

        return Response(
            {"log_id": log_id},
            status=status.HTTP_201_CREATED,
        )