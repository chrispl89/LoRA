"""
GPU worker tasks for training and inference (STUB).
"""
import os
import tempfile
import time
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.db import models
from app.services.s3 import get_s3_service
from app.services.trainer.train import run_training
from app.services.inference.generate import generate_image, generate_thumbnail
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


@celery_app.task(bind=True, name="gpu.train_model")
def train_model_task(self, model_version_id: int):
    """
    Train LoRA model (STUB - placeholder).
    """
    db: Session = SessionLocal()
    try:
        # Get model version
        model_version = db.query(models.ModelVersion).filter(
            models.ModelVersion.id == model_version_id
        ).first()
        
        if not model_version:
            logger.error("model_version_not_found", version_id=model_version_id)
            return
        
        # Get job
        job = db.query(models.Job).filter(
            models.Job.model_version_id == model_version_id
        ).first()
        
        if job:
            job.status = "started"
            job.started_at = func.now()
            db.commit()

        def add_event(event_type: str, message: str, meta: dict | None = None) -> None:
            if not job:
                return
            ev = models.JobEvent(job_id=job.id, event_type=event_type, message=message, metadata_json=meta or None)
            db.add(ev)
            db.commit()
        
        model_version.status = "training"
        db.commit()
        add_event("milestone", "training_started", {"model_version_id": model_version_id})
        
        logger.info("training_started", model_version_id=model_version_id)
        
        # Get person and preprocess run
        person = model_version.model.person
        preprocess_run = db.query(models.PreprocessRun).filter(
            models.PreprocessRun.person_id == person.id,
            models.PreprocessRun.status == "finished"
        ).order_by(models.PreprocessRun.created_at.desc()).first()
        
        if not preprocess_run or not preprocess_run.output_s3_prefix:
            model_version.status = "failed"
            model_version.error_message = "No processed dataset found"
            db.commit()
            return
        
        # Download dataset
        with tempfile.TemporaryDirectory() as temp_dir:
            s3 = get_s3_service()
            temp_path = Path(temp_dir)
            dataset_dir = temp_path / "dataset"
            dataset_dir.mkdir()
            
            # List and download processed images
            dataset_keys = s3.list_files(preprocess_run.output_s3_prefix)
            for key in dataset_keys:
                if key.endswith(('.jpg', '.jpeg', '.png')):
                    local_path = dataset_dir / Path(key).name
                    s3.download_file(key, str(local_path))
            
            # Prepare training config
            train_config = model_version.train_config_json or {}
            train_config.update({
                "base_model_name": model_version.base_model_name,
                "trigger_token": model_version.trigger_token,
            })

            total_steps = int(train_config.get("steps", 200))
            t0 = time.time()

            def progress_cb(step: int, total: int, loss: float) -> None:
                elapsed = max(0.0, time.time() - t0)
                eta = None
                if step > 0:
                    rate = elapsed / float(step)
                    eta = max(0.0, rate * max(0, (total - step)))
                meta = {
                    "current": int(step),
                    "total": int(total),
                    "loss": float(loss),
                    "elapsed_seconds": float(elapsed),
                    "eta_seconds": float(eta) if eta is not None else None,
                }
                # Persist + expose via Celery task meta.
                add_event("progress", f"step {step}/{total} loss={loss:.6f}", meta)
                try:
                    self.update_state(state="PROGRESS", meta=meta)
                except Exception:
                    pass
            
            # Run training (diffusers)
            output_dir = temp_path / "model_output"
            artifacts = run_training(
                config=train_config,
                dataset_path=str(dataset_dir),
                output_path=str(output_dir),
                progress_callback=progress_cb,
            )
            
            # Upload artifacts to S3
            artifact_prefix = f"models/lora/{model_version_id}/"
            uploaded_keys = []
            
            for artifact_type, artifact_path in artifacts.items():
                if isinstance(artifact_path, list):
                    for sample_path in artifact_path:
                        key = f"{artifact_prefix}{Path(sample_path).name}"
                        s3.upload_file(sample_path, key)
                        uploaded_keys.append(key)
                else:
                    ap = Path(artifact_path)
                    if ap.exists() and ap.is_dir():
                        for file_path in ap.rglob("*"):
                            if not file_path.is_file():
                                continue
                            rel = file_path.relative_to(ap).as_posix()
                            key = f"{artifact_prefix}{artifact_type}/{rel}"
                            s3.upload_file(str(file_path), key)
                            uploaded_keys.append(key)
                    else:
                        key = f"{artifact_prefix}{Path(artifact_path).name}"
                        s3.upload_file(str(artifact_path), key)
                        uploaded_keys.append(key)
            
            # Update model version
            model_version.artifact_s3_prefix = artifact_prefix
            model_version.status = "completed"
            db.commit()
            
            if job:
                job.status = "finished"
                job.finished_at = func.now()
                db.commit()
                add_event("milestone", "training_completed", {"model_version_id": model_version_id, "steps": total_steps})
            
            logger.info("training_completed", model_version_id=model_version_id)
    
    except Exception as e:
        logger.error("training_failed", model_version_id=model_version_id, error=str(e))
        if model_version:
            model_version.status = "failed"
            model_version.error_message = str(e)
        if job:
            job.status = "failed"
            job.error_message = str(e)
        db.commit()
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True, name="gpu.generate_image")
def generate_image_task(self, generation_id: int):
    """
    Generate image (STUB - placeholder).
    """
    db: Session = SessionLocal()
    try:
        # Get generation
        generation = db.query(models.Generation).filter(
            models.Generation.id == generation_id
        ).first()
        
        if not generation:
            logger.error("generation_not_found", generation_id=generation_id)
            return
        
        # Get job
        job = db.query(models.Job).filter(
            models.Job.generation_id == generation_id
        ).first()
        
        if job:
            job.status = "started"
            job.started_at = func.now()
            db.commit()

        def add_event(event_type: str, message: str, meta: dict | None = None) -> None:
            if not job:
                return
            ev = models.JobEvent(job_id=job.id, event_type=event_type, message=message, metadata_json=meta or None)
            db.add(ev)
            db.commit()
        
        generation.status = "generating"
        db.commit()
        
        logger.info("generation_started", generation_id=generation_id)
        add_event("milestone", "generation_started", {"generation_id": generation_id, "model_version_id": generation.model_version_id})
        
        # Get model version and LoRA path
        model_version = generation.model_version

        # Generate image
        with tempfile.TemporaryDirectory() as temp_dir:
            s3 = get_s3_service()
            temp_path = Path(temp_dir)
            output_file = temp_path / f"generation_{generation_id}.png"

            # Download LoRA adapter into the same temp dir (so it exists during generation)
            lora_path = None
            if model_version.artifact_s3_prefix:
                lora_dir = temp_path / "lora"
                lora_dir.mkdir(parents=True, exist_ok=True)

                prefix = f"{model_version.artifact_s3_prefix}lora_dir/"
                keys = s3_service.list_files(prefix)
                for key in keys:
                    if key.endswith("/"):
                        continue
                    rel = key[len(prefix):]
                    out_path = lora_dir / rel
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    s3_service.download_file(key, str(out_path))

                lora_path = str(lora_dir)
            
            t0 = time.time()

            def progress_cb(step: int, total: int) -> None:
                # Avoid DB spam: log every 5 steps
                if step % 5 != 0 and step != total - 1:
                    return
                elapsed = max(0.0, time.time() - t0)
                eta = None
                if step > 0:
                    rate = elapsed / float(step)
                    eta = max(0.0, rate * max(0, (total - step)))
                meta = {
                    "current": int(step),
                    "total": int(total),
                    "elapsed_seconds": float(elapsed),
                    "eta_seconds": float(eta) if eta is not None else None,
                }
                add_event("progress", f"diffusion_step {step}/{total}", meta)
                try:
                    self.update_state(state="PROGRESS", meta=meta)
                except Exception:
                    pass

            generate_image(
                prompt=generation.prompt,
                negative_prompt=generation.negative_prompt,
                model_version_id=model_version.id,
                lora_path=lora_path,
                steps=generation.steps,
                width=generation.width,
                height=generation.height,
                seed=generation.seed,
                output_path=str(output_file),
                base_model_name=model_version.base_model_name,
                hf_token=settings.HUGGINGFACE_HUB_TOKEN,
                progress_callback=progress_cb,
            )
            
            # Upload to S3
            output_key = f"outputs/{generation_id}.png"
            s3.upload_file(str(output_file), output_key, "image/png")
            
            # Generate thumbnail
            thumbnail_file = temp_path / f"thumb_{generation_id}.png"
            generate_thumbnail(str(output_file), str(thumbnail_file))
            thumbnail_key = f"outputs/thumbnails/{generation_id}.png"
            s3.upload_file(str(thumbnail_file), thumbnail_key, "image/png")
            
            # Update generation
            generation.output_s3_key = output_key
            generation.thumbnail_s3_key = thumbnail_key
            generation.status = "completed"
            db.commit()
            
            if job:
                job.status = "finished"
                job.finished_at = func.now()
                db.commit()
                add_event("milestone", "generation_completed", {"generation_id": generation_id})
            
            logger.info("generation_completed", generation_id=generation_id)
    
    except Exception as e:
        logger.error("generation_failed", generation_id=generation_id, error=str(e))
        if generation:
            generation.status = "failed"
            generation.error_message = str(e)
        if job:
            job.status = "failed"
            job.error_message = str(e)
        db.commit()
        try:
            add_event("error", "generation_failed", {"generation_id": generation_id, "error": str(e)})
        except Exception:
            pass
        raise
    
    finally:
        db.close()
