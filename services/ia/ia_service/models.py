from django.db import models


class DetectionAnomalieIA(models.Model):
    id_detection_anomalie_ia = models.AutoField(primary_key=True)
    id_appel_offre = models.IntegerField()
    id_soumission = models.IntegerField()
    type_anomalie = models.CharField(max_length=50)
    niveau_severite = models.CharField(max_length=20)
    score_confiance = models.DecimalField(max_digits=5, decimal_places=2)
    details = models.TextField(blank=True, default="")
    statut_examen = models.CharField(max_length=30, default="A_REVOIR")
    date_detection = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "detection_anomalie_ia"
        ordering = ["-date_detection", "-id_detection_anomalie_ia"]