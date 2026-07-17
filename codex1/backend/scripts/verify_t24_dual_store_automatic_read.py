from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import ValidationError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t24-dual-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "REAL_API_TEST_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
    "AUTOMATIC_READ_SYNC_ENABLED": "false",
    "NAVER_READONLY_INQUIRY_REAL_READ_ENABLED": "false",
    "LIFECYCLE_SCHEDULERS_ENABLED": "false",
    "PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED": "true",
})

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.config import Settings
from app.core.exceptions import ApiError
from app.database import Base, SessionLocal, engine
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.models.pxg_naver_readonly import PxgNaverReadonlyCleanupStatus, PxgNaverReadonlyCustomerInquiry
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services import (
    api_credential_readiness_service,
    automatic_read_sync_service,
    naver_readonly_inquiry_service,
)
from app.services.encryption import encrypt_value
from scripts.prepare_t24_dual_store_automatic_read import (
    APPROVAL_VALUE,
    PREPARATION_SYNC_TYPE,
    PreparationBlocked,
    StoreSpec,
    _require_process_approval,
    prepare_dual_store_automatic_read,
)


NOW = datetime(2026, 7, 17, 16, 0, tzinfo=timezone.utc)
ACTIVATION_AT = NOW + timedelta(minutes=15)


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "database_url": f"sqlite:///{DB_PATH.as_posix()}",
        "credential_encryption_key": os.environ["CREDENTIAL_ENCRYPTION_KEY"],
        "real_api_test_enabled": False,
        "real_api_write_enabled": False,
        "automatic_read_sync_enabled": False,
        "naver_readonly_inquiry_real_read_enabled": False,
        "lifecycle_schedulers_enabled": False,
        "pxg_naver_local_read_retention_cleanup_enabled": True,
        "naver_readonly_inquiry_approved_store_ids": [1, 2],
    }
    values.update(overrides)
    return Settings(**values)


def _manual_log(store_id: int, finished_at: datetime, *, safe: bool = True) -> SyncLog:
    item_status = "success" if safe else "skipped"
    return SyncLog(
        store_id=store_id,
        platform="naver",
        sync_type="manual_batch_sync",
        status="success",
        started_at=finished_at - timedelta(seconds=1),
        finished_at=finished_at,
        message="safe verification fixture",
        raw_summary={
            "status": "success" if safe else "failed",
            "platform_write": False,
            "items": [
                {"platform": "naver", "resource": "products", "status": item_status, "platform_write": False},
                {"platform": "naver", "resource": "orders", "status": item_status, "platform_write": False},
            ],
        },
    )


def _seed() -> tuple[list[StoreSpec], dict[int, datetime]]:
    Base.metadata.create_all(engine)
    resumes = {
        1: NOW - timedelta(days=7, hours=3),
        2: NOW - timedelta(days=7, hours=1),
    }
    specs: list[StoreSpec] = []
    with SessionLocal() as db:
        stores = [
            Store(id=1, name="T24 Dual Store A", platform="naver", status="active"),
            Store(id=2, name="T24 Dual Store B", platform="naver", status="active"),
        ]
        db.add_all(stores)
        db.flush()
        check = ApiCapabilityCheck(
            platform="naver",
            capability_key="naver.customer_inquiry_read",
            capability_name="Naver inquiry readonly",
            api_category="customer_inquiry",
            test_status="tested_success",
            test_mode="real_readonly",
            data_usefulness="high",
            first_phase_candidate=True,
            sales_source_type="not_applicable",
        )
        db.add(check)
        db.flush()
        for store in stores:
            credential = ApiCredential(
                store_id=store.id,
                platform="naver",
                credential_name=f"credential-{store.id}",
                client_id=f"client-{store.id}",
                encrypted_secret_key=encrypt_value(f"secret-{store.id}"),
                auth_status="test_passed",
                status="active",
                extra_config={"channel_no": f"channel-{store.id}", "grant_type": "SELF"},
            )
            db.add(credential)
            db.flush()
            db.add(ApiCapabilityTestResult(
                store_id=store.id,
                credential_id=credential.id,
                capability_id=check.id,
                test_mode="real_readonly",
                test_status="tested_success",
                http_status=200,
                permission_result="order_seller_confirmed",
                tested_at=NOW,
            ))
            db.add(PxgNaverReadonlyCleanupStatus(
                store_id=store.id,
                platform="naver",
                status="healthy",
                last_run_at=NOW,
                last_success_at=NOW,
            ))
            db.add(_manual_log(store.id, resumes[store.id]))
        db.add(_manual_log(1, NOW - timedelta(minutes=5), safe=False))
        db.commit()
        specs = [
            StoreSpec(store.id, hashlib.sha256(store.name.encode("utf-8")).hexdigest())
            for store in stores
        ]
    return specs, resumes


