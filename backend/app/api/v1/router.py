from fastapi import APIRouter

from app.api.v1.endpoints import credentials, health, stores, sync_logs


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(credentials.router)
api_router.include_router(stores.router)
api_router.include_router(sync_logs.router)
