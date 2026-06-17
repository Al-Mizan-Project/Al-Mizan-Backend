import uuid
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db import models
from .models import Document
from .serializers import DocumentSerializer, DocumentUploadSerializer, DocumentMetadataUpdateSerializer
from .services.minio_client import MinioStorageService
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiResponse

class DocumentFilterMixin:
    """
    OOP mixin for consistent document filtering rules.
    Allows searching and downloading bulk documents exactly by the same criteria.
    """
    def get_filtered_queryset(self, request):
        queryset = Document.objects.all()
        ids = request.query_params.get('ids')
        related_type = request.query_params.get('related_type')
        id_operateur_economique = request.query_params.get('id_operateur_economique')
        ia_verif_statut = request.query_params.get('ia_verif_statut')
        is_encrypted = request.query_params.get('is_encrypted')
        type_document = request.query_params.get('type_document')
        min_size = request.query_params.get('min_size')
        max_size = request.query_params.get('max_size')

        if ids:
            parsed_ids = []
            for value in ids.split(','):
                value = value.strip()
                if value.isdigit():
                    parsed_ids.append(int(value))
            if parsed_ids:
                queryset = queryset.filter(id_document__in=parsed_ids)
            else:
                return queryset.none()
        
        if related_type:
            queryset = queryset.filter(related_type=related_type)
        if id_operateur_economique and id_operateur_economique.isdigit():
            queryset = queryset.filter(id_operateur_economique=int(id_operateur_economique))
        if ia_verif_statut:
            queryset = queryset.filter(ia_verif_statut=ia_verif_statut)
        if type_document:
            queryset = queryset.filter(type_document__iexact=type_document)
        if min_size and min_size.isdigit():
            queryset = queryset.filter(taille_fichier__gte=int(min_size))
        if max_size and max_size.isdigit():
            queryset = queryset.filter(taille_fichier__lte=int(max_size))
        if is_encrypted is not None:
            is_enc_bool = is_encrypted.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_encrypted=is_enc_bool)
            
        # Temporal visibility: Hide if visible_after is in the future
        now = timezone.now()
        queryset = queryset.filter(models.Q(visible_after__isnull=True) | models.Q(visible_after__lte=now))
            
        return queryset

