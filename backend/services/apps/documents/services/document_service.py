from typing import List

from apps.common.exceptions import ConflictException, NotFoundException
from apps.integrations.documents_client import DocumentsClient
from apps.recours.domain.entities.document_recours import DocumentRecours
from apps.recours.infrastructure.models.document_recours_model import DocumentRecoursModel


class DocumentService:

    def __init__(self, documents_client: DocumentsClient):
        self.documents_client = documents_client

    # ---------------------------
    # ATTACH DOCUMENT
    # ---------------------------

    def attach_document(self, recours_id: int, document_id: int) -> DocumentRecours:

        # 1. Validate document exists in external service
        document = self.documents_client.get_document(document_id)

        if not document:
            raise NotFoundException("Document introuvable")

        # 2. Check if already linked
        exists = DocumentRecoursModel.objects.filter(
            id_recours=recours_id,
            id_document=document_id
        ).exists()

        if exists:
            raise ConflictException("Document déjà attaché à ce recours")

        # 3. Persist relation
        model = DocumentRecoursModel.objects.create(
            id_recours=recours_id,
            id_document=document_id
        )

        # 4. Return domain entity
        return DocumentRecours(
            id_recours=model.id_recours,
            id_document=model.id_document
        )

    # ---------------------------
    # DETACH DOCUMENT
    # ---------------------------

    def detach_document(self, recours_id: int, document_id: int):

        deleted, _ = DocumentRecoursModel.objects.filter(
            id_recours=recours_id,
            id_document=document_id
        ).delete()

        if deleted == 0:
            raise NotFoundException("Lien document-recours introuvable")

    # ---------------------------
    # LIST DOCUMENTS
    # ---------------------------

    def list_documents(self, recours_id: int) -> List[dict]:

        relations = DocumentRecoursModel.objects.filter(
            id_recours=recours_id
        )

        document_ids = [r.id_document for r in relations]

        # Fetch documents from external service
        documents = []

        for doc_id in document_ids:
            doc = self.documents_client.get_document(doc_id)
            if doc:
                documents.append(doc)

        return documents

    # ---------------------------
    # GET DOCUMENT IDS ONLY (optional helper)
    # ---------------------------

    def list_document_ids(self, recours_id: int) -> List[int]:
        return list(
            DocumentRecoursModel.objects.filter(
                id_recours=recours_id
            ).values_list("id_document", flat=True)
        )
