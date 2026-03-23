from django.db import models
from .recours_model import RecoursModel


class DocumentRecoursModel(models.Model):
    """Model for Document Recours"""
    recours = models.ForeignKey(RecoursModel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'recours'
