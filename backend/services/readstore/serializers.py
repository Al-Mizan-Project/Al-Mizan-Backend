from rest_framework import serializers
from .models import AuditLogRead

class AuditLogReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLogRead
        fields = '__all__'