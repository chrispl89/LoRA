from fastapi import APIRouter
from app.api.v1 import persons, models, generations

api_router = APIRouter()

api_router.include_router(persons.router, prefix="/persons", tags=["persons"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(generations.router, prefix="/generations", tags=["generations"])
