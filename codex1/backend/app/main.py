from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.handlers import register_exception_handlers
from app.database import init_db
from app.routers import health


settings = get_settings()


def _validate_production_configuration() -> None:
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
    yield


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
