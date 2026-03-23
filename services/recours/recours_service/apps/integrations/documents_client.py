from .base_client import BaseHttpClient


class DocumentsClient(BaseHttpClient):

    def create_document(self, data: dict):
        return self._post("/documents", data)

    def get_document(self, document_id: int):
        return self._get(f"/documents/{document_id}")

    def get_download_url(self, document_id: int):
        return self._get(f"/documents/{document_id}/download-url")

    def get_documents_by_related(self, related_type: str, related_id: int):
        return self._get(f"/documents/by-related/{related_type}/{related_id}")

    def update_document(self, document_id: int, data: dict):
        return self._patch(f"/documents/{document_id}", data)