from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class RecoursCreateView(APIView):
    def post(self, request): return None


class RecoursListView(APIView):
    def get(self, request): return None


class RecoursDetailView(APIView):
    def get(self, request, recours_id: int): return None
    def delete(self, request, recours_id: int): return None

class RecoursInstruireView(APIView):
    def post(self, request, recours_id: int): return None


class RecoursDecisionView(APIView):
    def post(self, request, recours_id: int): return None

class RecoursAccepterView(APIView):
    def post(self, request, recours_id: int): return None


class RecoursRejeterView(APIView):
    def post(self, request, recours_id: int): return None


class RecoursCloturerView(APIView):
    def post(self, request, recours_id: int): return None