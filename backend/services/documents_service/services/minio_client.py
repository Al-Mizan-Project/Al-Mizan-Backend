import hashlib
import uuid
import boto3
import zipfile
import io
import socket
from urllib.parse import urlparse
from botocore.exceptions import ClientError
from botocore.client import Config
from django.conf import settings
from typing import Tuple, Generator

class MinioStorageService:
    def __init__(self):
        endpoint = settings.MINIO_URL
        if not endpoint.startswith('http'):
            endpoint = f'http://{endpoint}'
            
        try:
            parsed = urlparse(endpoint)
            # boto3 strictly validates DNS and crashes on underscores like 'minio_documents'
            ip = socket.gethostbyname(parsed.hostname)
            endpoint = endpoint.replace(parsed.hostname, ip)
        except Exception:
            pass # Fallback to original
            
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name='us-east-1', # Required by boto3 even for local MinIO
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
        )
        self.bucket = settings.MINIO_BUCKET_NAME

    def stream_upload_and_hash(self, file_stream, object_name: str) -> str:
        """
        Uploads a file stream directly to MinIO while calculating its SHA-256 hash.
        This prevents loading the entire file into memory.
        Returns the SHA-256 hex digest.
        """
        sha256_hash = hashlib.sha256()
        
        # We need to compute the hash manually *before* uploading 
        # because boto3's multipart upload reads the stream unpredictably in multiple threads.
        while chunk := file_stream.read(8192):
            sha256_hash.update(chunk)
            
        file_stream.seek(0)
        
        try:
            self.s3_client.upload_fileobj(file_stream, self.bucket, object_name)
        except ClientError as e:
            raise Exception(f"Failed to upload to MinIO: {str(e)}")
            
        return sha256_hash.hexdigest()

    def get_file_stream(self, object_name: str) -> Generator[bytes, None, None]:
        """
        Retrieves a file from MinIO as a data stream generator.
        Useful for feeding directly into a StreamingHttpResponse.
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=object_name)
            for chunk in response['Body'].iter_chunks(chunk_size=8192):
                yield chunk
        except ClientError as e:
            raise Exception(f"Failed to retrieve from MinIO: {str(e)}")

    def stream_zip_downloads(self, documents: list[Tuple[str, str]]) -> Generator[bytes, None, None]:
        """
        Takes a list of tuples: [(object_name_in_minio, desired_name_in_zip), ...]
        Streams the downloaded files directly into a ZIP archive without loading everything into memory.
        """
        # A virtual buffer that tricks zipfile into thinking it's writing to a continuous file
        # while we are actually stealing its bytes and resetting the internal buffer to keep RAM usage near 0.
        class VirtualZipBuffer:
            def __init__(self):
                self._buffer = bytearray()
                self._offset = 0

            def write(self, data):
                self._buffer.extend(data)
                self._offset += len(data)
                return len(data)

            def tell(self):
                return self._offset

            def flush(self):
                pass
                
            def pop_bytes(self):
                chunk = bytes(self._buffer)
                self._buffer.clear()
                return chunk

        stream_buffer = VirtualZipBuffer()
        
        with zipfile.ZipFile(stream_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for object_name, desired_name in documents:
                try:
                    response = self.s3_client.get_object(Bucket=self.bucket, Key=object_name)
                    # For a truly massive file, we would stream this read too, but writestr 
                    # requires the whole string. For true streaming, we'd use zipstream.
                    # Since documents are usually a few MBs, this is acceptable for the zip case.
                    zip_file.writestr(desired_name, response['Body'].read())
                    # Yield the chunks created for this file
                    yield stream_buffer.pop_bytes()
                except ClientError as e:
                    print(f"Skipping {object_name} due to MinIO error: {str(e)}")
                    
        # When the with block closes, ZipFile writes the central directory to the buffer
        yield stream_buffer.pop_bytes()

    def delete_file(self, object_name: str) -> bool:
        """
        Hard deletes a file from MinIO storage.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=object_name)
            return True
        except ClientError as e:
            raise Exception(f"Failed to delete from MinIO: {str(e)}")
