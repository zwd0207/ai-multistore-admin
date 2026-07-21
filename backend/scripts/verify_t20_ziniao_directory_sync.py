import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t20-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
LEGACY_DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t20-legacy-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
CLI_PATH = Path(tempfile.gettempdir()) / f"t20-cli-{os.getpid()}-{uuid.uuid4().hex[:8]}" / "ziniao-cli.exe"
CLI_PATH.parent.mkdir(parents=True, exist_ok=True)
CLI_PATH.touch()
ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")

os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": ENCRYPTION_KEY,
    "APP_ENV": "test",
    "LIFECYCLE_SCHEDULERS_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
    "PLATFORM_ORDER_WRITE_ENABLED": "false",
    "SHIPPING_PLATFORM_WRITE_ENABLED": "false",
    "CUSTOMER_PLATFORM_WRITE_ENABLED": "false",
    "PLATFORM_PRODUCT_WRITE_ENABLED": "false",
    "PLATFORM_INVENTORY_WRITE_ENABLED": "false",
    "AI_AUTOMATIC_OPERATIONS_ENABLED": "false",
    "ZINIAO_BROWSER_OPEN_ENABLED": "true",
    "ZINIAO_DIRECTORY_SYNC_ENABLED": "false",
    "ZINIAO_CLI_EXECUTABLE": str(CLI_PATH),
    "ZINIAO_CLI_PROFILE": "ziniao-sso-pilot",
})

from sqlalchemy import select
from sqlalchemy.orm import close_all_sessions

from app.api.v1.endpoints import stores as stores_endpoint
from app.config import Settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.database import SessionLocal, engine, init_db
from app.models.auth import (
    ErpPermission,
    ErpRole,
    ErpRolePermission,
    ErpStoreMembership,
    ErpUser,
)
from app.models.device_environment import DeviceEnvironment
from app.models.operation_audit_log import OperationAuditLog
from app.models.order import Order
from app.models.store import Store
from app.models.sync_log import SyncLog
from app.services import platform_login_service, ziniao_directory_sync_service
from app.services.encryption import decrypt_value
from scripts import upgrade_ziniao_directory_schema


PUBLIC_IPS = [
    "8.8.8.8", "1.1.1.1", "9.9.9.9", "208.67.222.222", "8.8.4.4",
    "1.0.0.1", "4.2.2.1", "64.6.64.6", "94.140.14.14", "76.76.2.0",
    "185.228.168.9", "77.88.8.8", "156.154.70.1", "80.80.80.80", "84.200.69.80",
]


def directory_rows() -> list[dict]:
    rows = []
    for index in range(11):
        rows.append({
            "id": f"zn-nav-{index + 1:02d}",
            "name": f"Naver Business {index + 1:02d}",
            "platform": "Korea-Naver",
            "platformName": "Naver",
            "siteName": "Korea",
            "ip": PUBLIC_IPS[index],
            "username": f"forbidden-user-{index + 1}",
        })
    for index in range(4):
        rows.append({
            "id": f"zn-coupang-{index + 1:02d}",
            "name": f"Coupang Business {index + 1:02d}",
            "platform": "Global-Coupang",
            "platformName": "coupang",
            "siteName": "Global",
            "ip": PUBLIC_IPS[11 + index],
            "username": f"forbidden-coupang-user-{index + 1}",
        })
    rows.extend([
        {
            "id": "zn-custom-01",
            "name": "Naver Business 02",
            "platform": "Custom platform",
            "platformName": "https://ads.naver.com/",
            "siteName": "Custom platform",
            "ip": "",
            "username": "forbidden-custom-user-1",
        },
        {
            "id": "zn-custom-02",
            "name": "Lotte Operator Entry",
            "platform": "Custom platform",
            "platformName": "https://store.lotteon.com/cm/main/login_SO.wsp",
            "siteName": "Custom platform",
            "ip": "",
            "username": "forbidden-custom-user-2",
        },
        {
            "id": "zn-email-01",
            "name": "Operations Outlook",
            "platform": "outlook email",
            "platformName": "email",
            "siteName": "outlook",
            "ip": "",
            "username": "forbidden-email-user-1",
        },
        {
            "id": "zn-email-02",
            "name": "Operations 163",
            "platform": "163 email",
            "platformName": "email",
            "siteName": "163",
            "ip": "",
            "username": "forbidden-email-user-2",
        },
    ])
    return rows


