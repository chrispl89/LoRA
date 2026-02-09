"""
MinIO / S3 client for object storage.

IMPORTANT: This module must NOT attempt to connect to MinIO at import time.
Otherwise the API and tests would crash when MinIO isn't running yet.
"""

from __future__ import annotations

from functools import lru_cache
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3Service:
    """S3-compatible storage service (MinIO)."""

    def __init__(self):
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(
                signature_version="s3v4",
                connect_timeout=2,
                read_timeout=5,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
            region_name="us-east-1",  # MinIO doesn't care about region
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Ensure bucket exists."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except EndpointConnectionError as e:
            logger.error("minio_unreachable", endpoint=settings.MINIO_ENDPOINT, error=str(e))
            raise RuntimeError(
                f"MinIO/S3 endpoint unreachable: {settings.MINIO_ENDPOINT}. "
                "Start MinIO and verify MINIO_ENDPOINT/MINIO_USE_SSL."
            ) from e
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
                logger.info("bucket_created", bucket=self.bucket_name)
            except Exception as e:
                logger.error("bucket_creation_failed", error=str(e))
                raise
    
    def generate_presigned_put_url(
        self, 
        key: str, 
        content_type: str,
        expiration: int = None
    ) -> dict:
        """
        Generate presigned URL for PUT upload.
        
        Returns:
            {
                "url": "...",
                "fields": {...},  # For POST form data
                "key": "..."
            }
        """
        expiration = expiration or settings.PRESIGNED_URL_EXPIRATION_SECONDS
        
        try:
            url = self.client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'ContentType': content_type,
                },
                ExpiresIn=expiration
            )
            return {
                "url": url,
                "method": "PUT",
                "key": key,
                "content_type": content_type
            }
        except Exception as e:
            logger.error("presigned_url_failed", error=str(e), key=key)
            raise
    
    def generate_presigned_get_url(
        self,
        key: str,
        expiration: int = None
    ) -> str:
        """Generate presigned URL for GET download."""
        expiration = expiration or settings.PRESIGNED_URL_EXPIRATION_SECONDS
        
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error("presigned_get_url_failed", error=str(e), key=key)
            raise
    
    def upload_file(self, local_path: str, s3_key: str, content_type: str = None):
        """Upload file from local path."""
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.client.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )
            logger.info("file_uploaded", key=s3_key)
        except Exception as e:
            logger.error("file_upload_failed", error=str(e), key=s3_key)
            raise
    
    def download_file(self, s3_key: str, local_path: str):
        """Download file to local path."""
        try:
            self.client.download_file(self.bucket_name, s3_key, local_path)
            logger.info("file_downloaded", key=s3_key)
        except Exception as e:
            logger.error("file_download_failed", error=str(e), key=s3_key)
            raise
    
    def delete_file(self, s3_key: str):
        """Delete file from S3."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info("file_deleted", key=s3_key)
        except Exception as e:
            logger.error("file_delete_failed", error=str(e), key=s3_key)
            raise
    
    def list_files(self, prefix: str) -> list:
        """List files with prefix."""
        try:
            keys: list[str] = []
            continuation: Optional[str] = None

            while True:
                kwargs = {"Bucket": self.bucket_name, "Prefix": prefix}
                if continuation:
                    kwargs["ContinuationToken"] = continuation

                response = self.client.list_objects_v2(**kwargs)
                keys.extend([obj["Key"] for obj in response.get("Contents", [])])

                if response.get("IsTruncated"):
                    continuation = response.get("NextContinuationToken")
                    if not continuation:
                        break
                else:
                    break

            return keys
        except Exception as e:
            logger.error("list_files_failed", error=str(e), prefix=prefix)
            return []
    
    def delete_prefix(self, prefix: str):
        """Delete all files with prefix."""
        keys = self.list_files(prefix)
        for key in keys:
            self.delete_file(key)
        logger.info("prefix_deleted", prefix=prefix, count=len(keys))


@lru_cache(maxsize=1)
def get_s3_service() -> S3Service:
    """Lazily create the S3 client (MinIO may not be up at import time)."""
    return S3Service()
