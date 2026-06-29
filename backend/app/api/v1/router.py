from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    credentials,
    customer_inquiries,
    dashboard,
    health,
    orders,
    products,
    stats,
    stores,
    sync,
    sync_logs,
)


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(stats.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai.router)
api_router.include_router(credentials.router)
api_router.include_router(stores.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(customer_inquiries.router)
api_router.include_router(sync.router)
api_router.include_router(sync_logs.router)
