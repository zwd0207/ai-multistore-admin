import hashlib
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t24-logistics-recovery-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "APP_ENV": "test",
    "REAL_API_TEST_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
    "AUTOMATIC_READ_SYNC_ENABLED": "false",
    "LIFECYCLE_SCHEDULERS_ENABLED": "false",
})

from sqlalchemy import select

from app.config import Settings
from app.database import SessionLocal, engine, init_db
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from scripts.prepare_t24_dual_store_automatic_read import StoreSpec
from scripts.recover_t24_dual_store_logistics import (
    APPROVAL_ENV,
    APPROVAL_VALUE,
    APPROVED_STORE_IDS_ENV,
    FIRST_RUN_SPACING,
    RECOVERABLE_ERROR_CODE,
    RECOVERY_SYNC_TYPE,
    LogisticsRecoveryBlocked,
    recover_dual_store_logistics,
)


NOW = datetime(2026, 7, 18, 2, 0, tzinfo=timezone.utc)
WRITE_FLAGS = (
    "real_api_write_enabled",
    "platform_product_write_enabled",
    "platform_inventory_write_enabled",
    "platform_order_write_enabled",
    "customer_platform_write_enabled",
    "shipping_platform_write_enabled",
    "pxg_naver_shipping_pilot_enabled",
    "ai_automatic_operations_enabled",
)


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "database_url": f"sqlite:///{DB_PATH.as_posix()}",
        "credential_encryption_key": os.environ["CREDENTIAL_ENCRYPTION_KEY"],
        "real_api_write_enabled": False,
        "platform_product_write_enabled": False,
        "platform_inventory_write_enabled": False,
        "platform_order_write_enabled": False,
        "customer_platform_write_enabled": False,
        "shipping_platform_write_enabled": False,
        "pxg_naver_shipping_pilot_enabled": False,
        "ai_automatic_operations_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def _expect_blocked(code: str, call) -> None:
    try:
        call()
    except LogisticsRecoveryBlocked as exc:
        assert exc.error_code == code, (exc.error_code, code)
    else:
        raise AssertionError(f"expected recovery blocker: {code}")


def _seed() -> tuple[list[StoreSpec], dict[int, dict[str, SyncCheckpoint]]]:
    init_db()
    specs: list[StoreSpec] = []
    rows: dict[int, dict[str, SyncCheckpoint]] = {}
    with SessionLocal() as db:
        for index in range(2):
            store = Store(
                name=f"T24 Logistics Recovery {index + 1}",
                platform="naver",
                status="active",
            )
            db.add(store)
            db.flush()
            specs.append(StoreSpec(
                store.id,
                hashlib.sha256(store.name.encode("utf-8")).hexdigest(),
            ))
            resources = {
                "orders": SyncCheckpoint(
                    store_id=store.id,
                    platform="naver",
                    sync_type="naver_automatic_orders",
                    automatic_read_enabled=True,
                    status="success",
                    fresh_until=NOW + timedelta(minutes=20),
                    next_run_at=NOW + timedelta(minutes=5),
                ),
                "inquiries": SyncCheckpoint(
                    store_id=store.id,
                    platform="naver",
                    sync_type="naver_automatic_inquiries",
                    automatic_read_enabled=True,
                    status="success",
                    fresh_until=NOW + timedelta(minutes=20),
                    next_run_at=NOW + timedelta(minutes=5),
                ),
                "products": SyncCheckpoint(
                    store_id=store.id,
                    platform="naver",
                    sync_type="naver_automatic_products",
                    automatic_read_enabled=True,
                    status="success",
                    fresh_until=NOW + timedelta(hours=2),
                    next_run_at=NOW + timedelta(hours=1),
                ),
                "logistics": SyncCheckpoint(
                    store_id=store.id,
                    platform="naver",
                    sync_type="naver_automatic_logistics",
                    automatic_read_enabled=False,
                    status="blocked",
                    next_run_at=None,
                    retry_count=3,
                    last_error_code=RECOVERABLE_ERROR_CODE,
                    cursor_value=f"logistics-local-id:{100 + index}",
                ),
            }
            db.add_all(resources.values())
            rows[store.id] = resources
        db.commit()
        for resources in rows.values():
            for checkpoint in resources.values():
                db.refresh(checkpoint)
    return specs, rows


