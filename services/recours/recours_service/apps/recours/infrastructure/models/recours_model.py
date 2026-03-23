from django.db import models


class RecoursModel(models.Model):
    """Model for Recours"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'recours'
