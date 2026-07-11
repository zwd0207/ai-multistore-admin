import asyncio
from contextlib import suppress
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.handlers import register_exception_handlers
from app.database import SessionLocal, init_db
from app.routers import health


settings = get_settings()


def _validate_production_configuration() -> None:
    if settings.operator_trial_enabled:
        from app.services.operator_trial_service import assert_trial_runtime_closed

        assert_trial_runtime_closed(settings)
    if settings.app_env != "production":
        return
    errors = []
    if settings.allow_dev_auth:
        errors.append("ALLOW_DEV_AUTH")
    if not settings.session_token_pepper or len(settings.session_token_pepper) < 32:
        errors.append("SESSION_TOKEN_PEPPER")
    if settings.session_cookie_name != "__Host-erp_session" or not settings.session_cookie_secure:
        errors.append("SESSION_COOKIE")
    if not settings.cors_allowed_origins or any(
        origin == "*" or "localhost" in origin or "127.0.0.1" in origin or not origin.startswith("https://")
        for origin in settings.cors_allowed_origins
    ):
        errors.append("CORS_ALLOWED_ORIGINS")
    if settings.database_url.startswith("sqlite"):
        errors.append("DATABASE_URL")
    if errors:
        raise RuntimeError(f"unsafe production configuration: {', '.join(errors)}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    async def daily_cleanup_loop() -> None:
        while True:
            try:
                if not settings.pxg_naver_local_read_retention_cleanup_enabled:
                    await asyncio.sleep(24 * 60 * 60)
                    continue
                from app.services.pxg_naver_readonly_sync_safety_service import run_pxg_naver_daily_cleanup
                with SessionLocal() as db:
                    run_pxg_naver_daily_cleanup(db, settings=settings)
            except Exception:
                # The service persists a blocking control state when the PXG store exists.
                pass
            await asyncio.sleep(24 * 60 * 60)
    task = asyncio.create_task(daily_cleanup_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def create_app() -> FastAPI:
    _validate_production_configuration()
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def production_identity_and_security_headers(request: Request, call_next):
        if settings.app_env == "production" and request.headers.get("X-ERP-User-Key"):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "login session is required", "error_code": "session_required", "detail": None},
            )
        if _requires_write_protection(request):
            try:
                await _enforce_write_protection(request)
            except ApiError as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"success": False, "message": exc.message, "error_code": exc.error_code, "detail": None},
                )
        elif _requires_read_protection(request):
            try:
                _enforce_read_protection(request)
            except ApiError as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"success": False, "message": exc.message, "error_code": exc.error_code, "detail": None},
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith(("/api/v1/auth", "/api/v1/orders", "/api/v1/shipping")):
            response.headers["Cache-Control"] = "no-store, private"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    app.include_router(api_router)
    app.include_router(health.router, prefix=settings.api_prefix)

    @app.get("/", tags=["root"])
    def read_root() -> dict[str, str]:
        return {
            "service": settings.project_name,
            "status": "running",
            "docs": "/docs",
        }

    return app


app = create_app()


def _requires_write_protection(request: Request) -> bool:
    return (
        settings.app_env != "development"
        and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api/v1/")
        and request.url.path not in {
            "/api/v1/auth/login",
            "/api/v1/auth/mfa/verify",
            "/api/v1/auth/logout",
        }
    )


def _write_permission_for_path(path: str) -> str:
    if path.startswith("/api/v1/shipping/"):
        return "shipping.writeback.approve" if "writeback" in path else "shipping.batch.manage"
    if path.startswith("/api/v1/sync/"):
        if path == "/api/v1/sync/manual-batch/all":
            return "system.configure"
        return "customer.inquiries.reply" if path.endswith("/reply") else "platform.sync"
    if path.startswith("/api/v1/pxg-naver-readonly/"):
        return "platform.readonly.persist"
    if path.startswith("/api/v1/stores"):
        return "store.manage"
    if path.startswith(("/api/v1/credentials", "/api/v1/platform-logins", "/api/v1/api-credentials")):
        return "credentials.manage"
    if path.startswith(("/api/v1/device-environments", "/api/v1/email-accounts", "/api/v1/important-emails", "/api/v1/appeal-cases")):
        return "store.manage"
    if path.startswith(("/api/v1/api-capabilities", "/api/v1/api-capability-results")):
        return "system.configure"
    # Unknown and future write endpoints are privileged by default. They must be
    # assigned a narrower permission explicitly before ordinary operators use them.
    return "system.configure"


