from rest_framework import serializers
from .models import ComissionEvaluation, MembresCommissionEvaluation, Evaluation

class ComissionEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComissionEvaluation
        fields = '__all__'

class MembresCommissionEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembresCommissionEvaluation
        fields = '__all__'

class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = '__all__'
