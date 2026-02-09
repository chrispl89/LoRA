from __future__ import annotations

from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os


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
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Upload limits
    MAX_PHOTO_SIZE_MB: int = 15
    MIN_PHOTOS: int = 3
    MAX_PHOTOS: int = 30
    
    # Presigned URLs
    PRESIGNED_URL_EXPIRATION_SECONDS: int = 3600

    # Hugging Face (required for downloading most Stable Diffusion base models)
    HUGGINGFACE_HUB_TOKEN: str | None = None

    # Project paths / offline runtime (HF used only as a downloader, not runtime)
    # If unset, PROJECT_ROOT is inferred from this file location.
    PROJECT_ROOT: str | None = None
    MODELS_DIR: str | None = None

    # Force offline in runtime (API/workers). This should be enabled in prod.
    HF_RUNTIME_OFFLINE: bool = True
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # GPU
    USE_GPU: bool = False
    CUDA_VISIBLE_DEVICES: str = "0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


def get_project_root() -> Path:
    """
    Resolve repository root (directory containing `backend/` and `frontend/`).

    Default: inferred from this file path; can be overridden by PROJECT_ROOT env.
    """
    if settings.PROJECT_ROOT:
        return Path(settings.PROJECT_ROOT).expanduser().resolve()

    # backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend, [3]=repo root
    return Path(__file__).resolve().parents[3]


def get_models_dir() -> Path:
    """Resolve root `models/` directory (repo-local by default)."""
    if settings.MODELS_DIR:
        return Path(settings.MODELS_DIR).expanduser().resolve()
    return get_project_root() / "models"
