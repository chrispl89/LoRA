"""
Database models for LoRA Person MVP.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class PersonProfile(Base):
    """Person profile with consent flags."""
    __tablename__ = "person_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    consent_confirmed = Column(Boolean, default=False, nullable=False)
    subject_is_adult = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    photos = relationship("PhotoAsset", back_populates="person", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="person", cascade="all, delete-orphan")
    preprocess_runs = relationship("PreprocessRun", back_populates="person", cascade="all, delete-orphan")


class PhotoAsset(Base):
    """Uploaded photo asset."""
    __tablename__ = "photo_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person_profiles.id"), nullable=False, index=True)
    s3_key = Column(String(512), nullable=False, unique=True)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(String(50), default="uploaded")  # uploaded, processed, rejected, duplicate
    phash = Column(String(64), nullable=True, index=True)  # Perceptual hash for deduplication
    is_duplicate = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    person = relationship("PersonProfile", back_populates="photos")


class PreprocessRun(Base):
    """Preprocessing job run."""
    __tablename__ = "preprocess_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person_profiles.id"), nullable=False, index=True)
    status = Column(String(50), default="pending")  # pending, started, finished, failed
    images_accepted = Column(Integer, default=0)
    images_rejected = Column(Integer, default=0)
    images_duplicates = Column(Integer, default=0)
    output_s3_prefix = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    person = relationship("PersonProfile", back_populates="preprocess_runs")
    job = relationship("Job", back_populates="preprocess_run", uselist=False)


class Model(Base):
    """LoRA model."""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person_profiles.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    person = relationship("PersonProfile", back_populates="models")
    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")


class ModelVersion(Base):
    """Version of a LoRA model."""
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    base_model_name = Column(String(255), nullable=False)  # e.g., "runwayml/stable-diffusion-v1-5"
    trigger_token = Column(String(100), nullable=False)  # e.g., "sks person"
    train_config_json = Column(JSON, nullable=True)  # Training hyperparameters
    artifact_s3_prefix = Column(String(512), nullable=True)  # Path to LoRA files in S3
    status = Column(String(50), default="pending")  # pending, training, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    model = relationship("Model", back_populates="versions")
    job = relationship("Job", back_populates="model_version", uselist=False)
    generations = relationship("Generation", back_populates="model_version")


class Job(Base):
    """Background job tracking."""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(50), nullable=False, index=True)  # preprocess, train, generate
    status = Column(String(50), default="pending")  # pending, started, finished, failed
    celery_task_id = Column(String(255), nullable=True, unique=True, index=True)
    
    # Foreign keys (optional, depending on job type)
    preprocess_run_id = Column(Integer, ForeignKey("preprocess_runs.id"), nullable=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    generation_id = Column(Integer, ForeignKey("generations.id"), nullable=True)
    
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    preprocess_run = relationship("PreprocessRun", back_populates="job")
    model_version = relationship("ModelVersion", back_populates="job")
    generation = relationship("Generation", back_populates="job")
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.created_at")


class JobEvent(Base):
    """Job progress events."""
    __tablename__ = "job_events"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # progress, log, error, milestone
    message = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="events")


class Generation(Base):
    """Image generation result."""
    __tablename__ = "generations"
    
    id = Column(Integer, primary_key=True, index=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    steps = Column(Integer, default=50)
    width = Column(Integer, default=512)
    height = Column(Integer, default=512)
    seed = Column(Integer, nullable=True)
    status = Column(String(50), default="pending")  # pending, generating, completed, failed
    output_s3_key = Column(String(512), nullable=True)
    thumbnail_s3_key = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    model_version = relationship("ModelVersion", back_populates="generations")
    job = relationship("Job", back_populates="generation", uselist=False)
