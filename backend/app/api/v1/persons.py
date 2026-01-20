"""
Person profile endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from datetime import datetime
from app.api.dependencies import get_db
from app.db import models
from app.services.s3 import s3_service
from app.core.config import settings
from app.core.guardrails import validate_consent
from app.core.logging import get_logger
from app.workers.cpu.tasks import preprocess_person_task
from app.workers.gpu.tasks import train_model_task, generate_image_task

logger = get_logger(__name__)
router = APIRouter()


class PersonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    consent_confirmed: bool = Field(..., description="Must be true")
    subject_is_adult: bool = Field(..., description="Must be true")


class PersonResponse(BaseModel):
    id: int
    name: str
    consent_confirmed: bool
    subject_is_adult: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PresignUploadRequest(BaseModel):
    filename: str
    content_type: str = Field(..., pattern="^(image/jpeg|image/png|image/webp)$")
    size_bytes: int = Field(..., gt=0, le=settings.MAX_PHOTO_SIZE_MB * 1024 * 1024)


class PresignUploadResponse(BaseModel):
    url: str
    method: str
    key: str
    content_type: str


class PhotoCompleteRequest(BaseModel):
    key: str
    content_type: str
    size_bytes: int


class PhotoResponse(BaseModel):
    id: int
    s3_key: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class PreprocessResponse(BaseModel):
    preprocess_run_id: int
    job_id: int
    status: str


@router.post("", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(person: PersonCreate, db: Session = Depends(get_db)):
    """Create person profile with consent validation."""
    # Validate consent
    is_valid, error_msg = validate_consent(person.consent_confirmed, person.subject_is_adult)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    db_person = models.PersonProfile(
        name=person.name,
        consent_confirmed=person.consent_confirmed,
        subject_is_adult=person.subject_is_adult
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    
    logger.info("person_created", person_id=db_person.id, name=person.name)
    return db_person


@router.get("", response_model=List[PersonResponse])
def list_persons(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List person profiles (excluding deleted)."""
    persons = db.query(models.PersonProfile).filter(
        models.PersonProfile.deleted_at.is_(None)
    ).offset(skip).limit(limit).all()
    return persons


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(person_id: int, db: Session = Depends(get_db)):
    """Get person profile."""
    person = db.query(models.PersonProfile).filter(
        models.PersonProfile.id == person_id,
        models.PersonProfile.deleted_at.is_(None)
    ).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    """Delete person data (soft delete + S3 cleanup)."""
    person = db.query(models.PersonProfile).filter(
        models.PersonProfile.id == person_id,
        models.PersonProfile.deleted_at.is_(None)
    ).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Soft delete
    person.deleted_at = func.now()
    db.commit()
    
    # Delete photos from S3
    photos = db.query(models.PhotoAsset).filter(
        models.PhotoAsset.person_id == person_id
    ).all()
    for photo in photos:
        try:
            s3_service.delete_file(photo.s3_key)
        except Exception as e:
            logger.error("photo_delete_failed", photo_id=photo.id, error=str(e))
    
    # Delete models from S3
    for model in person.models:
        for version in model.versions:
            if version.artifact_s3_prefix:
                s3_service.delete_prefix(version.artifact_s3_prefix)
    
    # Delete generations
    for model in person.models:
        for version in model.versions:
            for generation in version.generations:
                if generation.output_s3_key:
                    s3_service.delete_file(generation.output_s3_key)
                if generation.thumbnail_s3_key:
                    s3_service.delete_file(generation.thumbnail_s3_key)
    
    logger.info("person_deleted", person_id=person_id)
    return None


