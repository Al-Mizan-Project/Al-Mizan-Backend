from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import AuditLogReadSerializer

from .services import AuditReadService


class AuditListView(APIView):
    # permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AuditReadService()

    def get(self, request):
        filters = {
            key: request.query_params.get(key)
            for key in [
                "utilisateur_id",
                "entite_type",
                "entite_id",
                "date_from",
                "date_to",
            ]
            if request.query_params.get(key) is not None
        }

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        result = self.service.list_logs(filters, page, page_size)
        
        serializer = AuditLogReadSerializer(result["items"], many=True)
        result["items"] = serializer.data

        return Response(result, status=status.HTTP_200_OK)


class AuditDetailView(APIView):
    # permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AuditReadService()

    def get(self, request, log_id: int):
        log = self.service.get_log(log_id)

        if not log:
            return Response(
                {"error": "Not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        serializer = AuditLogReadSerializer(log)

        return Response(serializer.data, status=status.HTTP_200_OK)


class AuditByUserView(APIView):
    # permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AuditReadService()

    def get(self, request, user_id: int):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        result = self.service.get_logs_by_user(user_id, page, page_size)
        
        serializer = AuditLogReadSerializer(result["items"], many=True)
        result["items"] = serializer.data

        return Response(result, status=status.HTTP_200_OK)


class AuditByEntityView(APIView):
    # permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AuditReadService()

    def get(self, request, entite_type: str, entite_id: int):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        result = self.service.get_logs_by_entity(
            entite_type,
            entite_id,
            page,
            page_size,
        )
        
        serializer = AuditLogReadSerializer(result["items"], many=True)
        result["items"] = serializer.data

        return Response(result, status=status.HTTP_200_OK)