from django.db import models


class DocumentRecoursModel(models.Model):

    id = models.AutoField(primary_key=True)
    id_recours = models.IntegerField()
    id_document = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "documents_recours"
        unique_together = ("id_recours", "id_document")

    def __str__(self):
        return f"Recours {self.id_recours} -> Document {self.id_document}"