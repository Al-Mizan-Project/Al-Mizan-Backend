from rest_framework import serializers
from documents_service.models import Document

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'id_document', 'related_type', 'nom', 'type_document', 
            'storage_url', 'hash_sha256', 'taille_fichier', 'is_encrypted', 
            'ia_verif_statut', 'ia_verif_details', 'uploaded_at', 'visible_after'
        ]
        read_only_fields = ['id_document', 'storage_url', 'hash_sha256', 'taille_fichier', 'uploaded_at']

class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=False)
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=False
    )
    related_type = serializers.CharField(max_length=50, required=True)
    is_encrypted = serializers.BooleanField(default=False)
    visible_after = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        if not data.get('file') and not data.get('files'):
            raise serializers.ValidationError("You must provide either 'file' (single) or 'files' (bulk).")
        return data

class DocumentMetadataUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['ia_verif_statut', 'ia_verif_details']