class FakeRunner:
    def __init__(self, rows: list[dict], *, profile: str = "ziniao-sso-pilot"):
        self.rows = rows
        self.profile = profile
        self.calls: list[list[str]] = []

    def __call__(self, command, **_kwargs):
        args = list(command)[1:]
        self.calls.append(args)
        if args == ["config", "list"]:
            return subprocess.CompletedProcess(command, 0, f"* {self.profile}\n", "")
        if args[:2] == ["account", "list"]:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"ok": True, "data": self.rows}, ensure_ascii=False),
                "",
            )
        if args[:2] == ["store", "resolve"]:
            selector = "--id" if "--id" in args else "--name"
            value = args[args.index(selector) + 1]
            row = next((item for item in self.rows if str(item["id"] if selector == "--id" else item["name"]) == value), None)
            if row is None:
                return subprocess.CompletedProcess(command, 1, "", "not found")
            data = {
                "storeId": row["id"],
                "name": row["name"],
                # The current local Bridge omits platformName from resolve.
                "platformName": "",
                "matched": True,
            }
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "data": data}), "")
        if args[:2] == ["store", "open"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True}), "")
        raise AssertionError(f"unexpected CLI command: {args}")


class FakeGeo:
    def __init__(self):
        self.calls: list[str] = []
        self.fail_for: set[str] = set()

    def __call__(self, ip_address: str) -> dict[str, str]:
        self.calls.append(ip_address)
        if ip_address in self.fail_for:
            raise TimeoutError("fake timeout")
        return {"country": "Test Country", "region": "Test Region", "city": "Test City"}


