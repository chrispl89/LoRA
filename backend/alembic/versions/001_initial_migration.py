"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Person profiles
    op.create_table(
        'person_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('consent_confirmed', sa.Boolean(), nullable=False),
        sa.Column('subject_is_adult', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_person_profiles_id'), 'person_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_person_profiles_name'), 'person_profiles', ['name'], unique=False)
    
    # Photo assets
    op.create_table(
        'photo_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('s3_key', sa.String(length=512), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('phash', sa.String(length=64), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['person_id'], ['person_profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('s3_key')
    )
    op.create_index(op.f('ix_photo_assets_id'), 'photo_assets', ['id'], unique=False)
    op.create_index(op.f('ix_photo_assets_person_id'), 'photo_assets', ['person_id'], unique=False)
    op.create_index(op.f('ix_photo_assets_phash'), 'photo_assets', ['phash'], unique=False)
    
    # Preprocess runs
    op.create_table(
        'preprocess_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('images_accepted', sa.Integer(), nullable=True),
        sa.Column('images_rejected', sa.Integer(), nullable=True),
        sa.Column('images_duplicates', sa.Integer(), nullable=True),
        sa.Column('output_s3_prefix', sa.String(length=512), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['person_id'], ['person_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_preprocess_runs_id'), 'preprocess_runs', ['id'], unique=False)
    op.create_index(op.f('ix_preprocess_runs_person_id'), 'preprocess_runs', ['person_id'], unique=False)
    
    # Models
    op.create_table(
        'models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['person_id'], ['person_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_models_id'), 'models', ['id'], unique=False)
    op.create_index(op.f('ix_models_person_id'), 'models', ['person_id'], unique=False)
    
    # Model versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('base_model_name', sa.String(length=255), nullable=False),
        sa.Column('trigger_token', sa.String(length=100), nullable=False),
        sa.Column('train_config_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('artifact_s3_prefix', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_versions_id'), 'model_versions', ['id'], unique=False)
    op.create_index(op.f('ix_model_versions_model_id'), 'model_versions', ['model_id'], unique=False)
    
    # Jobs
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('preprocess_run_id', sa.Integer(), nullable=True),
        sa.Column('model_version_id', sa.Integer(), nullable=True),
        sa.Column('generation_id', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['preprocess_run_id'], ['preprocess_runs.id'], ),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('celery_task_id')
    )
    op.create_index(op.f('ix_jobs_id'), 'jobs', ['id'], unique=False)
    op.create_index(op.f('ix_jobs_job_type'), 'jobs', ['job_type'], unique=False)
    op.create_index(op.f('ix_jobs_celery_task_id'), 'jobs', ['celery_task_id'], unique=False)
    
    # Job events
    op.create_table(
        'job_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_events_id'), 'job_events', ['id'], unique=False)
    op.create_index(op.f('ix_job_events_job_id'), 'job_events', ['job_id'], unique=False)
    
    # Generations
    op.create_table(
        'generations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_version_id', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('negative_prompt', sa.Text(), nullable=True),
        sa.Column('steps', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('output_s3_key', sa.String(length=512), nullable=True),
        sa.Column('thumbnail_s3_key', sa.String(length=512), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generations_id'), 'generations', ['id'], unique=False)
    op.create_index(op.f('ix_generations_model_version_id'), 'generations', ['model_version_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_generations_model_version_id'), table_name='generations')
    op.drop_index(op.f('ix_generations_id'), table_name='generations')
    op.drop_table('generations')
    op.drop_index(op.f('ix_job_events_job_id'), table_name='job_events')
    op.drop_index(op.f('ix_job_events_id'), table_name='job_events')
    op.drop_table('job_events')
    op.drop_index(op.f('ix_jobs_celery_task_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_job_type'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_id'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_model_versions_model_id'), table_name='model_versions')
    op.drop_index(op.f('ix_model_versions_id'), table_name='model_versions')
    op.drop_table('model_versions')
    op.drop_index(op.f('ix_models_person_id'), table_name='models')
    op.drop_index(op.f('ix_models_id'), table_name='models')
    op.drop_table('models')
    op.drop_index(op.f('ix_preprocess_runs_person_id'), table_name='preprocess_runs')
    op.drop_index(op.f('ix_preprocess_runs_id'), table_name='preprocess_runs')
    op.drop_table('preprocess_runs')
    op.drop_index(op.f('ix_photo_assets_phash'), table_name='photo_assets')
    op.drop_index(op.f('ix_photo_assets_person_id'), table_name='photo_assets')
    op.drop_index(op.f('ix_photo_assets_id'), table_name='photo_assets')
    op.drop_table('photo_assets')
    op.drop_index(op.f('ix_person_profiles_name'), table_name='person_profiles')
    op.drop_index(op.f('ix_person_profiles_id'), table_name='person_profiles')
    op.drop_table('person_profiles')
