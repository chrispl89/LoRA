from fastapi import APIRouter
from app.api.v1 import persons, models, generations, model_versions

api_router = APIRouter()

api_router.include_router(persons.router, prefix="/persons", tags=["persons"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(model_versions.router, prefix="/model-versions", tags=["model-versions"])
api_router.include_router(generations.router, prefix="/generations", tags=["generations"])
