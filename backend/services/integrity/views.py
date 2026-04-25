from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from .services import IntegrityService


class VerifyRecordView(APIView):
    # permission_classes = [IsAdminUser]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = IntegrityService()

    def get(self, request, record_id: int):
        result = self.service.verify_record(record_id)

        if "error" in result:
            return Response(result, status=status.HTTP_404_NOT_FOUND)

        return Response(result, status=status.HTTP_200_OK)


class VerifyFullChainView(APIView):
    # permission_classes = [IsAdminUser]

    def get(self, request):
        service = IntegrityService()
        result = service.verify_chain()

        return Response(result, status=status.HTTP_200_OK)