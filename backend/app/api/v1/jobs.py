"""
Job endpoints (progress/log output).
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db import models

router = APIRouter()


class JobEventResponse(BaseModel):
    id: int
    job_id: int
    event_type: str
    message: str
    metadata_json: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/model-versions/{version_id}/events", response_model=List[JobEventResponse])
def list_events_for_model_version(
    version_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    version = db.query(models.ModelVersion).filter(models.ModelVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    job = db.query(models.Job).filter(models.Job.model_version_id == version_id).first()
    if not job:
        return []

    events = (
        db.query(models.JobEvent)
        .filter(models.JobEvent.job_id == job.id)
        .order_by(models.JobEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return events


@router.get("/generations/{generation_id}/events", response_model=List[JobEventResponse])
def list_events_for_generation(
    generation_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    gen = db.query(models.Generation).filter(models.Generation.id == generation_id).first()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")

    job = db.query(models.Job).filter(models.Job.generation_id == generation_id).first()
    if not job:
        return []

    events = (
        db.query(models.JobEvent)
        .filter(models.JobEvent.job_id == job.id)
        .order_by(models.JobEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return events