def _request_store_id(request: Request, body: dict, db) -> int | None:
    candidate = body.get("store_id", body.get("storeId", request.query_params.get("store_id")))
    if candidate is not None:
        try:
            return int(candidate)
        except (TypeError, ValueError) as exc:
            raise ApiError("store scope is required", "store_scope_forbidden", 403) from exc
    parts = [part for part in request.url.path.split("/") if part]
    if len(parts) >= 5 and parts[2] == "shipping" and parts[3] == "warehouse-batches":
        from app.models.shipping import WarehouseShippingBatch

        try:
            batch = db.get(WarehouseShippingBatch, int(parts[4]))
        except ValueError:
            batch = None
        if batch is not None:
            return batch.store_id
    if len(parts) >= 4 and parts[2] == "stores":
        try:
            return int(parts[3])
        except ValueError:
            return None
    if len(parts) >= 4:
        try:
            resource_id = int(parts[3])
        except ValueError:
            return None
        from app.models.api_credential import ApiCredential
        from app.models.appeal_case import AppealCase
        from app.models.device_environment import DeviceEnvironment
        from app.models.email_account import EmailAccount
        from app.models.important_email import ImportantEmail
        from app.models.platform_login_credential import PlatformLoginCredential

        model_by_prefix = {
            "credentials": ApiCredential,
            "device-environments": DeviceEnvironment,
            "email-accounts": EmailAccount,
            "important-emails": ImportantEmail,
            "appeal-cases": AppealCase,
            "platform-logins": PlatformLoginCredential,
        }
        model = model_by_prefix.get(parts[2])
        record = db.get(model, resource_id) if model else None
        if record is not None:
            return record.store_id
    return None


async def _enforce_write_protection(request: Request) -> None:
    # Validate before routing so a rejected request cannot invoke a business service or external platform.
    import json

    raw_body = await request.body()
    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, ValueError):
        body = {}
    from app.services.operator_access_service import OperatorIdentity, require_any_store_permission, require_store_permission
    from app.services.session_service import require_csrf, require_session

    db = SessionLocal()
    try:
        principal = require_session(request, db)
        require_csrf(request, db, principal)
        identity = OperatorIdentity(
            user_id=principal.user_id,
            user_key_hash=principal.user_key_hash,
            session_id=principal.session_id,
            last_reauthenticated_at=principal.last_reauthenticated_at,
        )
        permission_key = _write_permission_for_path(request.url.path)
        store_id = _request_store_id(request, body, db)
        if store_id is None:
            require_any_store_permission(db, identity=identity, permission_key=permission_key)
        else:
            require_store_permission(db, identity=identity, store_id=store_id, permission_key=permission_key)
        from app.services.operator_trial_service import DISABLED_TRIAL_WRITE_PATHS
        if request.url.path in DISABLED_TRIAL_WRITE_PATHS:
            raise ApiError("legacy real platform write is disabled", "legacy_platform_write_disabled", 403)
        if settings.operator_trial_enabled and request.url.path.endswith("/writeback"):
            raise ApiError("platform writeback is disabled for the trial", "trial_platform_write_disabled", 403)
    finally:
        db.close()


def _requires_read_protection(request: Request) -> bool:
    return (
        settings.app_env != "development"
        and request.method.upper() in {"GET", "HEAD"}
        and request.url.path.startswith("/api/v1/")
        and not request.url.path.startswith(("/api/v1/auth/", "/api/v1/health"))
    )


def _enforce_read_protection(request: Request) -> None:
    from app.services.operator_access_service import OperatorIdentity, require_any_store_permission, require_store_membership
    from app.services.session_service import require_session

    db = SessionLocal()
    try:
        principal = require_session(request, db)
        identity = OperatorIdentity(
            user_id=principal.user_id,
            user_key_hash=principal.user_key_hash,
            session_id=principal.session_id,
            last_reauthenticated_at=principal.last_reauthenticated_at,
        )
        request.state.authenticated_user_id = principal.user_id
        store_id = _request_store_id(request, {}, db)
        if store_id is not None:
            require_store_membership(db, identity=identity, store_id=store_id)
        elif request.url.path != "/api/v1/stores":
            require_any_store_permission(db, identity=identity, permission_key="system.configure")
    finally:
        db.close()
