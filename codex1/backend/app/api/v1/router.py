from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    api_capabilities,
    api_credential_readiness,
    appeal_cases,
    auth,
    batch,
    backups,
    credentials,
    customer_inquiries,
    dashboard,
    device_environments,
    email_accounts,
    health,
    important_emails,
    operation_audit_logs,
    orders,
    platform_logins,
    permissions,
    products,
    shipping,
    stats,
    stores,
    sync,
    sync_logs,
)


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(stats.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai.router)
api_router.include_router(api_capabilities.router)
api_router.include_router(api_credential_readiness.router)
api_router.include_router(device_environments.router)
api_router.include_router(email_accounts.router)
api_router.include_router(important_emails.router)
api_router.include_router(appeal_cases.router)
api_router.include_router(batch.router)
api_router.include_router(backups.router)
api_router.include_router(credentials.router)
api_router.include_router(platform_logins.router)
api_router.include_router(permissions.router)
api_router.include_router(stores.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(shipping.router)
api_router.include_router(customer_inquiries.router)
api_router.include_router(sync.router)
api_router.include_router(sync_logs.router)
api_router.include_router(operation_audit_logs.router)
