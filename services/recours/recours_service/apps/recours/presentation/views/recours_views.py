from rest_framework.views import APIView


class RecoursCreateView(APIView):
    def post(self, request): ...


class RecoursListView(APIView):
    def get(self, request): ...


class RecoursDetailView(APIView):
    def get(self, request, recours_id: int): ...
    def delete(self, request, recours_id: int): ...


class RecoursInstruireView(APIView):
    def post(self, request, recours_id: int): ...


class RecoursDecisionView(APIView):
    def post(self, request, recours_id: int): ...


class RecoursAccepterView(APIView):
    def post(self, request, recours_id: int): ...


class RecoursRejeterView(APIView):
    def post(self, request, recours_id: int): ...


class RecoursCloturerView(APIView):
    def post(self, request, recours_id: int): ...