"""
CPU worker tasks for preprocessing.
"""
import os
import tempfile
from pathlib import Path
from typing import List
from PIL import Image
import imagehash
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.db import models
from app.services.s3 import get_s3_service
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="cpu.preprocess_person", queue="cpu_tasks")
def preprocess_person_task(self, person_id: int, preprocess_run_id: int):
    """
    Preprocess person photos: deduplication, normalization, face detection (stub).
    """
    db: Session = SessionLocal()
    try:
        # Get preprocess run
        preprocess_run = db.query(models.PreprocessRun).filter(
            models.PreprocessRun.id == preprocess_run_id
        ).first()
        
        if not preprocess_run:
            logger.error("preprocess_run_not_found", run_id=preprocess_run_id)
            return
        
        # Get job
        job = db.query(models.Job).filter(
            models.Job.preprocess_run_id == preprocess_run_id
        ).first()
        
        if job:
            job.status = "started"
            job.started_at = func.now()
            db.commit()
        
        preprocess_run.status = "started"
        preprocess_run.started_at = func.now()
        db.commit()
        
        logger.info("preprocessing_started", person_id=person_id, run_id=preprocess_run_id)
        
        # Get all uploaded photos for person
        photos = db.query(models.PhotoAsset).filter(
            models.PhotoAsset.person_id == person_id,
            models.PhotoAsset.status == "uploaded"
        ).all()
        
        if not photos:
            preprocess_run.status = "failed"
            preprocess_run.error_message = "No photos found"
            if job:
                job.status = "failed"
                job.error_message = "No photos found"
                job.finished_at = func.now()
            preprocess_run.finished_at = func.now()
            db.commit()
            return
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            s3 = get_s3_service()
            temp_path = Path(temp_dir)
            processed_dir = temp_path / "processed"
            processed_dir.mkdir()
            
            # Download and process photos
            processed_photos: List[models.PhotoAsset] = []
            duplicates: List[models.PhotoAsset] = []
            rejected: List[models.PhotoAsset] = []
            seen_hashes = set()
            
            for photo in photos:
                try:
                    # Download photo
                    local_path = temp_path / f"photo_{photo.id}.tmp"
                    s3.download_file(photo.s3_key, str(local_path))
                    
                    # Open and validate
                    img = Image.open(local_path)
                    img.verify()
                    img = Image.open(local_path)  # Reopen after verify
                    
                    # Calculate perceptual hash
                    phash_str = str(imagehash.phash(img))
                    photo.phash = phash_str
                    
                    # Check for duplicates
                    if phash_str in seen_hashes:
                        photo.status = "duplicate"
                        photo.is_duplicate = True
                        duplicates.append(photo)
                        logger.info("photo_duplicate", photo_id=photo.id, phash=phash_str)
                        continue
                    
                    seen_hashes.add(phash_str)
                    
                    # Normalize size (max 1024px)
                    max_size = 1024
                    if img.width > max_size or img.height > max_size:
                        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    
                    # Convert to RGB if needed
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Save processed image
                    processed_filename = f"processed_{photo.id}.jpg"
                    processed_path = processed_dir / processed_filename
                    img.save(processed_path, "JPEG", quality=95)
                    
                    # Upload to S3
                    output_key = f"datasets/processed/{person_id}/{processed_filename}"
                    s3.upload_file(str(processed_path), output_key, "image/jpeg")
                    
                    # Update photo
                    photo.status = "processed"
                    processed_photos.append(photo)
                    
                    logger.info("photo_processed", photo_id=photo.id, output_key=output_key)
                    
                except Exception as e:
                    logger.error("photo_processing_failed", photo_id=photo.id, error=str(e))
                    photo.status = "rejected"
                    rejected.append(photo)
            
            # TODO: Face detection (stub)
            # if face_detection_available:
            #     detect_faces(processed_dir)
            
            # Update preprocess run
            preprocess_run.images_accepted = len(processed_photos)
            preprocess_run.images_rejected = len(rejected)
            preprocess_run.images_duplicates = len(duplicates)
            preprocess_run.output_s3_prefix = f"datasets/processed/{person_id}/"
            preprocess_run.status = "finished"
            preprocess_run.finished_at = func.now()
            
            if job:
                job.status = "finished"
                job.finished_at = func.now()
            
            db.commit()
            
            logger.info(
                "preprocessing_completed",
                person_id=person_id,
                accepted=len(processed_photos),
                rejected=len(rejected),
                duplicates=len(duplicates)
            )
    
    except Exception as e:
        logger.error("preprocessing_failed", person_id=person_id, error=str(e))
        if preprocess_run:
            preprocess_run.status = "failed"
            preprocess_run.error_message = str(e)
        if job:
            job.status = "failed"
            job.error_message = str(e)
        db.commit()
        raise
    
    finally:
        db.close()
