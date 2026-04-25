from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.common.exceptions import ApplicationException
from apps.recours.domain.exceptions import RecoursException
from apps.recours.application.dto.recours_dto import (
    RecoursCreateDTO,
    RecoursDecisionDTO,
)
from apps.recours.application.services.recours_service import RecoursService
from apps.recours.presentation.serializers.recours_serializers import (
    RecoursCreateSerializer,
    RecoursDecisionSerializer,
    RecoursResponseSerializer,
)


class BaseAPIView(APIView):
    service: RecoursService | None = None

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

    def delete(self, request, recours_id: int):
        self.service.delete_recours(recours_id)

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

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )


class RecoursAccepterView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        result = self.service.accepter_recours(recours_id)

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )


class RecoursRejeterView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        result = self.service.rejeter_recours(recours_id)

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )


class RecoursCloturerView(BaseAPIView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service: RecoursService = kwargs.get("service")

    def post(self, request, recours_id: int):
        result = self.service.cloturer_recours(recours_id)

        return Response(
            RecoursResponseSerializer(result.__dict__).data
        )