def main() -> None:
    specs, seeded = _seed()
    store_ids = [spec.store_id for spec in specs]
    os.environ.pop(APPROVAL_ENV, None)
    os.environ.pop(APPROVED_STORE_IDS_ENV, None)

    with SessionLocal() as db:
        _expect_blocked(
            "t24_logistics_recovery_owner_approval_missing",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(), now=NOW
            ),
        )
        db.rollback()

    os.environ[APPROVAL_ENV] = APPROVAL_VALUE
    os.environ[APPROVED_STORE_IDS_ENV] = str(store_ids[0])
    with SessionLocal() as db:
        _expect_blocked(
            "t24_logistics_recovery_approved_ids_mismatch",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(), now=NOW
            ),
        )
        db.rollback()

    os.environ[APPROVED_STORE_IDS_ENV] = ",".join(str(store_id) for store_id in store_ids)
    with SessionLocal() as db:
        _expect_blocked(
            "t24_logistics_recovery_production_required",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(app_env="test"), now=NOW
            ),
        )
        db.rollback()
        for flag in WRITE_FLAGS:
            _expect_blocked(
                "t24_logistics_recovery_write_gate_open",
                lambda flag=flag: recover_dual_store_logistics(
                    db,
                    specs=specs,
                    settings=_settings(**{flag: True}),
                    now=NOW,
                ),
            )
            db.rollback()

        wrong_hash_specs = [
            StoreSpec(specs[0].store_id, "0" * 64),
            specs[1],
        ]
        _expect_blocked(
            "t24_logistics_recovery_store_name_mismatch",
            lambda: recover_dual_store_logistics(
                db, specs=wrong_hash_specs, settings=_settings(), now=NOW
            ),
        )
        db.rollback()

        leased = db.get(SyncCheckpoint, seeded[store_ids[0]]["products"].id)
        leased.lease_token = "active-lease"
        leased.lease_expires_at = NOW + timedelta(minutes=5)
        db.commit()
        _expect_blocked(
            "t24_logistics_recovery_active_lease_present",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(), now=NOW
            ),
        )
        db.rollback()
        leased = db.get(SyncCheckpoint, leased.id)
        leased.lease_token = None
        leased.lease_expires_at = None
        db.commit()

        orders = db.get(SyncCheckpoint, seeded[store_ids[0]]["orders"].id)
        orders.fresh_until = NOW
        db.commit()
        _expect_blocked(
            "t24_logistics_recovery_orders_not_fresh",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(), now=NOW
            ),
        )
        db.rollback()
        orders = db.get(SyncCheckpoint, orders.id)
        orders.fresh_until = NOW + timedelta(minutes=20)
        db.commit()

        second_logistics = db.get(
            SyncCheckpoint,
            seeded[store_ids[1]]["logistics"].id,
        )
        second_logistics.last_error_code = "network_timeout"
        db.commit()
        _expect_blocked(
            "t24_logistics_recovery_checkpoint_state_invalid",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(), now=NOW
            ),
        )
        db.rollback()
        first_logistics = db.get(
            SyncCheckpoint,
            seeded[store_ids[0]]["logistics"].id,
        )
        assert first_logistics.status == "blocked"
        assert first_logistics.last_error_code == RECOVERABLE_ERROR_CODE
        assert db.query(SyncLog).filter_by(sync_type=RECOVERY_SYNC_TYPE).count() == 0
        second_logistics = db.get(SyncCheckpoint, second_logistics.id)
        second_logistics.last_error_code = RECOVERABLE_ERROR_CODE
        db.commit()

        non_logistics_ids = [
            resources[resource].id
            for resources in seeded.values()
            for resource in ("orders", "inquiries", "products")
        ]
        before_non_logistics = {
            row.id: (
                row.status,
                row.automatic_read_enabled,
                row.next_run_at,
                row.fresh_until,
                row.last_error_code,
                row.lease_token,
                row.lease_expires_at,
            )
            for row in db.scalars(select(SyncCheckpoint).where(
                SyncCheckpoint.id.in_(non_logistics_ids)
            )).all()
        }
        original_cursors = {
            store_id: db.get(
                SyncCheckpoint,
                seeded[store_id]["logistics"].id,
            ).cursor_value
            for store_id in store_ids
        }
        result = recover_dual_store_logistics(
            db,
            specs=list(reversed(specs)),
            settings=_settings(),
            now=NOW,
        )
        assert result["status"] == "scheduled"
        assert result["store_ids"] == store_ids
        assert result["checkpoint_count"] == 2
        assert result["first_run_spacing_seconds"] == 60
        assert result["platform_write"] is False
        assert result["network_called"] is False
        assert [item["next_run_at"] for item in result["schedules"]] == [
            NOW.isoformat(),
            (NOW + FIRST_RUN_SPACING).isoformat(),
        ]

        for index, store_id in enumerate(store_ids):
            row = db.get(SyncCheckpoint, seeded[store_id]["logistics"].id)
            assert row.status == "idle" and row.automatic_read_enabled is True
            assert row.last_error_code is None and row.retry_count == 0
            assert row.lease_token is None and row.lease_expires_at is None
            assert row.cursor_value == original_cursors[store_id]
            expected = NOW + FIRST_RUN_SPACING * index
            actual = row.next_run_at
            if actual.tzinfo is None:
                actual = actual.replace(tzinfo=timezone.utc)
            assert actual == expected

        after_non_logistics = {
            row.id: (
                row.status,
                row.automatic_read_enabled,
                row.next_run_at,
                row.fresh_until,
                row.last_error_code,
                row.lease_token,
                row.lease_expires_at,
            )
            for row in db.scalars(select(SyncCheckpoint).where(
                SyncCheckpoint.id.in_(non_logistics_ids)
            )).all()
        }
        assert after_non_logistics == before_non_logistics

        logs = db.scalars(select(SyncLog).where(
            SyncLog.sync_type == RECOVERY_SYNC_TYPE
        ).order_by(SyncLog.store_id.asc())).all()
        assert len(logs) == 2
        assert [log.store_id for log in logs] == store_ids
        for index, log in enumerate(logs):
            assert log.status == "success" and log.error_detail is None
            assert log.raw_summary == {
                "status": "scheduled",
                "resource": "logistics",
                "recovered_error_code": RECOVERABLE_ERROR_CODE,
                "first_run_offset_seconds": index * 60,
                "platform_write": False,
                "network_called": False,
            }
            log_text = f"{log.message} {log.error_detail} {log.raw_summary}"
            assert all(f"T24 Logistics Recovery {number}" not in log_text for number in (1, 2))

        schedules_before_repeat = [
            db.get(SyncCheckpoint, seeded[store_id]["logistics"].id).next_run_at
            for store_id in store_ids
        ]
        _expect_blocked(
            "t24_logistics_recovery_already_applied",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(), now=NOW
            ),
        )
        db.rollback()
        assert db.query(SyncLog).filter_by(sync_type=RECOVERY_SYNC_TYPE).count() == 2
        assert [
            db.get(SyncCheckpoint, seeded[store_id]["logistics"].id).next_run_at
            for store_id in store_ids
        ] == schedules_before_repeat

        # The durable marker also prevents a second recovery cycle if a later
        # logistics run returns to the same blocked error.
        for store_id in store_ids:
            row = db.get(SyncCheckpoint, seeded[store_id]["logistics"].id)
            row.status = "blocked"
            row.automatic_read_enabled = False
            row.next_run_at = None
            row.last_error_code = RECOVERABLE_ERROR_CODE
        db.commit()
        _expect_blocked(
            "t24_logistics_recovery_already_applied",
            lambda: recover_dual_store_logistics(
                db, specs=specs, settings=_settings(), now=NOW + timedelta(minutes=2)
            ),
        )
        db.rollback()
        assert db.query(SyncLog).filter_by(sync_type=RECOVERY_SYNC_TYPE).count() == 2

    print("verify_recover_t24_dual_store_logistics: ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        DB_PATH.unlink(missing_ok=True)
