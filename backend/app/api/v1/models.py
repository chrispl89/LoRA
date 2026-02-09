"""
Model endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
from app.api.dependencies import get_db
from app.db import models
from app.core.guardrails import validate_consent
from app.core.logging import get_logger
from app.workers.gpu.tasks import train_model_task

logger = get_logger(__name__)
router = APIRouter()


class ModelCreate(BaseModel):
    person_id: int
    name: str = Field(..., min_length=1, max_length=255)
    # In offline runtime this should point to a local alias (e.g. "sd15") or local dir.
    base_model_name: str = Field(default="sd15")
    trigger_token: str = Field(..., min_length=1, max_length=100)
    train_config: Optional[dict] = None


class ModelResponse(BaseModel):
    id: int
    person_id: int
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ModelVersionResponse(BaseModel):
    id: int
    model_id: int
    version_number: int
    base_model_name: str
    trigger_token: str
    train_config_json: Optional[dict]
    artifact_s3_prefix: Optional[str]
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ModelDetailResponse(ModelResponse):
    versions: List[ModelVersionResponse]


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
def create_model(model_data: ModelCreate, db: Session = Depends(get_db)):
    """Create model and start training."""
    # Check person exists
    person = db.query(models.PersonProfile).filter(
        models.PersonProfile.id == model_data.person_id,
        models.PersonProfile.deleted_at.is_(None)
    ).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Validate consent
    is_valid, error_msg = validate_consent(person.consent_confirmed, person.subject_is_adult)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot train model: {error_msg}"
        )
    
    # Check if preprocessed dataset exists
    preprocess_run = db.query(models.PreprocessRun).filter(
        models.PreprocessRun.person_id == model_data.person_id,
        models.PreprocessRun.status == "finished"
    ).order_by(models.PreprocessRun.created_at.desc()).first()
    
    if not preprocess_run:
        raise HTTPException(
            status_code=400,
            detail="No preprocessed dataset found. Run preprocessing first."
        )
    
    # Create model
    db_model = models.Model(
        person_id=model_data.person_id,
        name=model_data.name
    )
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    
    # Create model version
    model_version = models.ModelVersion(
        model_id=db_model.id,
        version_number=1,
        base_model_name=model_data.base_model_name,
        trigger_token=model_data.trigger_token,
        train_config_json=model_data.train_config or {},
        status="pending"
    )
    db.add(model_version)
    db.commit()
    db.refresh(model_version)
    
    # Create job
    job = models.Job(
        job_type="train",
        status="pending",
        model_version_id=model_version.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Queue training task
    task = train_model_task.delay(model_version.id)
    job.celery_task_id = task.id
    db.commit()
    
    logger.info("model_created", model_id=db_model.id, version_id=model_version.id)
    
    return db_model


@router.get("", response_model=List[ModelResponse])
def list_models(
    skip: int = 0,
    limit: int = 100,
    person_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """List models."""
    query = db.query(models.Model).filter(models.Model.deleted_at.is_(None))
    
    if person_id:
        query = query.filter(models.Model.person_id == person_id)
    
    models_list = query.offset(skip).limit(limit).all()
    return models_list


@router.get("/{model_id}", response_model=ModelDetailResponse)
def get_model(model_id: int, db: Session = Depends(get_db)):
    """Get model with versions."""
    db_model = db.query(models.Model).filter(
        models.Model.id == model_id,
        models.Model.deleted_at.is_(None)
    ).first()
    
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return db_model


@router.get("/versions/{version_id}", response_model=ModelVersionResponse)
def get_model_version(version_id: int, db: Session = Depends(get_db)):
    """Get model version details."""
    version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")
    
    return version
