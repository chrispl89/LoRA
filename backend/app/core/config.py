from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/lora_person"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "lora-person-data"
    MINIO_USE_SSL: bool = False
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    
    # Security
    JWT_SECRET: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS
    # Keep this as a STRING so pydantic-settings won't try to JSON-decode it as a complex type.
    # Supported formats:
    # - Comma-separated: http://localhost:3000,http://localhost:3001
    # - JSON list string: ["http://localhost:3000","http://localhost:3001"]
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    def cors_origins_list(self) -> List[str]:
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
        return [x.strip() for x in raw.split(",") if x.strip()]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Upload limits
    MAX_PHOTO_SIZE_MB: int = 15
    MIN_PHOTOS: int = 3
    MAX_PHOTOS: int = 30
    
    # Presigned URLs
    PRESIGNED_URL_EXPIRATION_SECONDS: int = 3600
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_ALWAYS_EAGER: bool = False
    
    # GPU
    USE_GPU: bool = False
    CUDA_VISIBLE_DEVICES: str = "0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