def verify_settings_and_gate() -> None:
    settings = Settings(
        naver_readonly_inquiry_real_read_enabled=True,
        naver_readonly_inquiry_approved_store_ids=[1, 2],
    )
    assert settings.naver_readonly_inquiry_approved_store_id_set == frozenset({1, 2})
    legacy = Settings(
        naver_readonly_inquiry_real_read_enabled=True,
        naver_readonly_inquiry_approved_store_id=1,
        naver_readonly_inquiry_approved_store_ids=[1, 2],
    )
    assert legacy.naver_readonly_inquiry_approved_store_id_set == frozenset({1, 2})
    previous_plural = os.environ.get("NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS")
    previous_enabled = os.environ.get("NAVER_READONLY_INQUIRY_REAL_READ_ENABLED")
    previous_singular = os.environ.pop("NAVER_READONLY_INQUIRY_APPROVED_STORE_ID", None)
    try:
        os.environ["NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS"] = "[1,2]"
        os.environ["NAVER_READONLY_INQUIRY_REAL_READ_ENABLED"] = "true"
        parsed = Settings(_env_file=None)
        assert parsed.naver_readonly_inquiry_approved_store_id_set == frozenset({1, 2})
    finally:
        if previous_plural is None:
            os.environ.pop("NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS", None)
        else:
            os.environ["NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS"] = previous_plural
        if previous_enabled is None:
            os.environ.pop("NAVER_READONLY_INQUIRY_REAL_READ_ENABLED", None)
        else:
            os.environ["NAVER_READONLY_INQUIRY_REAL_READ_ENABLED"] = previous_enabled
        if previous_singular is not None:
            os.environ["NAVER_READONLY_INQUIRY_APPROVED_STORE_ID"] = previous_singular
    for invalid in ([], [1, 1], [0, 2], [-1, 2], [True, 2]):
        try:
            Settings(
                naver_readonly_inquiry_real_read_enabled=True,
                naver_readonly_inquiry_approved_store_ids=invalid,
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("invalid or empty dual-store allowlist must fail closed")
    try:
        Settings(
            naver_readonly_inquiry_real_read_enabled=True,
            naver_readonly_inquiry_approved_store_id=3,
            naver_readonly_inquiry_approved_store_ids=[1, 2],
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("conflicting singular and plural allowlists must fail closed")
    for store_id in (1, 2):
        naver_readonly_inquiry_service.assert_naver_inquiry_real_read_allowed(
            store_id=store_id,
            settings=settings,
        )
        assert automatic_read_sync_service._inquiry_gate_error(settings, store_id) is None
    try:
        naver_readonly_inquiry_service.assert_naver_inquiry_real_read_allowed(
            store_id=3,
            settings=settings,
        )
    except ApiError as exc:
        assert exc.error_code == "naver_inquiry_store_not_approved"
    else:
        raise AssertionError("an unapproved third store must remain blocked")


def verify_process_approval(specs: list[StoreSpec]) -> None:
    previous_approval = os.environ.get("T24_DUAL_STORE_PREPARATION_APPROVAL")
    previous_ids = os.environ.get("T24_DUAL_STORE_PREPARATION_STORE_IDS")
    try:
        os.environ["T24_DUAL_STORE_PREPARATION_APPROVAL"] = APPROVAL_VALUE
        os.environ["T24_DUAL_STORE_PREPARATION_STORE_IDS"] = "1,1,2"
        try:
            _require_process_approval(specs)
        except PreparationBlocked as exc:
            assert exc.error_code == "t24_dual_store_approved_ids_duplicate"
        else:
            raise AssertionError("duplicate process approval IDs must fail closed")
        os.environ["T24_DUAL_STORE_PREPARATION_STORE_IDS"] = "2,1"
        _require_process_approval(specs)
    finally:
        if previous_approval is None:
            os.environ.pop("T24_DUAL_STORE_PREPARATION_APPROVAL", None)
        else:
            os.environ["T24_DUAL_STORE_PREPARATION_APPROVAL"] = previous_approval
        if previous_ids is None:
            os.environ.pop("T24_DUAL_STORE_PREPARATION_STORE_IDS", None)
        else:
            os.environ["T24_DUAL_STORE_PREPARATION_STORE_IDS"] = previous_ids


def verify_latest_capability_result_wins() -> None:
    with SessionLocal() as db:
        credential = db.scalar(select(ApiCredential).where(ApiCredential.store_id == 1))
        capability = db.scalar(select(ApiCapabilityCheck).where(
            ApiCapabilityCheck.capability_key == "naver.customer_inquiry_read",
        ))
        failed = ApiCapabilityTestResult(
            store_id=1,
            credential_id=credential.id,
            capability_id=capability.id,
            test_mode="real_readonly",
            test_status="tested_failed",
            http_status=403,
            error_code="permission_forbidden",
            permission_result="not_confirmed",
            tested_at=NOW + timedelta(seconds=1),
        )
        db.add(failed)
        db.commit()
        try:
            naver_readonly_inquiry_service._approved_inquiry_credential(db, store_id=1)
        except ApiError as exc:
            assert exc.error_code == "naver_inquiry_capability_not_verified"
        else:
            raise AssertionError("a newer failed capability result must supersede an older success")
        db.delete(failed)
        db.commit()
        assert naver_readonly_inquiry_service._approved_inquiry_credential(db, store_id=1).id == credential.id


def verify_preparation(specs: list[StoreSpec], resumes: dict[int, datetime]) -> None:
    with SessionLocal() as db:
        result = prepare_dual_store_automatic_read(
            db,
            specs=specs,
            settings=_settings(),
            activation_at=ACTIVATION_AT,
            now=NOW,
        )
        assert result == {
            "status": "prepared",
            "store_ids": [1, 2],
            "checkpoint_count": 8,
            "first_run_spacing_seconds": 60,
            "activation_at": ACTIVATION_AT.isoformat(),
            "platform_write": False,
            "network_called": False,
        }
        checkpoints = db.scalars(select(SyncCheckpoint).order_by(
            SyncCheckpoint.next_run_at.asc(),
        )).all()
        assert len(checkpoints) == 8
        assert [
            checkpoint.next_run_at.replace(tzinfo=timezone.utc)
            for checkpoint in checkpoints
        ] == [ACTIVATION_AT + timedelta(minutes=index) for index in range(8)]
        for checkpoint in checkpoints:
            resource = automatic_read_sync_service._resource_for_checkpoint(checkpoint)
            assert checkpoint.automatic_read_enabled is True
            assert checkpoint.status == "idle"
            assert checkpoint.lease_token is None and checkpoint.cursor_value is None
            actual_resume = checkpoint.last_synced_at
            if actual_resume is not None:
                actual_resume = actual_resume.replace(tzinfo=timezone.utc)
            if resource in {"orders", "products"}:
                assert actual_resume == (
                    ACTIVATION_AT - timedelta(days=30)
                    if resource == "orders"
                    else resumes[checkpoint.store_id]
                )
            else:
                assert actual_resume is None
        logs = db.scalars(select(SyncLog).where(
            SyncLog.sync_type == PREPARATION_SYNC_TYPE,
        )).all()
        assert len(logs) == 2
        assert all((log.raw_summary or {}).get("platform_write") is False for log in logs)
        assert all((log.raw_summary or {}).get("network_called") is False for log in logs)
        repeat = prepare_dual_store_automatic_read(
            db,
            specs=list(reversed(specs)),
            settings=_settings(),
            activation_at=ACTIVATION_AT,
            now=NOW + timedelta(minutes=1),
        )
        assert repeat["status"] == "already_prepared" and repeat["checkpoint_count"] == 8

        marker = logs[0]
        original_summary = dict(marker.raw_summary)
        marker.raw_summary = {**original_summary, "network_called": True}
        db.commit()
        try:
            prepare_dual_store_automatic_read(
                db,
                specs=specs,
                settings=_settings(),
                activation_at=ACTIVATION_AT,
                now=NOW + timedelta(minutes=1),
            )
        except PreparationBlocked as exc:
            assert exc.error_code == "automatic_read_preparation_evidence_invalid"
        else:
            raise AssertionError("tampered preparation evidence must fail closed")
        marker.raw_summary = original_summary
        db.commit()

        try:
            prepare_dual_store_automatic_read(
                db,
                specs=specs,
                settings=_settings(),
                activation_at=ACTIVATION_AT,
                now=ACTIVATION_AT + timedelta(seconds=1),
            )
        except PreparationBlocked as exc:
            assert exc.error_code == "t24_activation_time_too_soon"
        else:
            raise AssertionError("an expired activation schedule must fail closed")

        checkpoints[0].last_attempt_at = NOW
        db.commit()
        try:
            prepare_dual_store_automatic_read(
                db,
                specs=specs,
                settings=_settings(),
                activation_at=ACTIVATION_AT,
                now=NOW + timedelta(minutes=2),
            )
        except PreparationBlocked as exc:
            assert exc.error_code == "t24_checkpoint_not_pristine"
        else:
            raise AssertionError("consumed checkpoints must never be reset by preparation")
        checkpoints[0].last_attempt_at = None
        db.commit()


def verify_commit_fence() -> None:
    settings = Settings(
        naver_readonly_inquiry_real_read_enabled=True,
        naver_readonly_inquiry_approved_store_ids=[1, 2],
    )
    with SessionLocal() as db:
        checkpoint = db.scalar(select(SyncCheckpoint).where(
            SyncCheckpoint.store_id == 1,
            SyncCheckpoint.sync_type == "naver_automatic_inquiries",
        ))
        credential = db.scalar(select(ApiCredential).where(ApiCredential.store_id == 1))
        checkpoint.status = "running"
        checkpoint.lease_token = "fence-token"
        checkpoint.lease_expires_at = NOW + timedelta(minutes=10)
        db.commit()
        lease = {"checkpoint_id": checkpoint.id, "token": "fence-token"}
        naver_readonly_inquiry_service._fence_inquiry_commit(
            db,
            lease=lease,
            store_id=1,
            credential_id=credential.id,
            automatic=True,
            settings=settings,
            now=NOW,
        )
        db.rollback()
        checkpoint = db.get(SyncCheckpoint, checkpoint.id)
        checkpoint.automatic_read_enabled = False
        db.commit()
        try:
            naver_readonly_inquiry_service._fence_inquiry_commit(
                db,
                lease=lease,
                store_id=1,
                credential_id=credential.id,
                automatic=True,
                settings=settings,
                now=NOW,
            )
        except ApiError as exc:
            assert exc.error_code == "naver_inquiry_commit_fence_lost"
            db.rollback()
        else:
            raise AssertionError("disabled automatic checkpoint must fail the final commit fence")


def verify_activation_gate() -> None:
    with SessionLocal() as db:
        blocked = automatic_read_sync_service._apply_prepared_activation_gate(
            db,
            now=ACTIVATION_AT + timedelta(minutes=10),
        )
        assert blocked == 8
        checkpoints = db.scalars(select(SyncCheckpoint).order_by(
            SyncCheckpoint.store_id.asc(),
            SyncCheckpoint.id.asc(),
        )).all()
        assert all(
            checkpoint.status == "blocked"
            and checkpoint.automatic_read_enabled is False
            and checkpoint.last_error_code == "automatic_read_activation_window_missed"
            for checkpoint in checkpoints
        )
        by_store: dict[int, int] = {}
        for checkpoint in checkpoints:
            resource = automatic_read_sync_service._resource_for_checkpoint(checkpoint)
            store_index = checkpoint.store_id - 1
            resource_index = automatic_read_sync_service.PREPARED_ACTIVATION_RESOURCE_ORDER.index(resource)
            by_store[checkpoint.store_id] = by_store.get(checkpoint.store_id, 0) + 1
            checkpoint.status = "idle"
            checkpoint.automatic_read_enabled = True
            checkpoint.next_run_at = ACTIVATION_AT + timedelta(
                minutes=store_index * 4 + resource_index,
            )
            checkpoint.last_error_code = None
        assert by_store == {1: 4, 2: 4}
        db.commit()


class ThirtySliceOrderReader:
    def __init__(self) -> None:
        self.slices: list[int] = []

    def read_orders(self, _context, *, start_at, end_at, cursor):
        assert end_at - start_at >= timedelta(days=30)
        slice_index = int(cursor or 0)
        self.slices.append(slice_index)
        next_cursor = str(slice_index + 1) if slice_index < 29 else None
        return automatic_read_sync_service.store_onboarding_service.NaverReadPage(
            items=[],
            next_cursor=next_cursor,
        )

    def read_products(self, *_args, **_kwargs):
        raise AssertionError("order resume test must not call product reads")


def verify_thirty_day_order_resume() -> None:
    reader = ThirtySliceOrderReader()
    with SessionLocal() as db:
        checkpoint = db.scalar(select(SyncCheckpoint).where(
            SyncCheckpoint.store_id == 1,
            SyncCheckpoint.sync_type == automatic_read_sync_service.RESOURCE_CONFIG["orders"]["sync_type"],
        ))
        first = automatic_read_sync_service.run_automatic_checkpoint(
            db,
            checkpoint_id=checkpoint.id,
            now=ACTIVATION_AT,
            reader=reader,
        )
        assert first == "failed"
        db.refresh(checkpoint)
        assert checkpoint.status == "retry_wait"
        assert checkpoint.automatic_read_enabled is True
        assert checkpoint.last_error_code == "read_page_limit_reached"
        assert checkpoint.cursor_value == "20"
        retry_at = checkpoint.next_run_at.replace(tzinfo=timezone.utc)
        second = automatic_read_sync_service.run_automatic_checkpoint(
            db,
            checkpoint_id=checkpoint.id,
            now=retry_at,
            reader=reader,
        )
        assert second == "success"
        db.refresh(checkpoint)
        assert checkpoint.status == "success"
        assert checkpoint.cursor_value is None
        assert reader.slices == list(range(30))


def verify_postgres_revocation_rolls_back_pending_inquiries() -> None:
    postgres_url = os.environ.get("T22_TEST_POSTGRES_URL")
    if not postgres_url:
        return
    schema = f"t24_dual_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(postgres_url, future=True)
    isolated_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        isolated_engine = create_engine(
            postgres_url,
            future=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(isolated_engine)
        IsolatedSession = sessionmaker(bind=isolated_engine, expire_on_commit=False, future=True)
        with IsolatedSession() as seed_db:
            seed_db.add(Store(id=1, name="T24 PostgreSQL Fence", platform="naver", status="active"))
            seed_db.flush()
            credential = ApiCredential(
                id=1,
                store_id=1,
                platform="naver",
                credential_name="postgres-fence",
                client_id="postgres-client",
                encrypted_secret_key=encrypt_value("postgres-secret"),
                auth_status="test_passed",
                status="active",
                extra_config={"channel_no": "postgres-channel"},
            )
            capability = ApiCapabilityCheck(
                id=1,
                platform="naver",
                capability_key="naver.customer_inquiry_read",
                capability_name="Naver inquiry readonly",
                api_category="customer_inquiry",
                test_status="tested_success",
                test_mode="real_readonly",
                data_usefulness="high",
                first_phase_candidate=True,
                sales_source_type="not_applicable",
            )
            seed_db.add_all((credential, capability))
            seed_db.flush()
            seed_db.add(ApiCapabilityTestResult(
                store_id=1,
                credential_id=1,
                capability_id=1,
                test_mode="real_readonly",
                test_status="tested_success",
                http_status=200,
                permission_result="order_seller_confirmed",
                tested_at=NOW,
            ))
            seed_db.add(SyncCheckpoint(
                store_id=1,
                platform="naver",
                sync_type="naver_automatic_inquiries",
                automatic_read_enabled=True,
                status="running",
                lease_token="postgres-fence-token",
                lease_expires_at=NOW + timedelta(minutes=10),
            ))
            seed_db.commit()

        pending_db = IsolatedSession()
        revocation_db = IsolatedSession()
        try:
            checkpoint = pending_db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == 1))
            outcome = naver_readonly_inquiry_service._upsert_item(
                pending_db,
                store_id=1,
                item={
                    "inquiryNo": "postgres-fence-inquiry",
                    "inquiryContent": "must roll back",
                    "customerName": "Synthetic Customer",
                    "createdAt": NOW.isoformat(),
                },
                observed_at=NOW,
            )
            assert outcome == "created"

            revoked = revocation_db.get(SyncCheckpoint, checkpoint.id)
            revoked.status = "blocked"
            revoked.automatic_read_enabled = False
            revoked.lease_token = None
            revoked.lease_expires_at = None
            revocation_db.commit()

            try:
                naver_readonly_inquiry_service._fence_inquiry_commit(
                    pending_db,
                    lease={"checkpoint_id": checkpoint.id, "token": "postgres-fence-token"},
                    store_id=1,
                    credential_id=1,
                    automatic=True,
                    settings=Settings(
                        naver_readonly_inquiry_real_read_enabled=True,
                        naver_readonly_inquiry_approved_store_ids=[1, 2],
                    ),
                    now=NOW,
                )
            except ApiError as exc:
                assert exc.error_code == "naver_inquiry_commit_fence_lost"
                pending_db.rollback()
            else:
                raise AssertionError("PostgreSQL revocation must defeat the pending inquiry commit")
        finally:
            pending_db.close()
            revocation_db.close()
        with IsolatedSession() as verify_db:
            assert verify_db.query(PxgNaverReadonlyCustomerInquiry).count() == 0

        lock_db = IsolatedSession()
        writer_started = threading.Event()
        writer_done = threading.Event()
        writer_errors: list[Exception] = []

        def append_failed_capability() -> None:
            writer_db = IsolatedSession()
            try:
                writer_started.set()
                api_credential_readiness_service._persist_real_readonly_capability_results(
                    writer_db,
                    [{
                        "platform": "naver",
                        "capability_key": "naver.customer_inquiry_read",
                        "capability_name": "Naver inquiry readonly",
                        "api_category": "customer_inquiry",
                        "endpoint_path": "/v1/pay-user/inquiries",
                        "method": "GET",
                        "test_mode": "real_readonly",
                        "test_status": "tested_failed",
                        "http_status": 403,
                        "error_code": "permission_forbidden",
                        "permission_result": "not_confirmed",
                        "rate_limit_summary": None,
                        "response_fields_observed": None,
                        "notes": "synthetic PostgreSQL lock verification",
                        "store_id": 1,
                        "credential_id": 1,
                    }],
                )
            except Exception as exc:
                writer_errors.append(exc)
            finally:
                writer_db.close()
                writer_done.set()

        try:
            assert naver_readonly_inquiry_service._approved_inquiry_credential(
                lock_db,
                store_id=1,
            ).id == 1
            writer = threading.Thread(target=append_failed_capability, daemon=True)
            writer.start()
            assert writer_started.wait(timeout=2)
            time.sleep(0.2)
            assert not writer_done.is_set(), "capability append must wait on the credential lock"
            lock_db.commit()
            assert writer_done.wait(timeout=5)
            writer.join(timeout=1)
            assert not writer_errors
        finally:
            lock_db.rollback()
            lock_db.close()
        with IsolatedSession() as verify_db:
            try:
                naver_readonly_inquiry_service._approved_inquiry_credential(verify_db, store_id=1)
            except ApiError as exc:
                assert exc.error_code == "naver_inquiry_capability_not_verified"
            else:
                raise AssertionError("the serialized newer capability failure must block subsequent reads")
    finally:
        if isolated_engine is not None:
            isolated_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def verify_fail_closed(specs: list[StoreSpec]) -> None:
    for settings, expected in (
        (_settings(lifecycle_schedulers_enabled=True), "t24_lifecycle_scheduler_must_remain_disabled"),
        (_settings(automatic_read_sync_enabled=True), "t24_automatic_read_must_remain_disabled"),
        (_settings(customer_platform_write_enabled=True), "t24_platform_write_gate_open"),
        (
            _settings(naver_readonly_inquiry_approved_store_ids=[1]),
            "t24_runtime_allowlist_mismatch",
        ),
    ):
        with SessionLocal() as db:
            try:
                prepare_dual_store_automatic_read(
                    db,
                    specs=specs,
                    settings=settings,
                    activation_at=ACTIVATION_AT,
                    now=NOW,
                )
            except PreparationBlocked as exc:
                assert exc.error_code == expected
            else:
                raise AssertionError("unsafe production runtime must block preparation")
    with SessionLocal() as db:
        duplicate = ApiCredential(
            store_id=1,
            platform="naver",
            credential_name="duplicate-must-block",
            client_id="duplicate",
            encrypted_secret_key=encrypt_value("duplicate-secret"),
            auth_status="test_passed",
            status="active",
            extra_config={"channel_no": "duplicate-channel"},
        )
        db.add(duplicate)
        db.commit()
        for call, expected_code in (
            (
                lambda: naver_readonly_inquiry_service._approved_inquiry_credential(db, store_id=1),
                "naver_inquiry_credential_ambiguous",
            ),
            (
                lambda: automatic_read_sync_service._context(db, 1),
                "credential_ambiguous",
            ),
        ):
            try:
                call()
            except Exception as exc:
                actual_code = getattr(exc, "error_code", None) or getattr(exc, "code", None)
                assert actual_code == expected_code
            else:
                raise AssertionError("multiple active credentials must fail closed")
        db.delete(duplicate)
        db.commit()

        original = db.scalar(select(ApiCredential).where(
            ApiCredential.store_id == 1,
            ApiCredential.status == "active",
        ))
        original.status = "inactive"
        rotated = ApiCredential(
            store_id=1,
            platform="naver",
            credential_name="rotated-must-reprepare",
            client_id="rotated",
            encrypted_secret_key=encrypt_value("rotated-secret"),
            auth_status="test_passed",
            status="active",
            extra_config={"channel_no": "rotated-channel"},
        )
        db.add(rotated)
        db.commit()
        try:
            automatic_read_sync_service._context(db, 1)
        except Exception as exc:
            assert getattr(exc, "code", None) == "credential_changed_since_activation"
        else:
            raise AssertionError("credential rotation must not reuse a prepared checkpoint waterline")
        db.delete(rotated)
        original.status = "active"
        db.commit()


def main() -> None:
    try:
        verify_settings_and_gate()
        specs, resumes = _seed()
        verify_process_approval(specs)
        verify_latest_capability_result_wins()
        verify_preparation(specs, resumes)
        verify_activation_gate()
        verify_thirty_day_order_resume()
        verify_commit_fence()
        verify_postgres_revocation_rolls_back_pending_inquiries()
        verify_fail_closed(specs)
        print("t24 dual-store automatic readonly verification: ok")
    finally:
        engine.dispose()
        DB_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
