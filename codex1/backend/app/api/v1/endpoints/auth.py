from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.responses import success_response
from app.database import get_db
from app.schemas.auth import LoginRequest, MfaVerifyRequest
from app.services.session_service import (
    begin_login,
    complete_mfa,
    require_csrf,
    require_session,
    rotate_csrf_token,
    revoke_session,
    session_summary,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _require_allowed_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    if not origin or origin not in get_settings().cors_allowed_origins:
        raise ApiError("request origin is not allowed", "csrf_validation_failed", 403)


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store, private"


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _require_allowed_origin(request)
    data, token = begin_login(db, login_identifier=payload.login_identifier, password=payload.password)
    _set_session_cookie(response, token)
    return success_response(data=data, message="MFA verification required")


@router.post("/mfa/verify")
def verify_mfa(payload: MfaVerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _require_allowed_origin(request)
    data, token, _csrf = complete_mfa(
        db,
        pending_token=request.cookies.get(get_settings().session_cookie_name),
        code=payload.code,
    )
    _set_session_cookie(response, token)
    return success_response(data=data, message="login completed")


@router.get("/session")
def read_session(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    principal = require_session(request, db)
    response.headers["Cache-Control"] = "no-store, private"
    data = session_summary(db, principal)
    data["csrf_token"] = rotate_csrf_token(db, principal)
    return success_response(data=data, message="session active")


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    principal = require_session(request, db)
    require_csrf(request, db, principal)
    settings = get_settings()
    revoke_session(db, token=request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.session_cookie_secure, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store, private"
    return success_response(data={"status": "logged_out"}, message="logout completed")
