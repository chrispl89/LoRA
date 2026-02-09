"""
Model version endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.api.dependencies import get_db
from app.db import models

router = APIRouter()


class ModelVersionResponse(BaseModel):
    id: int
    model_id: int
    version_number: int
    base_model_name: str
    trigger_token: str
    train_config_json: Optional[dict] = None
    artifact_s3_prefix: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{version_id}", response_model=ModelVersionResponse)
def get_model_version(version_id: int, db: Session = Depends(get_db)):
    """
    Get model version details.

    This endpoint matches the required API spec:
    GET /v1/model-versions/{id}
    """
    version = db.query(models.ModelVersion).filter(models.ModelVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")
    return version