@router.post("/{person_id}/uploads/presign", response_model=PresignUploadResponse)
def presign_upload(person_id: int, request: PresignUploadRequest, db: Session = Depends(get_db)):
    """Generate presigned URL for photo upload."""
    # Check person exists
    person = db.query(models.PersonProfile).filter(
        models.PersonProfile.id == person_id,
        models.PersonProfile.deleted_at.is_(None)
    ).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Check photo count limit
    photo_count = db.query(models.PhotoAsset).filter(
        models.PhotoAsset.person_id == person_id,
        models.PhotoAsset.status != "rejected"
    ).count()
    
    if photo_count >= settings.MAX_PHOTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_PHOTOS} photos allowed"
        )
    
    # Generate S3 key
    s3_key = f"uploads/{person_id}/{request.filename}"
    
    # Generate presigned URL
    presigned_data = s3_service.generate_presigned_put_url(
        key=s3_key,
        content_type=request.content_type
    )
    
    return presigned_data


@router.post("/{person_id}/photos/complete", response_model=PhotoResponse, status_code=status.HTTP_201_CREATED)
def complete_photo_upload(person_id: int, request: PhotoCompleteRequest, db: Session = Depends(get_db)):
    """Register uploaded photo."""
    # Check person exists
    person = db.query(models.PersonProfile).filter(
        models.PersonProfile.id == person_id,
        models.PersonProfile.deleted_at.is_(None)
    ).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Check if key exists in S3 (basic validation)
    # In production, verify file actually exists
    
    # Create photo record
    photo = models.PhotoAsset(
        person_id=person_id,
        s3_key=request.key,
        content_type=request.content_type,
        size_bytes=request.size_bytes,
        status="uploaded"
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    
    logger.info("photo_registered", photo_id=photo.id, person_id=person_id)
    return photo


@router.get("/{person_id}/photos", response_model=List[PhotoResponse])
def list_photos(person_id: int, db: Session = Depends(get_db)):
    """List photos for a person."""
    person = db.query(models.PersonProfile).filter(
        models.PersonProfile.id == person_id,
        models.PersonProfile.deleted_at.is_(None)
    ).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    photos = db.query(models.PhotoAsset).filter(
        models.PhotoAsset.person_id == person_id
    ).order_by(models.PhotoAsset.created_at.desc()).all()
    
    return photos


@router.get("/{person_id}/photos/{photo_id}/url")
def get_photo_url(person_id: int, photo_id: int, db: Session = Depends(get_db)):
    """Get presigned URL for photo."""
    photo = db.query(models.PhotoAsset).filter(
        models.PhotoAsset.id == photo_id,
        models.PhotoAsset.person_id == person_id
    ).first()
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    url = s3_service.generate_presigned_get_url(photo.s3_key)
    return {"url": url}


@router.post("/{person_id}/preprocess", response_model=PreprocessResponse)
def start_preprocess(person_id: int, db: Session = Depends(get_db)):
    """Start preprocessing job."""
    # Check person exists
    person = db.query(models.PersonProfile).filter(
        models.PersonProfile.id == person_id,
        models.PersonProfile.deleted_at.is_(None)
    ).first()
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Validate consent
    is_valid, error_msg = validate_consent(person.consent_confirmed, person.subject_is_adult)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot preprocess: {error_msg}"
        )
    
    # Check photo count
    photo_count = db.query(models.PhotoAsset).filter(
        models.PhotoAsset.person_id == person_id,
        models.PhotoAsset.status == "uploaded"
    ).count()
    
    if photo_count < settings.MIN_PHOTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum {settings.MIN_PHOTOS} photos required"
        )
    
    # Create preprocess run
    preprocess_run = models.PreprocessRun(
        person_id=person_id,
        status="pending"
    )
    db.add(preprocess_run)
    db.commit()
    db.refresh(preprocess_run)
    
    # Create job
    job = models.Job(
        job_type="preprocess",
        status="pending",
        preprocess_run_id=preprocess_run.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Queue Celery task
    task = preprocess_person_task.delay(person_id, preprocess_run.id)
    job.celery_task_id = task.id
    db.commit()
    
    logger.info("preprocess_started", person_id=person_id, run_id=preprocess_run.id)
    
    return {
        "preprocess_run_id": preprocess_run.id,
        "job_id": job.id,
        "status": "pending"
    }
