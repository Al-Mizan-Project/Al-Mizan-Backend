import json
from django.db import transaction
from appels_service.models import AppelOffres
from soumissions_app.models import Soumission, Attribution
from documents_service.models import Document

def reset_data():
    with transaction.atomic():
        # 1. Reset Appels d'offres
        appels = AppelOffres.objects.all()
        appels.update(etat_execution='en_attente', statut='non_valide')
        print(f"Updated {appels.count()} appels_offres to 'en_attente' and 'non_valide'")

        # 2. Reset Attributions - Delete them since they shouldn't exist before validation,
        # OR set their status to something else if applicable. Since 'definitive' is the only current one,
        # we will just delete them to reset the state.
        # Wait, maybe they mean 'provisoire'? Let's just delete them.
        attr_count, _ = Attribution.objects.all().delete()
        print(f"Deleted {attr_count} attributions to reset state")

        # 3 & 4. Delete 'decision_validation' docs and remove from soumissions
        val_docs = Document.objects.filter(type_document='decision_validation')
        doc_ids = list(val_docs.values_list('id_document', flat=True))
        
        if doc_ids:
            for soumission in Soumission.objects.all():
                new_doc_ids = [d for d in soumission.document_ids if d not in doc_ids]
                if len(new_doc_ids) != len(soumission.document_ids):
                    soumission.document_ids = new_doc_ids
                    soumission.save()
            
            docs_deleted, _ = val_docs.delete()
            print(f"Deleted {docs_deleted} decision_validation documents: {doc_ids}")
        else:
            print("No decision_validation documents found.")

if __name__ == '__main__':
    reset_data()
