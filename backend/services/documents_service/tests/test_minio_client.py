import io
import zipfile
import hashlib
from unittest.mock import patch, MagicMock
from django.test import TestCase
from documents_service.services.minio_client import MinioStorageService

class MinioStorageServiceTest(TestCase):

    @patch('documents_service.services.minio_client.boto3.client')
    def test_stream_upload_and_hash(self, mock_boto_client):
        service = MinioStorageService()
        fake_content = b"This is a fake document content for unit testing."
        expected_hash = hashlib.sha256(fake_content).hexdigest()
        fake_file_stream = io.BytesIO(fake_content)
        calculated_hash = service.stream_upload_and_hash(fake_file_stream, "test-uuid.txt")
        self.assertEqual(calculated_hash, expected_hash)
        mock_boto_client().upload_fileobj.assert_called_once()
        
    @patch('documents_service.services.minio_client.boto3.client')
    def test_stream_zip_downloads(self, mock_boto_client):
        # Mock the S3 get_object response
        mock_response_file1 = {'Body': MagicMock()}
        mock_response_file1['Body'].read.return_value = b"Content 1"
        
        mock_response_file2 = {'Body': MagicMock()}
        mock_response_file2['Body'].read.return_value = b"Content 2"
        
        # Configure the mock to return different files on successive calls
        mock_boto_client().get_object.side_effect = [mock_response_file1, mock_response_file2]
        
        service = MinioStorageService()
        docs_to_zip = [("uuid-1.txt", "file1.txt"), ("uuid-2.txt", "file2.txt")]
        
        # Consume the generator into a single bytes object
        zip_bytes = b"".join(list(service.stream_zip_downloads(docs_to_zip)))
        
        # Validate the resulting ZIP file
        zip_io = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(zip_io, 'r') as zf:
            self.assertListEqual(zf.namelist(), ["file1.txt", "file2.txt"])
            self.assertEqual(zf.read("file1.txt"), b"Content 1")
            self.assertEqual(zf.read("file2.txt"), b"Content 2")
            
        self.assertEqual(mock_boto_client().get_object.call_count, 2)
