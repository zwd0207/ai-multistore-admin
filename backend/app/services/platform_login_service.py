from collections.abc import Callable
import json
import os
from pathlib import Path
import re
import subprocess
import threading
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.device_environment import DeviceEnvironment
from app.models.email_account import EmailAccount
from app.models.platform_login_credential import PlatformLoginCredential
from app.schemas.platform_login import PlatformLoginCreate, PlatformLoginUpdate
from app.services.encryption import decrypt_value, encrypt_value
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local
from app.services.store_service import ensure_store_exists, normalize_browser_binding, normalize_platform


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
_PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_OPEN_LOCKS_GUARD = threading.Lock()
_OPEN_LOCKS: dict[int, threading.Lock] = {}


def _serialize(item: PlatformLoginCredential) -> dict:
    return {
        "id": item.id,
        "store_id": item.store_id,
        "platform": item.platform,
        "login_label": item.login_label,
        "login_account": item.login_account,
        "email_account_id": item.email_account_id,
        "device_environment_id": item.device_environment_id,
        "login_status": item.login_status,
        "last_login_check_at": item.last_login_check_at.isoformat() if item.last_login_check_at else None,
        "remark": item.remark,
        "hasLoginPassword": bool(item.encrypted_login_password),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _get_model(db: Session, login_id: int) -> PlatformLoginCredential:
    item = db.get(PlatformLoginCredential, login_id)
    if item is None:
        raise ApiError(
            message="平台登录信息不存在",
            error_code="PLATFORM_LOGIN_NOT_FOUND",
            status_code=404,
            detail={"login_id": login_id},
        )
    return item


def _ensure_email_belongs_to_store(db: Session, email_account_id: int | None, store_id: int) -> None:
    if email_account_id is None:
        return
    item = db.get(EmailAccount, email_account_id)
    if item is None:
        raise ApiError(
            message="验证码邮箱不存在",
            error_code="EMAIL_ACCOUNT_NOT_FOUND",
            status_code=404,
            detail={"email_account_id": email_account_id},
        )
    if item.store_id != store_id:
        raise ApiError(
            message="验证码邮箱不属于当前店铺",
            error_code="EMAIL_ACCOUNT_STORE_MISMATCH",
            status_code=400,
            detail={"email_account_id": email_account_id, "store_id": store_id},
        )


def _ensure_device_belongs_to_store(db: Session, device_environment_id: int | None, store_id: int) -> None:
    if device_environment_id is None:
        return
    item = db.get(DeviceEnvironment, device_environment_id)
    if item is None:
        raise ApiError(
            message="设备环境不存在",
            error_code="DEVICE_ENVIRONMENT_NOT_FOUND",
            status_code=404,
            detail={"device_environment_id": device_environment_id},
        )
    if item.store_id != store_id:
        raise ApiError(
            message="设备环境不属于当前店铺",
            error_code="DEVICE_ENVIRONMENT_STORE_MISMATCH",
            status_code=400,
            detail={"device_environment_id": device_environment_id, "store_id": store_id},
        )


def _validate_bindings(
    db: Session,
    store_id: int,
    email_account_id: int | None,
    device_environment_id: int | None,
) -> None:
    ensure_store_exists(db, store_id)
    _ensure_email_belongs_to_store(db, email_account_id, store_id)
    _ensure_device_belongs_to_store(db, device_environment_id, store_id)


def create_platform_login(db: Session, payload: PlatformLoginCreate) -> dict:
    platform = normalize_platform(payload.platform)
    _validate_bindings(db, payload.store_id, payload.email_account_id, payload.device_environment_id)
    item = PlatformLoginCredential(
        store_id=payload.store_id,
        platform=platform,
        login_label=payload.login_label,
        login_account=payload.login_account or None,
        encrypted_login_password=encrypt_value(payload.login_password),
        email_account_id=payload.email_account_id,
        device_environment_id=payload.device_environment_id,
        login_status=payload.login_status,
        last_login_check_at=payload.last_login_check_at,
        remark=payload.remark,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def list_platform_logins(db: Session, store_id: int, page: int = 1, page_size: int = 20) -> dict:
    ensure_store_exists(db, store_id)
    statement = (
        select(PlatformLoginCredential)
        .where(PlatformLoginCredential.store_id == store_id)
        .order_by(PlatformLoginCredential.id.asc())
    )
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total = len(db.scalars(select(PlatformLoginCredential).where(PlatformLoginCredential.store_id == store_id)).all())
    return {"items": [_serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


def get_platform_login(db: Session, login_id: int) -> dict:
    return _serialize(_get_model(db, login_id))


def update_platform_login(db: Session, login_id: int, payload: PlatformLoginUpdate) -> dict:
    item = _get_model(db, login_id)
    updates = payload.model_dump(exclude_unset=True)
    target_store_id = updates.get("store_id", item.store_id) or item.store_id
    target_email_id = updates.get("email_account_id", item.email_account_id)
    target_device_id = updates.get("device_environment_id", item.device_environment_id)
    _validate_bindings(db, target_store_id, target_email_id, target_device_id)

    if "store_id" in updates and updates["store_id"] is not None:
        item.store_id = updates["store_id"]
    if "platform" in updates and updates["platform"] is not None:
        item.platform = normalize_platform(updates["platform"])
    if "login_label" in updates and updates["login_label"] is not None:
        item.login_label = updates["login_label"]
    if "login_account" in updates:
        item.login_account = updates["login_account"] or None
    if "login_password" in updates:
        password = updates["login_password"]
        if password:
            item.encrypted_login_password = encrypt_value(password)
    if "email_account_id" in updates:
        item.email_account_id = updates["email_account_id"]
    if "device_environment_id" in updates:
        item.device_environment_id = updates["device_environment_id"]
    if "login_status" in updates and updates["login_status"] is not None:
        item.login_status = updates["login_status"]
    if "last_login_check_at" in updates:
        item.last_login_check_at = updates["last_login_check_at"]
    if "remark" in updates:
        item.remark = updates["remark"]

    db.commit()
    db.refresh(item)
    return _serialize(item)


def _store_open_lock(store_id: int) -> threading.Lock:
    with _OPEN_LOCKS_GUARD:
        return _OPEN_LOCKS.setdefault(store_id, threading.Lock())


def _cli_executable(settings: Settings) -> Path:
    raw_path = str(settings.ziniao_cli_executable or "").strip()
    if not raw_path:
        raise ApiError("紫鸟本机连接尚未配置", "ZINIAO_CLI_NOT_CONFIGURED", 409)
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file() or (os.name == "nt" and path.name.lower() != "ziniao-cli.exe"):
        raise ApiError("紫鸟本机连接不可用", "ZINIAO_CLI_NOT_AVAILABLE", 409)
    return path


def _run_cli(
    executable: Path,
    arguments: list[str],
    *,
    settings: Settings,
    command_runner: CommandRunner,
) -> subprocess.CompletedProcess[str]:
    timeout = max(5, min(int(settings.ziniao_cli_timeout_seconds), 60))
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "check": False,
        "shell": False,
        "env": {**os.environ, "ZINIAO_CLI_NO_UPDATE_CHECK": "1"},
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return command_runner([str(executable), *arguments], **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise ApiError("紫鸟响应超时，请稍后重试", "ZINIAO_CLI_TIMEOUT", 504) from exc
    except OSError as exc:
        raise ApiError("紫鸟本机连接不可用", "ZINIAO_CLI_NOT_AVAILABLE", 409) from exc


def _require_cli_profile(
    executable: Path,
    *,
    settings: Settings,
    command_runner: CommandRunner,
) -> None:
    expected = str(settings.ziniao_cli_profile or "").strip()
    if not _PROFILE_PATTERN.fullmatch(expected):
        raise ApiError("紫鸟 CLI 配置名称无效", "ZINIAO_PROFILE_INVALID", 409)
    result = _run_cli(executable, ["config", "list"], settings=settings, command_runner=command_runner)
    if result.returncode != 0:
        raise ApiError("紫鸟 CLI 认证不可用", "ZINIAO_PROFILE_UNAVAILABLE", 409)
    active = next(
        (line.strip()[2:].strip() for line in result.stdout.splitlines() if line.strip().startswith("* ")),
        "",
    )
    if active != expected:
        raise ApiError("紫鸟本机授权配置未启用", "ZINIAO_PROFILE_NOT_ACTIVE", 409)


def _resolve_ziniao_store(
    executable: Path,
    *,
    profile_name: str,
    external_id: str | None = None,
    expected_platform: str = "naver",
    expected_source_platform: str | None = None,
    settings: Settings,
    command_runner: CommandRunner,
) -> None:
    selector = ["--id", external_id] if external_id else ["--name", profile_name]
    result = _run_cli(
        executable,
        [
            "store", "resolve",
            *selector,
            "--expected-name", profile_name,
            "--format", "json",
        ],
        settings=settings,
        command_runner=command_runner,
    )
    if result.returncode != 0:
        raise ApiError("未找到已绑定的紫鸟店铺", "ZINIAO_STORE_NOT_FOUND", 409)
    try:
        payload = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ApiError("紫鸟店铺校验失败", "ZINIAO_STORE_RESOLVE_INVALID", 502) from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ApiError("紫鸟店铺校验失败", "ZINIAO_STORE_RESOLVE_INVALID", 502)
    data = payload.get("data")
    candidates = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
    matches = [
        item
        for item in candidates
        if isinstance(item, dict)
        and item.get("matched") is not False
        and str(item.get("name") or item.get("storeName") or "") == profile_name
        and (
            not external_id
            or str(item.get("storeId") or item.get("id") or "") == external_id
        )
    ]
    unique_matches = {
        (
            str(item.get("storeId") or item.get("id") or ""),
            str(item.get("platformName") or item.get("platform") or ""),
        )
        for item in matches
    }
    if not unique_matches:
        raise ApiError("未找到已绑定的紫鸟店铺", "ZINIAO_STORE_NOT_FOUND", 409)
    if len(unique_matches) != 1:
        raise ApiError("紫鸟店铺匹配不唯一", "ZINIAO_STORE_MATCH_NOT_UNIQUE", 409)
    _store_id, platform_name = next(iter(unique_matches))
    normalized_platform = str(expected_platform or "").strip().lower()
    source_platform = str(expected_source_platform or "").strip().lower()
    platform_text = platform_name.lower()
    resolved_platform_matches = (
        normalized_platform == "naver" and "naver" in platform_text
        or normalized_platform == "coupang" and "coupang" in platform_text
        or normalized_platform == "custom" and bool(source_platform) and platform_text == source_platform
    )
    directory_source_matches = (
        normalized_platform == "naver" and "naver" in source_platform
        or normalized_platform == "coupang" and "coupang" in source_platform
        or normalized_platform == "custom" and bool(source_platform)
    )
    # Current ZClaw resolve responses identify the exact store but may omit
    # platformName. In that case the encrypted directory binding is the trusted
    # platform source; legacy name-only bindings still require a platform value.
    platform_matches = resolved_platform_matches or (
        bool(external_id) and not platform_text and directory_source_matches
    )
    if not _store_id or not platform_matches:
        raise ApiError("紫鸟店铺平台与系统不一致", "ZINIAO_STORE_PLATFORM_MISMATCH", 409)


def _write_browser_open_audit(
    db: Session,
    *,
    store_id: int,
    platform: str,
    actor_id: str,
    correlation_id: str,
    status: str,
    reason_code: str,
    settings: Settings,
) -> bool:
    now = get_utc_now()
    result = write_operation_audit_log_local(
        db,
        {
            "created_at": now,
            "updated_at": now,
            "store_id": store_id,
            "platform": platform,
            "environment": settings.app_env,
            "actor_type": "human",
            "actor_id": actor_id,
            "action": "ziniao_browser_open",
            "operation_phase": "local_browser_handoff",
            "correlation_id": correlation_id,
            "status": status,
            "reason_code": reason_code,
            "target_type": "store",
            "target_id": store_id,
            "changed_field_names": [],
            "counts_summary": {"browser_windows_requested": 1 if status == "success" else 0},
            "safety_flags": {
                "platform_write": False,
                "arbitrary_url_allowed": False,
                "raw_response_saved": False,
                "secrets_saved": False,
            },
            "sensitive_scan_passed": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
        },
        write_enabled=True,
        manual_approval=True,
        local_write_scope=LOCAL_WRITER_SCOPE,
    )
    return bool(result.get("audit_rows_written"))


def open_store_backend(
    db: Session,
    *,
    store_id: int,
    actor_id: str,
    settings: Settings | None = None,
    command_runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    runtime_settings = settings or get_settings()
    if not runtime_settings.ziniao_browser_open_enabled:
        raise ApiError("紫鸟店铺入口尚未启用", "ZINIAO_BROWSER_OPEN_DISABLED", 409)
    store = ensure_store_exists(db, store_id)
    if store.status != "active":
        raise ApiError("当前店铺已停用", "ZINIAO_STORE_INACTIVE", 409)
    if str(store.ziniao_directory_status or "unmanaged") == "removed":
        raise ApiError("该店铺已从紫鸟目录移除", "ZINIAO_STORE_REMOVED", 409)
    provider, profile_name = normalize_browser_binding(store.browser_provider, store.browser_profile_name)
    if provider != "ziniao" or not profile_name:
        raise ApiError("请先绑定紫鸟店铺", "ZINIAO_STORE_NOT_BOUND", 409)
    external_id = None
    if store.ziniao_external_id_encrypted:
        try:
            external_id = str(decrypt_value(store.ziniao_external_id_encrypted) or "").strip() or None
        except ApiError as exc:
            raise ApiError("紫鸟店铺绑定无法读取", "ZINIAO_STORE_BINDING_INVALID", 409) from exc
    store_platform = str(store.platform or "").strip().lower()
    if not external_id and store_platform != "naver":
        raise ApiError("该平台尚未完成紫鸟目录绑定", "ZINIAO_PLATFORM_NOT_SUPPORTED", 409)

    lock = _store_open_lock(store.id)
    if not lock.acquire(blocking=False):
        raise ApiError("店铺后台正在打开，请稍候", "ZINIAO_STORE_OPEN_IN_PROGRESS", 409)
    correlation_id = f"ziniao_open_{store.id}_{uuid.uuid4().hex[:12]}"
    planned_audit_written = False
    try:
        executable = _cli_executable(runtime_settings)
        _require_cli_profile(executable, settings=runtime_settings, command_runner=command_runner)
        _resolve_ziniao_store(
            executable,
            profile_name=profile_name,
            external_id=external_id,
            expected_platform=store_platform,
            expected_source_platform=store.ziniao_source_platform,
            settings=runtime_settings,
            command_runner=command_runner,
        )
        planned_audit_written = _write_browser_open_audit(
            db,
            store_id=store.id,
            platform=store_platform,
            actor_id=actor_id,
            correlation_id=correlation_id,
            status="planned",
            reason_code="ziniao_browser_open_requested",
            settings=runtime_settings,
        )
        if not planned_audit_written:
            raise ApiError("店铺打开审计不可用", "ZINIAO_OPEN_AUDIT_UNAVAILABLE", 503)
        result = _run_cli(
            executable,
            [
                "store", "open",
                *( ["--id", external_id] if external_id else ["--name", profile_name] ),
                "--expected-name", profile_name,
            ],
            settings=runtime_settings,
            command_runner=command_runner,
        )
        if result.returncode != 0:
            raise ApiError("紫鸟店铺打开失败", "ZINIAO_STORE_OPEN_FAILED", 502)
        try:
            success_audit_written = _write_browser_open_audit(
                db,
                store_id=store.id,
                platform=store_platform,
                actor_id=actor_id,
                correlation_id=correlation_id,
                status="success",
                reason_code="ziniao_browser_opened",
                settings=runtime_settings,
            )
        except Exception:
            db.rollback()
            success_audit_written = False
        return {
            "status": "opened",
            "store_id": store.id,
            "provider": "ziniao",
            "manual_browser_session_opened": True,
            "automated_platform_write_enabled": False,
            "arbitrary_url_allowed": False,
            "audit_recorded": success_audit_written,
        }
    except ApiError as exc:
        if planned_audit_written:
            try:
                _write_browser_open_audit(
                    db,
                    store_id=store.id,
                    platform=store_platform,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    status="failed",
                    reason_code=str(exc.error_code or "ziniao_browser_open_failed").lower(),
                    settings=runtime_settings,
                )
            except Exception:
                db.rollback()
        raise
    finally:
        lock.release()
