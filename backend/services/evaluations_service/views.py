import os
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg

from .models import ComissionEvaluation, MembresCommissionEvaluation, Evaluation
from .serializers import EvaluationSerializer

class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})

class ReadyView(APIView):
    def get(self, request):
        return Response({"status": "ready"})


class EvaluationView(APIView):
    """
    GET  / - Récupérer toutes les évaluations
    POST / - Un membre crée une évaluation pour une soumission
    """
    def get(self, request):
        evaluations = Evaluation.objects.all()
        
        # ── Service Isolation (ADDITION) ────────────────────────────────
        auth_header = request.headers.get("Authorization")
        if auth_header:
            headers = {"Authorization": auth_header}
            url = f"{settings.CONTRACTANT_SERVICE_URL}/my-service"
            try:
                resp = requests.get(url, headers=headers, timeout=3)
                if resp.status_code == 200:
                    service_id = resp.json().get("id_service")
                    if service_id:
                        evaluations = evaluations.filter(id_comission__id_service=service_id)
            except Exception:
                pass
        # ───────────────────────────────────────────────────────────────

        serializer = EvaluationSerializer(evaluations, many=True)
        return Response(serializer.data)

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
        evaluation = self.get_object(evaluation_id)
        if not evaluation:
            return Response({"error": "Évaluation non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        serializer = EvaluationSerializer(evaluation)
        return Response(serializer.data)

    def patch(self, request, evaluation_id):
        evaluation = self.get_object(evaluation_id)
        if not evaluation:
            return Response({"error": "Évaluation non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        serializer = EvaluationSerializer(evaluation, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, evaluation_id):
        evaluation = self.get_object(evaluation_id)
        if not evaluation:
            return Response({"error": "Évaluation non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        evaluation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SoumissionEvaluationsView(APIView):
    def get(self, request, soumission_id):
        evaluations = Evaluation.objects.filter(id_soumission=soumission_id)
        serializer = EvaluationSerializer(evaluations, many=True)
        return Response(serializer.data)


class AppelOffreEvaluationsView(APIView):
    def get(self, request, appel_id):
        id_comission = request.query_params.get("id_comission")
        if not id_comission:
            return Response({"error": "id_comission requis dans les paramètres URL"}, status=status.HTTP_400_BAD_REQUEST)
        
        evaluations = Evaluation.objects.filter(id_comission=id_comission)
        serializer = EvaluationSerializer(evaluations, many=True)
        return Response(serializer.data)


class CalculerClassementView(APIView):
    def post(self, request, appel_id):
        id_comission = request.data.get("id_comission")
        if not id_comission:
            return Response({"error": "id_comission requis"}, status=status.HTTP_400_BAD_REQUEST)

        evaluations = Evaluation.objects.filter(id_comission=id_comission)
        if not evaluations.exists():
            return Response({"error": "Aucune évaluation trouvée pour cette commission"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            moyennes = evaluations.values('id_soumission').annotate(moyenne=Avg('note')).order_by('-moyenne')
            return Response({"classement": list(moyennes)})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClassementView(APIView):
    def get(self, request, appel_id):
        id_comission = request.query_params.get("id_comission")
        if not id_comission:
            return Response({"error": "id_comission requis dans les paramètres URL"}, status=status.HTTP_400_BAD_REQUEST)

        evaluations = Evaluation.objects.filter(id_comission=id_comission)
        if not evaluations.exists():
            return Response({"error": "Aucune évaluation trouvée pour cette commission"}, status=status.HTTP_404_NOT_FOUND)
        
        moyennes = evaluations.values('id_soumission').annotate(moyenne=Avg('note')).order_by('-moyenne')
        return Response({"classement": list(moyennes)})


class ValiderNotesView(APIView):
    def post(self, request, appel_id):
        id_comission = request.data.get("id_comission")
        if not id_comission:
            return Response({"error": "id_comission requis"}, status=status.HTTP_400_BAD_REQUEST)

        evaluations = Evaluation.objects.filter(id_comission=id_comission)
        if not evaluations.exists():
            return Response({"error": "Aucune évaluation trouvée pour cette commission"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({"message": "Notes validées avec succès pour la commission", "id_comission": id_comission})

