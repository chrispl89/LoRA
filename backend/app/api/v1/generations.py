"""
Generation endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
from app.api.dependencies import get_db
from app.db import models
from app.services.s3 import s3_service
from app.core.guardrails import check_prompt_safety
from app.core.logging import get_logger
from app.workers.gpu.tasks import generate_image_task

logger = get_logger(__name__)
router = APIRouter()


class GenerationCreate(BaseModel):
    model_version_id: int
    prompt: str = Field(..., min_length=1, max_length=1000)
    negative_prompt: Optional[str] = Field(None, max_length=1000)
    steps: int = Field(default=50, ge=1, le=100)
    width: int = Field(default=512, ge=256, le=1024)
    height: int = Field(default=512, ge=256, le=1024)
    seed: Optional[int] = Field(None, ge=0)


class GenerationResponse(BaseModel):
    id: int
    model_version_id: int
    prompt: str
    negative_prompt: Optional[str]
    steps: int
    width: int
    height: int
    seed: Optional[int]
    status: str
    output_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
def create_generation(gen_data: GenerationCreate, db: Session = Depends(get_db)):
    """Create generation job."""
    # Check model version exists and is completed
    model_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == gen_data.model_version_id
    ).first()
    
    if not model_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    
    if model_version.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Model version is not ready (status: {model_version.status})"
        )
    
    # Check prompt safety (guardrails)
    is_safe, violations = check_prompt_safety(gen_data.prompt, gen_data.negative_prompt or "")
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Prompt contains blocked keywords",
                "violations": violations
            }
        )
    
    # Create generation
    generation = models.Generation(
        model_version_id=gen_data.model_version_id,
        prompt=gen_data.prompt,
        negative_prompt=gen_data.negative_prompt,
        steps=gen_data.steps,
        width=gen_data.width,
        height=gen_data.height,
        seed=gen_data.seed,
        status="pending"
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    
    # Create job
    job = models.Job(
        job_type="generate",
        status="pending",
        generation_id=generation.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Queue generation task
    task = generate_image_task.delay(generation.id)
    job.celery_task_id = task.id
    db.commit()
    
    logger.info("generation_created", generation_id=generation.id)
    
    return generation


@router.get("/{generation_id}", response_model=GenerationResponse)
def get_generation(generation_id: int, db: Session = Depends(get_db)):
    """Get generation status and result."""
    generation = db.query(models.Generation).filter(
        models.Generation.id == generation_id
    ).first()
    
    if not generation:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    # Generate presigned URLs if available
    output_url = None
    thumbnail_url = None
    
    if generation.output_s3_key:
        output_url = s3_service.generate_presigned_get_url(generation.output_s3_key)
    
    if generation.thumbnail_s3_key:
        thumbnail_url = s3_service.generate_presigned_get_url(generation.thumbnail_s3_key)
    
    # Convert to response model
    response = GenerationResponse(
        id=generation.id,
        model_version_id=generation.model_version_id,
        prompt=generation.prompt,
        negative_prompt=generation.negative_prompt,
        steps=generation.steps,
        width=generation.width,
        height=generation.height,
        seed=generation.seed,
        status=generation.status,
        output_url=output_url,
        thumbnail_url=thumbnail_url,
        error_message=generation.error_message,
        created_at=generation.created_at
    )
    
    return response