class DocumentUploadView(views.APIView):
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        summary="Upload Document(s)",
        description="""Uploads a single document or bulk documents to the GED system.
        Files are dynamically calculated for SHA-256 and securely streamed to MinIO.
        - Pass `file` for a single upload.
        - Pass `files` multiple times for bulk parallel uploads.""",
        request=DocumentUploadSerializer,
        responses={
            201: DocumentSerializer(many=True),
            207: OpenApiResponse(response=DocumentSerializer, description="Multi-Status (Some uploads failed, some succeeded)"),
            400: OpenApiResponse(description="Bad Request / Invalid Validation")
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        related_type = serializer.validated_data['related_type']
        explicit_type_document = serializer.validated_data.get('type_document', None)
        id_operateur_economique = serializer.validated_data.get('id_operateur_economique', None)
        is_encrypted = serializer.validated_data.get('is_encrypted', False)
        visible_after = serializer.validated_data.get('visible_after', None)
        
        is_bulk = 'files' in request.FILES
        uploaded_files = request.FILES.getlist('files') if is_bulk else [request.FILES.get('file')]
        uploaded_files = [f for f in uploaded_files if f]

        if not uploaded_files:
            return Response({"error": "No files found in the request."}, status=status.HTTP_400_BAD_REQUEST)

        minio_service = MinioStorageService()
        created_documents = []
        errors = []

        for uploaded_file in uploaded_files:
            taille_fichier = uploaded_file.size
            original_filename = uploaded_file.name
            extension = original_filename.split('.')[-1].lower() if '.' in original_filename else 'bin'
            
            # Generate unique storage name
            unique_obj_name = f"{uuid.uuid4()}.{extension}"
            storage_url = f"{minio_service.bucket}/{unique_obj_name}"

            # Stream upload directly to MinIO and calculate SHA-256 on the fly
            try:
                sha256_hash = minio_service.stream_upload_and_hash(uploaded_file, unique_obj_name)
                
                # Save metadata to database
                # Use explicit type_document if provided, otherwise use file extension
                final_type_document = explicit_type_document or extension
                document = Document.objects.create(
                    related_type=related_type,
                    id_operateur_economique=id_operateur_economique,
                    nom=original_filename,
                    type_document=final_type_document,
                    storage_url=storage_url,
                    hash_sha256=sha256_hash,
                    taille_fichier=taille_fichier,
                    is_encrypted=is_encrypted,
                    visible_after=visible_after
                )
                created_documents.append(document)
            except Exception as e:
                errors.append({"filename": original_filename, "error": str(e)})

        if not created_documents and errors:
            return Response({"errors": errors}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data = DocumentSerializer(created_documents, many=True).data
        
        if is_bulk or len(response_data) != 1:
            if errors:
                return Response({"documents": response_data, "errors": errors}, status=status.HTTP_207_MULTI_STATUS)
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            if errors:
                return Response({"documents": response_data[0], "errors": errors}, status=status.HTTP_207_MULTI_STATUS)
            return Response(response_data[0], status=status.HTTP_201_CREATED)

class DocumentDownloadView(views.APIView):
    @extend_schema(
        summary="Download a Document",
        description="Initiates a direct streaming download of physically stored document bytes from MinIO via UUID.",
        responses={
            200: OpenApiResponse(response=OpenApiTypes.BINARY, description="File Stream"),
            403: OpenApiResponse(description="Forbidden - Document is not yet visible"),
            404: OpenApiResponse(description="Not Found - Document doesn't exist")
        }
    )
    def get(self, request, id_document, *args, **kwargs):
        document = get_object_or_404(Document, id_document=id_document)
        
        if document.visible_after and document.visible_after > timezone.now():
            return Response(
                {"error": "This document is not yet visible to the public."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        minio_service = MinioStorageService()
        
        # Extract the object key from the storage URL. Uploads persist
        # `storage_url = "{bucket}/{key}"`, so the bucket prefix must be stripped
        # to recover the real MinIO key (otherwise the bucket name is wrongly
        # included in the key and HeadObject 404s). Bare keys are left untouched.
        object_name = document.storage_url.lstrip('/')
        bucket_prefix = f"{minio_service.bucket}/"
        if object_name.startswith(bucket_prefix):
            object_name = object_name[len(bucket_prefix):]
        
        # Verify the file exists in MinIO BEFORE starting the stream.
        # get_file_stream is a generator so its body only runs when Django
        # iterates the StreamingHttpResponse – by then headers are already
        # sent and a failure would crash the socket instead of returning 404.
        try:
            minio_service.s3_client.head_object(
                Bucket=minio_service.bucket, Key=object_name
            )
        except Exception as e:
            return Response(
                {"error": f"File not found in storage: {str(e)}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            file_stream = minio_service.get_file_stream(object_name)
            # Serve with the real MIME type and inline disposition so the file can be
            # previewed directly (e.g. a PDF in an <iframe>) instead of being treated as
            # an opaque text/html download.
            doc_type = (document.type_document or '').strip().lower()
            if '/' in doc_type:
                content_type = doc_type
                ext = doc_type.rsplit('/', 1)[-1]
            else:
                ext = doc_type or document.nom.rsplit('.', 1)[-1].lower()
                content_type = {
                    'pdf': 'application/pdf',
                    'png': 'image/png',
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'webp': 'image/webp',
                }.get(ext, 'application/octet-stream')
            response = StreamingHttpResponse(file_stream, content_type=content_type)
            base_name = document.nom.rsplit('.', 1)[0] if '.' in document.nom else document.nom
            safe_filename = slugify(base_name) + '.' + ext
            response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)


class DocumentCollectionView(DocumentUploadView, DocumentFilterMixin):
    """
    Compatibility collection endpoint used by modules that expect
    `/documents` instead of `/api/documents/`.
    """

    def get(self, request, *args, **kwargs):
        queryset = self.get_filtered_queryset(request).order_by("-uploaded_at")
        serializer = DocumentSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DocumentDetailView(views.APIView):
    """
    Metadata-oriented compatibility endpoint used by existing inter-service
    clients. The binary payload remains available at `/api/documents/<id>/`.
    """

    def get(self, request, id_document, *args, **kwargs):
        document = get_object_or_404(Document, id_document=id_document)
        serializer = DocumentSerializer(document)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id_document, *args, **kwargs):
        document = get_object_or_404(Document, id_document=id_document)
        serializer = DocumentMetadataUpdateSerializer(document, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DocumentSerializer(document).data, status=status.HTTP_200_OK)

    def delete(self, request, id_document, *args, **kwargs):
        return DocumentDeleteView().delete(request, id_document, *args, **kwargs)


class DocumentDownloadUrlView(views.APIView):
    def get(self, request, id_document, *args, **kwargs):
        document = get_object_or_404(Document, id_document=id_document)
        download_url = request.build_absolute_uri(f"/api/documents/{document.id_document}/")
        return Response(
            {
                "id_document": document.id_document,
                "download_url": download_url,
                "storage_url": document.storage_url,
            },
            status=status.HTTP_200_OK,
        )

class DocumentBulkZipView(views.APIView, DocumentFilterMixin):
    @extend_schema(
        summary="Download Multiple Documents as ZIP",
        description="Streams a dynamic `.zip` file natively combining all documents matching your search queries or explicit IDs.",
        parameters=[
            OpenApiParameter('ids', OpenApiTypes.STR, description="Comma-separated IDs (e.g. 1,2,3). If omitted, filters combine everything."),
            OpenApiParameter('related_type', OpenApiTypes.STR, description="Filter by Document Type (e.g. soumission)"),
            OpenApiParameter('type_document', OpenApiTypes.STR, description="Filter by File extension (e.g. pdf)"),
            OpenApiParameter('ia_verif_statut', OpenApiTypes.STR, description="Filter by AI Status (e.g. VALID)"),
        ],
        responses={
            200: OpenApiResponse(response=OpenApiTypes.BINARY, description="ZIP Streaming Bytes"),
            404: OpenApiResponse(description="No files found to ZIP")
        }
    )
    def get(self, request, *args, **kwargs):
        document_ids = request.query_params.get('ids', '')
        if document_ids:
            id_list = [id.strip() for id in document_ids.split(',')]
            documents = Document.objects.filter(id_document__in=id_list)
        else:
            # Generate zip based on dynamic query parameters if no IDs provided
            documents = self.get_filtered_queryset(request)
        
        if not documents.exists():
            return Response({"error": "No documents found matching the criteria."}, status=status.HTTP_404_NOT_FOUND)
            
        docs_to_zip = []
        for doc in documents:
            object_name = doc.storage_url.split('/')[-1]
            safe_filename = slugify(doc.nom.replace('.' + doc.type_document, '')) + '.' + doc.type_document
            docs_to_zip.append((object_name, safe_filename))
            
        minio_service = MinioStorageService()
        
        try:
            zip_stream = minio_service.stream_zip_downloads(docs_to_zip)
            response = StreamingHttpResponse(zip_stream, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="documents_export.zip"'
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    summary="Update Document AI Metadata",
    description="Updates the internal AI verification status and details for an existing document asynchronously."
)
class DocumentMetadataPatchView(generics.UpdateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentMetadataUpdateSerializer
    lookup_field = 'id_document'

@extend_schema(
    summary="Search and Filter Documents",
    description="Returns a paginated list of documents matching specified search parameters in the database.",
    parameters=[
        OpenApiParameter('related_type', OpenApiTypes.STR, description="Filter by related type"),
        OpenApiParameter('id_operateur_economique', OpenApiTypes.INT, description="Filter by owner operator"),
        OpenApiParameter('ia_verif_statut', OpenApiTypes.STR, description="Filter by AI Status"),
        OpenApiParameter('type_document', OpenApiTypes.STR, description="Filter by file extension (e.g. pdf)"),
        OpenApiParameter('min_size', OpenApiTypes.INT, description="Minimum size in bytes"),
        OpenApiParameter('max_size', OpenApiTypes.INT, description="Maximum size in bytes"),
        OpenApiParameter('is_encrypted', OpenApiTypes.BOOL, description="Is Encrypted Filter"),
    ]
)
class DocumentSearchView(generics.ListAPIView, DocumentFilterMixin):
    serializer_class = DocumentSerializer
    
    def get_queryset(self):
        return self.get_filtered_queryset(self.request)


class OperateurDocumentsView(views.APIView, DocumentFilterMixin):
    @extend_schema(
        summary="List Documents by Operateur Economique",
        description="Returns all documents owned by a specific operateur economique, with optional filtering.",
        parameters=[
            OpenApiParameter('related_type', OpenApiTypes.STR, description="Filter by related type"),
            OpenApiParameter('type_document', OpenApiTypes.STR, description="Filter by file extension"),
        ],
        responses={200: DocumentSerializer(many=True)},
    )
    def get(self, request, id_operateur, *args, **kwargs):
        queryset = self.get_filtered_queryset(request).filter(
            id_operateur_economique=id_operateur
        ).order_by("-uploaded_at")

        serializer = DocumentSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class DocumentDeleteView(views.APIView):
    @extend_schema(
        summary="Delete a Document",
        description="Physically purges the file payload from MinIO and deletes the database reference.",
        responses={
            204: OpenApiResponse(description="Successfully Deleted"),
            404: OpenApiResponse(description="Not Found")
        }
    )
    def delete(self, request, id_document, *args, **kwargs):
        document = get_object_or_404(Document, id_document=id_document)
        minio_service = MinioStorageService()
        object_name = document.storage_url.split('/')[-1]
        
        try:
            minio_service.delete_file(object_name)
        except Exception as e:
            # Depending on business logic, you might still want to delete the DB record
            # even if MinIO fails, or you might want to raise an error.
            print(f"Failed to delete from MinIO, orphan file may exist: {str(e)}")
            
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