def settings(**overrides) -> Settings:
    values = {
        "database_url": f"sqlite:///{DB_PATH.as_posix()}",
        "credential_encryption_key": ENCRYPTION_KEY,
        "app_env": "test",
        "ziniao_browser_open_enabled": True,
        "ziniao_directory_sync_enabled": False,
        "ziniao_directory_sync_interval_seconds": 300,
        "ziniao_cli_executable": str(CLI_PATH),
        "ziniao_cli_profile": "ziniao-sso-pilot",
        "real_api_write_enabled": False,
        "platform_order_write_enabled": False,
        "shipping_platform_write_enabled": False,
        "customer_platform_write_enabled": False,
        "platform_product_write_enabled": False,
        "platform_inventory_write_enabled": False,
        "ai_automatic_operations_enabled": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def verify_migration() -> None:
    connection = sqlite3.connect(LEGACY_DB_PATH)
    try:
        connection.execute("CREATE TABLE stores (id INTEGER PRIMARY KEY, name VARCHAR(200), platform VARCHAR(50))")
        connection.execute("CREATE TABLE device_environments (id INTEGER PRIMARY KEY, store_id INTEGER)")
        connection.execute("CREATE TABLE erp_store_memberships (id INTEGER PRIMARY KEY, user_id INTEGER, store_id INTEGER, role_id INTEGER)")
        connection.commit()
    finally:
        connection.close()
    with patch.object(upgrade_ziniao_directory_schema, "_database_path", return_value=LEGACY_DB_PATH):
        first = upgrade_ziniao_directory_schema.upgrade()
        second = upgrade_ziniao_directory_schema.upgrade()
    assert "ziniao_external_id_encrypted" in first["stores"]
    assert "encrypted_ip_address" in first["device_environments"]
    assert first["erp_store_memberships"] == ["assignment_source"]
    assert all(not changed for changed in second.values())


def seed() -> tuple[int, int, int, int]:
    init_db()
    with SessionLocal() as db:
        pxg = Store(
            name="PXG internal name",
            platform="naver",
            status="active",
            browser_provider="ziniao",
            browser_profile_name="Naver Business 01",
        )
        local_store = Store(name="Local manual store", platform="naver", status="active")
        owner = ErpUser(user_key_hash="t20-owner", display_name="T20 Owner", status="active", auth_provider="password")
        restricted = ErpUser(user_key_hash="t20-restricted", display_name="T20 Restricted", status="active", auth_provider="password")
        owner_role = ErpRole(role_key="t20_owner", role_label_zh="owner", role_label_en="owner", status="active")
        restricted_role = ErpRole(role_key="t20_restricted", role_label_zh="restricted", role_label_en="restricted", status="active")
        db.add_all([pxg, local_store, owner, restricted, owner_role, restricted_role])
        db.flush()
        open_permission = db.scalar(select(ErpPermission).where(
            ErpPermission.permission_key == "platform.browser.open",
        ))
        admin_permission = db.scalar(select(ErpPermission).where(
            ErpPermission.permission_key == "store_membership.assign",
        ))
        assert open_permission is not None and admin_permission is not None
        db.add_all([
            ErpRolePermission(role_id=owner_role.id, permission_id=open_permission.id),
            ErpRolePermission(role_id=owner_role.id, permission_id=admin_permission.id),
            ErpStoreMembership(
                user_id=owner.id,
                store_id=pxg.id,
                role_id=owner_role.id,
                membership_status="active",
                assignment_source="manual",
            ),
            ErpStoreMembership(
                user_id=owner.id,
                store_id=local_store.id,
                role_id=owner_role.id,
                membership_status="active",
                assignment_source="manual",
            ),
            ErpStoreMembership(
                user_id=restricted.id,
                store_id=pxg.id,
                role_id=restricted_role.id,
                membership_status="active",
                assignment_source="manual",
            ),
            Order(
                store_id=pxg.id,
                platform="naver",
                external_order_id="history-order-001",
                product_name="Historical product",
                quantity=1,
                order_amount=100,
                currency="KRW",
                order_status="completed",
                ordered_at=get_utc_now(),
                source_type="historical_backfill",
            ),
        ])
        db.commit()
        return pxg.id, local_store.id, owner.id, restricted.id


def response_items(response: dict) -> list[dict]:
    return response["data"]["items"]


def verify_sync(pxg_id: int, local_store_id: int, owner_id: int, restricted_id: int) -> None:
    rows = directory_rows()
    runner = FakeRunner(rows)
    geo = FakeGeo()
    runtime_settings = settings()
    with SessionLocal() as db:
        result = ziniao_directory_sync_service.sync_ziniao_directory(
            db,
            settings=runtime_settings,
            command_runner=runner,
            geo_lookup=geo,
        )
        assert result["source_count"] == 19, result
        assert result["business_entry_count"] == 17, result
        assert result["excluded_email_count"] == 2, result
        assert result["created"] == 16, result
        assert result["network_updates"] == 15, result
        managed = db.scalars(select(Store).where(Store.ziniao_auto_managed.is_(True))).all()
        assert len(managed) == 17
        assert sum(store.platform == "naver" for store in managed) == 11
        assert sum(store.platform == "coupang" for store in managed) == 4
        assert sum(store.ziniao_operational_mode == "open_only" for store in managed) == 2
        assert not db.scalars(select(Store).where(Store.name.in_(("Operations Outlook", "Operations 163")))).all()
        assert len({store.name for store in managed}) == 17
        pxg = db.get(Store, pxg_id)
        assert pxg.name == "PXG internal name"
        assert pxg.ziniao_name_managed is False
        assert decrypt_value(pxg.ziniao_external_id_encrypted) == "zn-nav-01"
        assert db.get(Store, local_store_id).ziniao_directory_status == "unmanaged"

        environments = db.scalars(select(DeviceEnvironment).where(
            DeviceEnvironment.source_provider == "ziniao",
        )).all()
        assert len(environments) == 17
        encrypted = [item for item in environments if item.encrypted_ip_address]
        assert len(encrypted) == 15
        assert all(item.masked_ip_address and item.masked_ip_address != decrypt_value(item.encrypted_ip_address) for item in encrypted)
        assert len(geo.calls) == 15

        auto_memberships = db.scalars(select(ErpStoreMembership).where(
            ErpStoreMembership.assignment_source == "ziniao_directory",
            ErpStoreMembership.membership_status == "active",
        )).all()
        assert len(auto_memberships) == 16
        assert all(membership.user_id == owner_id for membership in auto_memberships)

        owner_data = stores_endpoint.serialize_store(pxg, db=db, user_id=owner_id)
        restricted_data = stores_endpoint.serialize_store(pxg, db=db, user_id=restricted_id)
        assert owner_data["network"]["ip_address"] == PUBLIC_IPS[0]
        assert restricted_data["network"]["ip_address"] != PUBLIC_IPS[0]
        assert restricted_data["network"]["ip_address"].endswith("*.*")
        assert "ziniao_external_id" not in json.dumps(owner_data)

        owner_request = SimpleNamespace(state=SimpleNamespace(authenticated_user_id=owner_id))
        restricted_request = SimpleNamespace(state=SimpleNamespace(authenticated_user_id=restricted_id))
        owner_list = stores_endpoint.list_stores(owner_request, page=1, page_size=100, include_archived=False, db=db)
        assert len(response_items(owner_list)) == 18
        restricted_list = stores_endpoint.list_stores(restricted_request, page=1, page_size=100, include_archived=False, db=db)
        assert len(response_items(restricted_list)) == 1
        try:
            stores_endpoint.list_stores(restricted_request, page=1, page_size=100, include_archived=True, db=db)
            raise AssertionError("restricted archived listing should fail")
        except ApiError as exc:
            assert exc.error_code == "store_membership_assign_forbidden"

        log = db.scalar(select(SyncLog).where(SyncLog.sync_type == "ziniao_directory"))
        audit = db.scalar(select(OperationAuditLog).where(OperationAuditLog.action == "ziniao_directory_sync"))
        assert log is not None and log.raw_summary["raw_response_saved"] is False
        assert audit is not None and audit.raw_response_saved is False and audit.secrets_saved is False

        open_result = platform_login_service.open_store_backend(
            db,
            store_id=pxg_id,
            actor_id="t20-owner",
            settings=runtime_settings,
            command_runner=runner,
        )
        assert open_result["status"] == "opened"
        resolve_call = next(call for call in runner.calls if call[:2] == ["store", "resolve"])
        open_call = next(call for call in runner.calls if call[:2] == ["store", "open"])
        assert resolve_call[2:4] == ["--id", "zn-nav-01"]
        assert open_call[2:4] == ["--id", "zn-nav-01"]
        assert "zn-nav-01" not in json.dumps(open_result)

        coupang = db.scalar(select(Store).where(Store.platform == "coupang"))
        custom = db.scalar(select(Store).where(Store.ziniao_operational_mode == "open_only"))
        for target in (coupang, custom):
            result = platform_login_service.open_store_backend(
                db,
                store_id=target.id,
                actor_id="t20-owner",
                settings=runtime_settings,
                command_runner=runner,
            )
            assert result["status"] == "opened"
        audit_platforms = set(db.scalars(select(OperationAuditLog.platform).where(
            OperationAuditLog.action == "ziniao_browser_open",
            OperationAuditLog.status == "success",
        )).all())
        assert {"naver", "coupang", "custom"}.issubset(audit_platforms)

        rebound_entry = ziniao_directory_sync_service.ZiniaoDirectoryEntry(
            external_id="different-id",
            external_id_hash=ziniao_directory_sync_service._identity_hash("different-id", runtime_settings),
            source_name=pxg.browser_profile_name,
            source_platform="Naver",
            source_site="Korea",
            platform="naver",
            operational_mode="business",
            ip_address=None,
            ip_status="no_ip",
        )
        assert ziniao_directory_sync_service._find_store_for_entry([pxg], rebound_entry) is None

    database_bytes = DB_PATH.read_bytes()
    assert b"zn-nav-01" not in database_bytes
    assert PUBLIC_IPS[0].encode("ascii") not in database_bytes
    assert b"forbidden-user-1" not in database_bytes

    renamed_rows = [dict(row) for row in rows]
    renamed_rows[2] = {**renamed_rows[2], "name": "Naver Business Renamed", "ip": "8.26.56.26"}
    renamed_runner = FakeRunner(renamed_rows)
    with SessionLocal() as db:
        before = db.scalar(select(Store).where(Store.ziniao_external_id_hash == ziniao_directory_sync_service._identity_hash("zn-nav-03", runtime_settings)))
        before_id = before.id
        result = ziniao_directory_sync_service.sync_ziniao_directory(
            db,
            settings=runtime_settings,
            command_runner=renamed_runner,
            geo_lookup=geo,
        )
        renamed = db.get(Store, before_id)
        assert result["renamed"] == 1, result
        assert renamed.name == "Naver Business Renamed"
        environment = db.scalar(select(DeviceEnvironment).where(
            DeviceEnvironment.store_id == before_id,
            DeviceEnvironment.source_provider == "ziniao",
        ))
        assert decrypt_value(environment.encrypted_ip_address) == "8.26.56.26"
        geo_calls_after_change = len(geo.calls)
        ziniao_directory_sync_service.sync_ziniao_directory(
            db,
            settings=runtime_settings,
            command_runner=renamed_runner,
            geo_lookup=geo,
        )
        assert len(geo.calls) == geo_calls_after_change
        active_auto_memberships = db.scalars(select(ErpStoreMembership).where(
            ErpStoreMembership.assignment_source == "ziniao_directory",
            ErpStoreMembership.membership_status == "active",
        )).all()
        assert len(active_auto_memberships) == 16

    geo_failure_rows = [dict(row) for row in renamed_rows]
    geo_failure_rows[3] = {**geo_failure_rows[3], "ip": "8.20.247.20"}
    geo.fail_for.add("8.20.247.20")
    with SessionLocal() as db:
        result = ziniao_directory_sync_service.sync_ziniao_directory(
            db,
            settings=runtime_settings,
            command_runner=FakeRunner(geo_failure_rows),
            geo_lookup=geo,
        )
        assert result["status"] == "success"
        failed_store = db.scalar(select(Store).where(
            Store.ziniao_external_id_hash == ziniao_directory_sync_service._identity_hash("zn-nav-04", runtime_settings),
        ))
        failed_environment = db.scalar(select(DeviceEnvironment).where(
            DeviceEnvironment.store_id == failed_store.id,
            DeviceEnvironment.source_provider == "ziniao",
        ))
        assert failed_environment.network_status == "failed"

    duplicate_rows = [dict(row) for row in rows]
    duplicate_rows[-1] = {**duplicate_rows[-1], "id": duplicate_rows[0]["id"]}
    try:
        ziniao_directory_sync_service.parse_directory_payload(
            json.dumps({"ok": True, "data": duplicate_rows}),
            settings=runtime_settings,
        )
        raise AssertionError("duplicate external id should fail")
    except ziniao_directory_sync_service.ZiniaoDirectoryError as exc:
        assert exc.code == "ziniao_directory_duplicate_external_id"

    missing_rows = [row for row in renamed_rows if row["id"] != "zn-nav-01"]
    with SessionLocal() as db:
        first = ziniao_directory_sync_service.sync_ziniao_directory(
            db,
            settings=runtime_settings,
            command_runner=FakeRunner(missing_rows),
            geo_lookup=geo,
        )
        assert first["archived"] == 0
        assert db.get(Store, pxg_id).ziniao_missing_count == 1
        second = ziniao_directory_sync_service.sync_ziniao_directory(
            db,
            settings=runtime_settings,
            command_runner=FakeRunner(missing_rows),
            geo_lookup=geo,
        )
        pxg = db.get(Store, pxg_id)
        assert second["archived"] == 1
        assert pxg.ziniao_directory_status == "removed"
        assert pxg.status == "active"
        assert db.scalar(select(Order).where(Order.store_id == pxg_id)) is not None
        owner_request = SimpleNamespace(state=SimpleNamespace(authenticated_user_id=owner_id))
        normal = stores_endpoint.list_stores(owner_request, page=1, page_size=100, include_archived=False, db=db)
        archived = stores_endpoint.list_stores(owner_request, page=1, page_size=100, include_archived=True, db=db)
        assert all(item["id"] != pxg_id for item in response_items(normal))
        assert any(item["id"] == pxg_id for item in response_items(archived))
        try:
            platform_login_service.open_store_backend(
                db,
                store_id=pxg_id,
                actor_id="t20-owner",
                settings=runtime_settings,
                command_runner=FakeRunner(rows),
            )
            raise AssertionError("removed store open should fail")
        except ApiError as exc:
            assert exc.error_code == "ZINIAO_STORE_REMOVED"
        restored = ziniao_directory_sync_service.sync_ziniao_directory(
            db,
            settings=runtime_settings,
            command_runner=FakeRunner(renamed_rows),
            geo_lookup=geo,
        )
        assert restored["restored"] == 1
        assert db.get(Store, pxg_id).ziniao_directory_status == "active"
        assert db.get(Store, local_store_id).ziniao_directory_status == "unmanaged"


def verify_scheduler() -> None:
    rows = directory_rows()
    runner = FakeRunner(rows)
    geo = FakeGeo()
    runtime_settings = settings(ziniao_directory_sync_enabled=True)
    ziniao_directory_sync_service.reset_scheduler_state_for_tests()
    first = ziniao_directory_sync_service.run_due_ziniao_directory_sync(
        session_factory=SessionLocal,
        settings=runtime_settings,
        command_runner=runner,
        geo_lookup=geo,
    )
    assert first["status"] == "success"
    second = ziniao_directory_sync_service.run_due_ziniao_directory_sync(
        session_factory=SessionLocal,
        settings=runtime_settings,
        command_runner=runner,
        geo_lookup=geo,
    )
    assert second["status"] == "not_due"
    assert ziniao_directory_sync_service._RUN_LOCK.acquire(blocking=False)
    try:
        ziniao_directory_sync_service.reset_scheduler_state_for_tests()
        concurrent = ziniao_directory_sync_service.run_due_ziniao_directory_sync(
            session_factory=SessionLocal,
            settings=runtime_settings,
            command_runner=runner,
            geo_lookup=geo,
        )
        assert concurrent["status"] == "running"
    finally:
        ziniao_directory_sync_service._RUN_LOCK.release()


def verify_source_contract() -> None:
    main_text = (BACKEND_DIR / "app" / "main.py").read_text(encoding="utf-8")
    service_text = (BACKEND_DIR / "app" / "services" / "ziniao_directory_sync_service.py").read_text(encoding="utf-8")
    stores_text = (BACKEND_DIR / "app" / "api" / "v1" / "endpoints" / "stores.py").read_text(encoding="utf-8")
    assert "run_due_ziniao_directory_sync" in main_text
    assert "asyncio.create_task(run_ziniao" not in main_text
    assert '["account", "list"' not in service_text or '"account", "list"' in service_text
    assert "https://ipwho.is/" in service_text
    assert "include_archived" in stores_text
    assert ziniao_directory_sync_service._normalize_ip("动态网络") == (None, "dynamic")
    for forbidden in ("platform password", "naver write", "second store table"):
        assert forbidden not in service_text.lower()


def main() -> None:
    verify_migration()
    pxg_id, local_store_id, owner_id, restricted_id = seed()
    verify_sync(pxg_id, local_store_id, owner_id, restricted_id)
    verify_scheduler()
    verify_source_contract()
    print("T20 Ziniao directory sync verification passed")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all_sessions()
        engine.dispose()
        for path in (DB_PATH, LEGACY_DB_PATH, CLI_PATH):
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                pass
        try:
            CLI_PATH.parent.rmdir()
        except OSError:
            pass
