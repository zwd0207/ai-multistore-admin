import os
import sys
import tempfile
import uuid
import hashlib
import json
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t18-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "APP_ENV": "test",
    "REAL_API_TEST_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
    "SHIPPING_PLATFORM_WRITE_ENABLED": "false",
    "PXG_NAVER_SHIPPING_PILOT_ENABLED": "false",
})

import app.models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.auth import ErpUser  # noqa: E402
from app.models.operation_audit_log import OperationAuditLog  # noqa: E402
from app.models.order import Order  # noqa: E402
from app.models.order_status_event import OrderStatusEvent  # noqa: E402
from app.models.shipping import (  # noqa: E402
    ShippingTrackingImportBatch,
    ShippingTrackingImportRow,
    WarehouseShippingApprovalGrant,
    WarehouseShippingBatch,
    WarehouseShippingBatchOrder,
)
from app.models.store import Store  # noqa: E402
from app.services import shipping_service, warehouse_shipping_service  # noqa: E402
from app.services import operator_trial_service  # noqa: E402
from app.services.operator_trial_service import TRIAL_STORE_NAME  # noqa: E402


ACTOR = {"role": "operator", "actor_id": "t18-operator"}
TRACKING_NUMBER = "T18-TRACKING-998877"
TEST_CREDENTIAL_UPDATED_AT = datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc)


def mock_credential(*, credential_id: int = 1, client_id: str = "t18-mock-client", updated_at=TEST_CREDENTIAL_UPDATED_AT):
    return SimpleNamespace(id=credential_id, client_id=client_id, updated_at=updated_at)


def mock_credential_binding(*, credential_id: int = 1, client_id: str = "t18-mock-client", updated_at=TEST_CREDENTIAL_UPDATED_AT) -> str:
    marker = {
        "credential_id": credential_id,
        "client_id": client_id,
        "updated_at": updated_at.isoformat(),
    }
    return hashlib.sha256(json.dumps(marker, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def settings(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        real_api_write_enabled=enabled,
        shipping_platform_write_enabled=enabled,
        pxg_naver_shipping_pilot_enabled=enabled,
        platform_order_write_enabled=False,
    )


def reset_database() -> None:
    if DB_PATH.exists():
        Base.metadata.drop_all(bind=engine)
    init_db()


def fixture():
    with SessionLocal() as db:
        store = Store(name=TRIAL_STORE_NAME, platform="naver")
        user = ErpUser(
            user_key_hash="t18-operator-key",
            display_name="T18 Operator",
            status="active",
        )
        db.add_all([store, user])
        db.flush()
        order = Order(
            store_id=store.id,
            platform="naver",
            external_order_id="t18-order-001",
            external_product_order_id="t18-product-order-001",
            product_name="PXG pilot bag",
            quantity=1,
            order_amount=1,
            currency="KRW",
            # The existing warehouse-confirmation flow has already moved the
            # local workflow state to DISPATCHED. T18 separately verifies the
            # latest Naver state before any platform POST.
            order_status="DISPATCHED",
            ordered_at=shipping_service.get_utc_now(),
            source_type="t18-verify",
            raw_data={
                "tracking_number": TRACKING_NUMBER,
                "shipping_tracking_number": TRACKING_NUMBER,
                "legacy": {"invoice_number": TRACKING_NUMBER},
            },
        )
        db.add(order)
        db.flush()
        tracking_batch = ShippingTrackingImportBatch(
            store_id=store.id,
            platform="naver",
            file_type="tracking_upload",
            file_format="xlsx",
            source_file_name="t18-return.xlsx",
            row_count=1,
            ready_row_count=1,
            audit_correlation_id="t18-import",
        )
        db.add(tracking_batch)
        db.flush()
        tracking_row = ShippingTrackingImportRow(
            import_batch_id=tracking_batch.id,
            store_id=store.id,
            platform="naver",
            order_reference=order.external_order_id,
            product_order_reference=order.external_product_order_id,
            carrier="CJ",
            tracking_number=TRACKING_NUMBER,
            shipped_at="2026-07-13T09:30:00+09:00",
            row_status="ready_for_confirmation",
        )
        batch = WarehouseShippingBatch(
            batch_no=f"T18-{uuid.uuid4().hex[:10]}",
            store_id=store.id,
            platform="naver",
            status="ready_to_writeback",
            version=7,
            tracking_import_batch_id=tracking_batch.id,
        )
        db.add_all([tracking_row, batch])
        db.flush()
        batch_row = WarehouseShippingBatchOrder(
            batch_id=batch.id,
            local_order_id=order.id,
            store_id=store.id,
            platform="naver",
            order_reference=order.external_order_id,
            product_order_reference=order.external_product_order_id,
            product_name=order.product_name,
            quantity=1,
            row_status="ready_for_writeback",
            is_active=True,
            active_lock="active",
            carrier="CJ",
            tracking_number_hash=shipping_service._safe_hash_identifier(TRACKING_NUMBER),
            shipped_at=tracking_row.shipped_at,
        )
        db.add(batch_row)
        db.commit()
        return store.id, user.id, order.id, batch.id


def preflight(
    product_order_id: str,
    *,
    status: str = "PAYED",
    claim: str = "",
    carrier_code: str | None = None,
    tracking_number_hash: str | None = None,
    writeback_state: str = "",
    credential_binding: str | None = None,
):
    def _read(*_args, **_kwargs):
        return {
            "credential_id": 1,
            "credential_binding": credential_binding or mock_credential_binding(),
            "platform_checked_at": shipping_service.get_utc_now(),
            "states": [{
                "product_order_id": product_order_id,
                "order_status": status,
                "claim_status": claim,
                # A normal pre-write Naver order has not yet received a
                # carrier or tracking number. Reconciliation supplies an
                # exact platform logistics record explicitly.
                "carrier_code": carrier_code,
                "tracking_number_hash": tracking_number_hash,
                "writeback_state": writeback_state,
            }],
        }, None
    return _read


def approve(db, *, batch_id: int, user_id: int):
    return warehouse_shipping_service.issue_approval_grant(
        db,
        batch_id=batch_id,
        user_id=user_id,
        grant_scope="writeback",
        t18_pilot_execution=True,
    )


def execute(db, *, batch_id: int, user_id: int, token: str):
    return warehouse_shipping_service.execute_warehouse_batch_writeback(
        db,
        batch_id=batch_id,
        user_id=user_id,
        approval_token=token,
        manual_approval=True,
        final_operator_confirmation=True,
        real_api_call_requested=True,
        actor_context=ACTOR,
        t18_pilot_execution=True,
        action="execute",
    )


def direct_write(db, *, store_id: int, tracking_rows: list[dict], **overrides):
    payload = {
        "store_id": store_id,
        "tracking_rows": tracking_rows,
        "manual_approval": True,
        "matching_contract_acknowledged": True,
        "backup_evidence_acknowledged": True,
        "audit_evidence_acknowledged": True,
        "local_status_evidence_acknowledged": True,
        "naver_writeback_boundary_acknowledged": True,
        "operator_checklist_acknowledged": True,
        "execution_approval": True,
        "dry_run_evidence_acknowledged": True,
        "permission_evidence_acknowledged": True,
        "final_operator_confirmation": True,
        "real_api_call_requested": True,
        "actor_context": ACTOR,
        "t18_pilot_execution": True,
    }
    payload.update(overrides)
    return shipping_service.execute_naver_shipment_writeback(db, **payload)


def tracking_rows() -> list[dict]:
    return [{
        "order_reference": "t18-order-001",
        "product_order_reference": "t18-product-order-001",
        "carrier": "CJ",
        "tracking_number": TRACKING_NUMBER,
        "shipped_at": "2026-07-13T09:30:00+09:00",
    }]


def test_closed_gates_never_read_or_write() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    calls = {"preflight": 0}

    def no_preflight(*_args, **_kwargs):
        calls["preflight"] += 1
        raise AssertionError("preflight must not run while a write gate is closed")

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=False)), patch.object(
        warehouse_shipping_service, "_t18_platform_preflight", no_preflight,
    ):
        result = approve(db, batch_id=batch_id, user_id=user_id)
        assert result["status"] == "blocked", result
        assert result["skip_reason"] == "real_api_write_disabled", result
        assert result["token_request_count"] == 0 and result["http_request_count"] == 0, result
        assert result["writeback_capability"]["pilot_enabled"] is False, result
    assert calls["preflight"] == 0, calls


def test_bottom_level_gate_blocks_token_and_http() -> None:
    reset_database()
    store_id, _user_id, _order_id, _batch_id = fixture()
    rows = [{
        "order_reference": "t18-order-001",
        "product_order_reference": "t18-product-order-001",
        "carrier": "CJ",
        "tracking_number": TRACKING_NUMBER,
        "shipped_at": "2026-07-13T09:30:00+09:00",
    }]
    for setting_name, expected_reason in (
        ("real_api_write_enabled", "real_api_write_disabled"),
        ("shipping_platform_write_enabled", "shipping_platform_write_disabled"),
        ("pxg_naver_shipping_pilot_enabled", "pxg_naver_shipping_pilot_disabled"),
    ):
        runtime_settings = settings(enabled=True)
        setattr(runtime_settings, setting_name, False)
        calls = {"credential": 0, "token": 0, "http": 0}

        def credential(*_args, **_kwargs):
            calls["credential"] += 1
            raise AssertionError("credential lookup must not run behind a closed write gate")

        with SessionLocal() as db, patch.object(shipping_service, "get_settings", lambda: runtime_settings), patch.object(
            shipping_service, "_ensure_naver_shipping_credential", credential,
        ), patch.object(
            shipping_service.api_credential_readiness_service,
            "_request_naver_token_from_context",
            lambda _context: calls.__setitem__("token", calls["token"] + 1),
        ), patch.object(
            shipping_service,
            "_post_naver_shipment_dispatch",
            lambda **_kwargs: calls.__setitem__("http", calls["http"] + 1),
        ):
            result = shipping_service.execute_naver_shipment_writeback(
                db,
                store_id=store_id,
                tracking_rows=rows,
                manual_approval=True,
                matching_contract_acknowledged=True,
                backup_evidence_acknowledged=True,
                audit_evidence_acknowledged=True,
                local_status_evidence_acknowledged=True,
                naver_writeback_boundary_acknowledged=True,
                operator_checklist_acknowledged=True,
                execution_approval=True,
                dry_run_evidence_acknowledged=True,
                permission_evidence_acknowledged=True,
                final_operator_confirmation=True,
                real_api_call_requested=True,
                actor_context=ACTOR,
                t18_pilot_execution=True,
            )
            assert result["status"] == "blocked" and result["skip_reason"] == expected_reason, result
            assert result["token_request_count"] == 0 and result["http_request_count"] == 0, result
        assert calls == {"credential": 0, "token": 0, "http": 0}, calls


def test_all_eight_gate_combinations_and_proof_requirement() -> None:
    reset_database()
    store_id, _user_id, _order_id, _batch_id = fixture()
    rows = tracking_rows()
    for real_write, shipping_write, pilot_write in product((False, True), repeat=3):
        runtime_settings = settings(enabled=True)
        runtime_settings.real_api_write_enabled = real_write
        runtime_settings.shipping_platform_write_enabled = shipping_write
        runtime_settings.pxg_naver_shipping_pilot_enabled = pilot_write
        calls = {"credential": 0, "token": 0, "http": 0}

        def credential(*_args, **_kwargs):
            calls["credential"] += 1
            raise AssertionError("credential lookup must require all gates and an internal proof")

        with SessionLocal() as db, patch.object(shipping_service, "get_settings", lambda: runtime_settings), patch.object(
            shipping_service, "_ensure_naver_shipping_credential", credential,
        ), patch.object(
            shipping_service.api_credential_readiness_service,
            "_request_naver_token_from_context",
            lambda _context: calls.__setitem__("token", calls["token"] + 1),
        ), patch.object(
            shipping_service,
            "_post_naver_shipment_dispatch",
            lambda **_kwargs: calls.__setitem__("http", calls["http"] + 1),
        ):
            result = direct_write(db, store_id=store_id, tracking_rows=rows)
        if not real_write:
            assert result["skip_reason"] == "real_api_write_disabled", result
        elif not shipping_write:
            assert result["skip_reason"] == "shipping_platform_write_disabled", result
        elif not pilot_write:
            assert result["skip_reason"] == "pxg_naver_shipping_pilot_disabled", result
        else:
            assert result["skip_reason"] == "t18_execution_proof_required", result
        assert calls == {"credential": 0, "token": 0, "http": 0}, (real_write, shipping_write, pilot_write, calls)


def test_platform_order_write_flag_remains_closed() -> None:
    reset_database()
    store_id, _user_id, _order_id, _batch_id = fixture()
    runtime_settings = settings(enabled=True)
    runtime_settings.platform_order_write_enabled = True
    calls = {"credential": 0}
    with SessionLocal() as db, patch.object(shipping_service, "get_settings", lambda: runtime_settings), patch.object(
        shipping_service,
        "_ensure_naver_shipping_credential",
        lambda *_args, **_kwargs: calls.__setitem__("credential", calls["credential"] + 1),
    ):
        result = direct_write(db, store_id=store_id, tracking_rows=tracking_rows())
    assert result["skip_reason"] == "platform_order_write_must_remain_disabled", result
    assert calls["credential"] == 0, calls


def test_exact_approval_execution_and_privacy() -> None:
    reset_database()
    _store_id, user_id, order_id, batch_id = fixture()
    preflight_calls = {"count": 0}
    post_calls = {"count": 0}

    def checked_preflight(*args, **kwargs):
        preflight_calls["count"] += 1
        return preflight("t18-product-order-001")(*args, **kwargs)

    def token_request(_context):
        return "mock-access-token", 200

    def post_dispatch(*, candidates, **_kwargs):
        post_calls["count"] += 1
        assert len(candidates) == 1, candidates
        assert candidates[0]["product_order_id"] == "t18-product-order-001", candidates
        return {
            "success": True,
            "http_status": 200,
            "success_product_order_ids": ["t18-product-order-001"],
            "fail_product_order_infos": [],
            "diagnostics": {"raw_response_saved": False},
        }

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", checked_preflight), patch.object(
        shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", token_request,
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential()), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(shipping_service, "_post_naver_shipment_dispatch", post_dispatch):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        assert approval["status"] == "approval_granted", approval
        assert approval["writeback_capability"]["candidate_count"] == 1, approval
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "success", result
        assert result["real_api_called"] is True, result
        assert result["writeback_capability"]["status"] == "completed", result
        assert TRACKING_NUMBER not in str(result), result
        replay = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert replay["status"] == "blocked", replay

        grant = db.query(WarehouseShippingApprovalGrant).one()
        assert grant.attempt_status == "success", grant.attempt_status
        assert grant.attempt_token_hash and grant.attempt_token_hash != grant.token_hash
        order = db.get(Order, order_id)
        assert TRACKING_NUMBER not in str(order.raw_data), order.raw_data
        event = db.query(OrderStatusEvent).filter(OrderStatusEvent.order_id == order_id).one()
        assert TRACKING_NUMBER not in str(event.safe_metadata), event.safe_metadata
        audit_rows = db.query(OperationAuditLog).filter(OperationAuditLog.store_id == order.store_id).all()
        assert audit_rows and all(TRACKING_NUMBER not in str(row) for row in audit_rows), audit_rows
        assert any((row.safety_flags or {}).get("real_api_called") is True for row in audit_rows), audit_rows
    assert preflight_calls["count"] == 2, preflight_calls
    assert post_calls["count"] == 1, post_calls


def test_platform_state_change_invalidates_approval() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    states = ["PAYED", "READY"]
    post_calls = {"count": 0}

    def changing_preflight(*args, **kwargs):
        return preflight("t18-product-order-001", status=states.pop(0))(*args, **kwargs)

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", changing_preflight), patch.object(
        shipping_service, "_post_naver_shipment_dispatch", lambda **_kwargs: post_calls.__setitem__("count", post_calls["count"] + 1),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        assert approval["status"] == "approval_granted", approval
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "blocked", result
        assert result["skip_reason"] == "shipping_approval_candidate_changed", result
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "prepared"
    assert post_calls["count"] == 0, post_calls


def test_capability_contract_and_platform_logistics_guards() -> None:
    reset_database()
    store_id, user_id, _order_id, batch_id = fixture()
    masked_tracking = warehouse_shipping_service.order_service._mask_tracking_number(TRACKING_NUMBER)
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)):
        listing = warehouse_shipping_service.list_warehouse_batches(
            db, store_id=store_id, platform="naver", include_rows=False,
        )
        capability = next(item for item in listing["items"] if item["id"] == batch_id)["writeback_capability"]
        assert capability["status"] == "approval_required", capability
        assert capability["allowed_action"] == "approve", capability
        assert capability["store_name"] == TRIAL_STORE_NAME, capability
        assert capability["product_order_reference"] == "t18-product-order-001", capability
        assert capability["carrier"] == "CJ", capability
        assert capability["tracking_number_masked"] == masked_tracking, capability
        assert capability["platform_latest_status"] is None, capability
        assert TRACKING_NUMBER not in str(capability), capability

        with patch.object(
            warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001"),
        ):
            approval = approve(db, batch_id=batch_id, user_id=user_id)
        assert approval["status"] == "approval_granted", approval
        approved_capability = approval["writeback_capability"]
        assert approved_capability["allowed_action"] == "execute", approved_capability
        assert approved_capability["store_name"] == TRIAL_STORE_NAME, approved_capability
        assert approved_capability["product_order_reference"] == "t18-product-order-001", approved_capability
        assert approved_capability["carrier"] == "CJ", approved_capability
        assert approved_capability["tracking_number_masked"] == masked_tracking, approved_capability
        assert approved_capability["platform_latest_status"] == "PAYED", approved_capability
        assert TRACKING_NUMBER not in str(approved_capability), approved_capability

    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        warehouse_shipping_service,
        "_t18_platform_preflight",
        preflight(
            "t18-product-order-001",
            tracking_number_hash=shipping_service._safe_hash_identifier(TRACKING_NUMBER),
        ),
    ):
        result = approve(db, batch_id=batch_id, user_id=user_id)
        assert result["status"] == "blocked", result
        assert result["skip_reason"] == "naver_platform_tracking_already_present", result
        assert db.query(WarehouseShippingApprovalGrant).count() == 0

    cases = (
        ("carrier", {"carrier_code": "HANJIN"}, "shipping_approval_candidate_changed"),
        (
            "tracking",
            {"tracking_number_hash": shipping_service._safe_hash_identifier("platform-tracking")},
            "naver_platform_tracking_already_present",
        ),
        (
            "writeback_state",
            {"writeback_state": "PENDING"},
            "naver_platform_writeback_state_not_writeback_eligible",
        ),
    )
    for case_name, changed_state, expected_reason in cases:
        reset_database()
        _store_id, user_id, _order_id, batch_id = fixture()
        preflights = [
            preflight("t18-product-order-001"),
            preflight("t18-product-order-001", **changed_state),
        ]
        post_calls = {"count": 0}

        def changing_preflight(*args, **kwargs):
            return preflights.pop(0)(*args, **kwargs)

        with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
            warehouse_shipping_service, "_t18_platform_preflight", changing_preflight,
        ), patch.object(
            shipping_service, "_post_naver_shipment_dispatch", lambda **_kwargs: post_calls.__setitem__("count", post_calls["count"] + 1),
        ):
            approval = approve(db, batch_id=batch_id, user_id=user_id)
            assert approval["status"] == "approval_granted", (case_name, approval)
            result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
            assert result["status"] == "blocked", (case_name, result)
            assert result["skip_reason"] == expected_reason, (case_name, result)
            assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "prepared"
        assert post_calls["count"] == 0, (case_name, post_calls)


def test_prepost_failures_do_not_consume_attempt() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    post_calls = {"count": 0}

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
        shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential(credential_id=2),
    ), patch.object(
        shipping_service,
        "_post_naver_shipment_dispatch",
        lambda **_kwargs: post_calls.__setitem__("count", post_calls["count"] + 1),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "blocked", result
        assert result["skip_reason"] == "t18_expected_credential_mismatch", result
        grant = db.query(WarehouseShippingApprovalGrant).one()
        assert grant.attempt_status == "prepared" and grant.used_at is None, grant.attempt_status
        assert post_calls["count"] == 0, post_calls

    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
        shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential(client_id="rotated-client"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "blocked", result
        assert result["skip_reason"] == "t18_credential_binding_changed", result
        grant = db.query(WarehouseShippingApprovalGrant).one()
        assert grant.attempt_status == "prepared" and grant.used_at is None, grant.attempt_status

    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
        shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential(),
    ), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(
        shipping_service.api_credential_readiness_service,
        "_request_naver_token_from_context",
        side_effect=RuntimeError("mock authentication failure"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "blocked", result
        assert result["skip_reason"] == "naver_write_authentication_failed", result
        grant = db.query(WarehouseShippingApprovalGrant).one()
        assert grant.attempt_status == "prepared" and grant.used_at is None, grant.attempt_status


def test_token_then_expired_claim_never_posts() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    calls = {"token": 0, "post": 0}

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(
        warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001"),
    ), patch.object(
        shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential(),
    ), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(
        shipping_service.api_credential_readiness_service,
        "_request_naver_token_from_context",
        lambda _context: _expire_approval_after_token(db, calls),
    ), patch.object(
        shipping_service,
        "_post_naver_shipment_dispatch",
        lambda **_kwargs: calls.__setitem__("post", calls["post"] + 1),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "blocked", result
        assert result["skip_reason"] == "shipping_approval_token_invalid", result
        grant = db.query(WarehouseShippingApprovalGrant).one()
        assert grant.attempt_status == "prepared" and grant.used_at is None, grant
    assert calls == {"token": 1, "post": 0}, calls


def _expire_approval_after_token(db, calls: dict[str, int]) -> tuple[str, int]:
    calls["token"] += 1
    grant = db.query(WarehouseShippingApprovalGrant).one()
    grant.expires_at = shipping_service.get_utc_now() - timedelta(seconds=1)
    db.commit()
    return "mock-access-token", 200


def test_wrong_user_expired_token_and_restart_attempts_are_blocked() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001"),
    ):
        other_user = ErpUser(user_key_hash="t18-other-user", display_name="Other", status="active")
        db.add(other_user)
        db.commit()
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        wrong_user = execute(db, batch_id=batch_id, user_id=other_user.id, token=approval["approval_token"])
        assert wrong_user["skip_reason"] == "shipping_approval_token_invalid", wrong_user
        grant = db.query(WarehouseShippingApprovalGrant).one()
        assert grant.attempt_status == "prepared", grant.attempt_status
        grant.expires_at = shipping_service.get_utc_now() - timedelta(seconds=1)
        db.commit()
        expired = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert expired["skip_reason"] == "shipping_approval_token_invalid", expired

    for attempt_status in ("requesting", "unknown"):
        reset_database()
        _store_id, user_id, _order_id, batch_id = fixture()
        with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
            warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001"),
        ):
            approval = approve(db, batch_id=batch_id, user_id=user_id)
            grant = db.query(WarehouseShippingApprovalGrant).one()
            grant.attempt_status = attempt_status
            grant.used_at = shipping_service.get_utc_now()
            grant.attempt_token_hash = "restart-proof"
            db.commit()
            with patch.object(
                warehouse_shipping_service,
                "_t18_platform_preflight",
                side_effect=AssertionError("restart protection must block before another platform read or POST"),
            ):
                blocked = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
            assert blocked["status"] == "blocked", blocked
            assert blocked["skip_reason"] == "shipping_approval_attempt_already_claimed", blocked


def test_developer_actor_is_rejected_before_preflight() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        with patch.object(
            warehouse_shipping_service,
            "_t18_platform_preflight",
            side_effect=AssertionError("developer identity must be rejected before preflight"),
        ):
            result = warehouse_shipping_service.execute_warehouse_batch_writeback(
                db,
                batch_id=batch_id,
                user_id=user_id,
                approval_token=approval["approval_token"],
                manual_approval=True,
                final_operator_confirmation=True,
                real_api_call_requested=True,
                actor_context={"role": "developer", "actor_id": "dev"},
                t18_pilot_execution=True,
                action="execute",
            )
        assert result["skip_reason"] == "operator_role_required", result


def test_unknown_requires_reconciliation_without_resend() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    post_calls = {"count": 0}
    state = {"value": "PAYED"}

    def current_preflight(*args, **kwargs):
        platform_logistics = {}
        if state["value"] == "DISPATCHED":
            platform_logistics = {
                "carrier_code": shipping_service._normalize_naver_delivery_company_code("CJ"),
                "tracking_number_hash": shipping_service._safe_hash_identifier(TRACKING_NUMBER),
            }
        return preflight("t18-product-order-001", status=state["value"], **platform_logistics)(*args, **kwargs)

    def timeout_post(**_kwargs):
        post_calls["count"] += 1
        raise TimeoutError("mock timeout only")

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", current_preflight), patch.object(
        shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", lambda _context: ("mock", 200),
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential()), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(shipping_service, "_post_naver_shipment_dispatch", timeout_post):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "unknown", result
        assert result["writeback_capability"]["allowed_action"] == "reconcile", result
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "unknown"
        state["value"] = "DISPATCHED"
        reconciled = warehouse_shipping_service.execute_warehouse_batch_writeback(
            db,
            batch_id=batch_id,
            manual_approval=False,
            final_operator_confirmation=False,
            real_api_call_requested=False,
            actor_context=ACTOR,
            t18_pilot_execution=True,
            action="reconcile",
        )
        assert reconciled["status"] == "reconciled_success", reconciled
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "reconciled_success"
    assert post_calls["count"] == 1, post_calls


def test_ambiguous_post_results_are_unknown_and_privacy_safe() -> None:
    cases = {
        "http_5xx": lambda _candidates: {
            "success": False, "http_status": 503, "error_code": "shipment_dispatch_failed",
        },
        "timeout": lambda _candidates: (_ for _ in ()).throw(TimeoutError("mock timeout")),
        "invalid_json": lambda _candidates: (_ for _ in ()).throw(ValueError("mock malformed JSON")),
        "missing_exact_id": lambda _candidates: {
            "success": True, "http_status": 200, "success_product_order_ids": [], "fail_product_order_infos": [],
        },
    }
    for case_name, behavior in cases.items():
        reset_database()
        _store_id, user_id, _order_id, batch_id = fixture()
        calls = {"post": 0}

        def post_dispatch(*, candidates, **_kwargs):
            calls["post"] += 1
            return behavior(candidates)

        with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
            shipping_service, "get_settings", lambda: settings(enabled=True),
        ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
            shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", lambda _context: ("mock", 200),
        ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential()), patch.object(
            shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
        ), patch.object(shipping_service, "_post_naver_shipment_dispatch", post_dispatch):
            approval = approve(db, batch_id=batch_id, user_id=user_id)
            result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
            assert result["status"] == "unknown", (case_name, result)
            assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "unknown", case_name
            assert TRACKING_NUMBER not in str(result), (case_name, result)
        assert calls["post"] == 1, (case_name, calls)


def test_reconcile_works_with_write_gates_closed_and_requires_exact_logistics() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
        shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", lambda _context: ("mock", 200),
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential()), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(
        shipping_service, "_post_naver_shipment_dispatch", side_effect=TimeoutError("ambiguous post"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "unknown", result

        with patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=False)), patch.object(
            warehouse_shipping_service,
            "_t18_platform_preflight",
            preflight(
                "t18-product-order-001",
                status="DISPATCHED",
                carrier_code=shipping_service._normalize_naver_delivery_company_code("CJ"),
                tracking_number_hash=shipping_service._safe_hash_identifier(TRACKING_NUMBER),
            ),
        ):
            reconciled = warehouse_shipping_service.execute_warehouse_batch_writeback(
                db,
                batch_id=batch_id,
                manual_approval=False,
                final_operator_confirmation=False,
                real_api_call_requested=False,
                actor_context=ACTOR,
                t18_pilot_execution=True,
                action="reconcile",
            )
        assert reconciled["status"] == "reconciled_success", reconciled
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "reconciled_success"

    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
        shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", lambda _context: ("mock", 200),
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential()), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(
        shipping_service, "_post_naver_shipment_dispatch", side_effect=TimeoutError("ambiguous post"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        assert execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])["status"] == "unknown"
        with patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=False)), patch.object(
            warehouse_shipping_service,
            "_t18_platform_preflight",
            preflight(
                "t18-product-order-001",
                status="DISPATCHED",
                tracking_number_hash=shipping_service._safe_hash_identifier("different-tracking"),
            ),
        ):
            mismatch = warehouse_shipping_service.execute_warehouse_batch_writeback(
                db, batch_id=batch_id, manual_approval=False, final_operator_confirmation=False,
                real_api_call_requested=False, actor_context=ACTOR, t18_pilot_execution=True, action="reconcile",
            )
        assert mismatch["status"] == "unknown", mismatch
        assert mismatch["skip_reason"] == "naver_reconciliation_exact_logistics_not_confirmed", mismatch
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "unknown"


def test_reconciled_not_applied_consumes_the_single_attempt() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
        shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", lambda _context: ("mock", 200),
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential()), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(
        shipping_service, "_post_naver_shipment_dispatch", side_effect=TimeoutError("ambiguous post"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        assert execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])["status"] == "unknown"
        with patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=False)), patch.object(
            warehouse_shipping_service,
            "_t18_platform_preflight",
            preflight("t18-product-order-001", status="PAYED", writeback_state="NOT_APPLIED"),
        ):
            reconciled = warehouse_shipping_service.execute_warehouse_batch_writeback(
                db, batch_id=batch_id, manual_approval=False, final_operator_confirmation=False,
                real_api_call_requested=False, actor_context=ACTOR, t18_pilot_execution=True, action="reconcile",
            )
        assert reconciled["status"] == "reconciled_not_applied", reconciled
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "reconciled_not_applied"
        next_approval = approve(db, batch_id=batch_id, user_id=user_id)
        assert next_approval["skip_reason"] == "pxg_naver_pilot_attempt_limit_reached", next_approval


def test_multi_row_cross_store_claim_and_concurrent_attempt_guards() -> None:
    reset_database()
    store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)):
        batch = db.get(WarehouseShippingBatch, batch_id)
        extra_order = Order(
            store_id=store_id,
            platform="naver",
            external_order_id="t18-order-002",
            external_product_order_id="t18-product-order-002",
            product_name="PXG pilot bag second item",
            quantity=1,
            order_amount=1,
            currency="KRW",
            order_status="DISPATCHED",
            ordered_at=shipping_service.get_utc_now(),
            source_type="t18-verify",
            raw_data={},
        )
        db.add(extra_order)
        db.flush()
        db.add(ShippingTrackingImportRow(
            import_batch_id=batch.tracking_import_batch_id,
            store_id=store_id,
            platform="naver",
            order_reference=extra_order.external_order_id,
            product_order_reference=extra_order.external_product_order_id,
            carrier="CJ",
            tracking_number="T18-TRACKING-SECOND",
            shipped_at="2026-07-13T09:40:00+09:00",
            row_status="ready_for_confirmation",
        ))
        db.add(WarehouseShippingBatchOrder(
            batch_id=batch.id,
            local_order_id=extra_order.id,
            store_id=store_id,
            platform="naver",
            order_reference=extra_order.external_order_id,
            product_order_reference=extra_order.external_product_order_id,
            product_name=extra_order.product_name,
            quantity=1,
            row_status="ready_for_writeback",
            is_active=True,
            active_lock="active",
            carrier="CJ",
            tracking_number_hash=shipping_service._safe_hash_identifier("T18-TRACKING-SECOND"),
            shipped_at="2026-07-13T09:40:00+09:00",
        ))
        db.commit()
        multi_row = approve(db, batch_id=batch_id, user_id=user_id)
        assert multi_row["skip_reason"] == "pxg_naver_pilot_single_row_required", multi_row
        assert db.query(WarehouseShippingApprovalGrant).count() == 0

    reset_database()
    store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001", claim="CANCEL_REQUEST"),
    ):
        claim_blocked = approve(db, batch_id=batch_id, user_id=user_id)
        assert claim_blocked["skip_reason"] == "naver_platform_claim_present", claim_blocked
        assert db.query(WarehouseShippingApprovalGrant).count() == 0

        other_store = Store(name="outside PXG pilot", platform="naver")
        db.add(other_store)
        db.flush()
        batch = db.get(WarehouseShippingBatch, batch_id)
        batch.store_id = other_store.id
        db.commit()
        cross_store = approve(db, batch_id=batch_id, user_id=user_id)
        assert cross_store["skip_reason"] == "pxg_naver_pilot_store_required", cross_store

    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        grant = db.query(WarehouseShippingApprovalGrant).one()
        batch = db.get(WarehouseShippingBatch, batch_id)
        first, nonce, first_error = warehouse_shipping_service._t18_claim_attempt(
            db, batch=batch, grant_id=grant.id, user_id=user_id, candidate_hash=grant.candidate_hash,
        )
        second, _second_nonce, second_error = warehouse_shipping_service._t18_claim_attempt(
            db, batch=batch, grant_id=grant.id, user_id=user_id, candidate_hash=grant.candidate_hash,
        )
        assert first is not None and nonce and first_error is None
        assert second is not None and second_error == "shipping_approval_attempt_already_claimed"
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "requesting"


def test_product_order_reference_never_updates_a_sibling_order() -> None:
    reset_database()
    store_id, _user_id, first_order_id, _batch_id = fixture()
    with SessionLocal() as db:
        first_order = db.get(Order, first_order_id)
        first_order.source_type = "pxg_naver_readonly_local_v1"
        db.commit()
        sibling = Order(
            store_id=store_id,
            platform="naver",
            external_order_id="t18-order-001",
            external_product_order_id="t18-product-order-sibling",
            product_name="PXG second item",
            quantity=1,
            order_amount=1,
            currency="KRW",
            order_status="PAYED",
            ordered_at=shipping_service.get_utc_now(),
            source_type="pxg_naver_readonly_local_v1",
            raw_data={},
        )
        db.add(sibling)
        db.commit()
        candidates, skipped = shipping_service._build_naver_dispatch_candidates(
            db,
            store_id=store_id,
            platform="naver",
            import_batch_id=None,
            tracking_rows=[{
                "order_reference": "t18-order-001",
                "product_order_reference": "t18-product-order-sibling",
                "carrier": "CJ",
                "tracking_number": "T18-SIBLING-TRACKING",
                "shipped_at": "2026-07-13T10:00:00+09:00",
            }],
        )
        assert not skipped and len(candidates) == 1, (candidates, skipped)
        assert candidates[0]["order"].id == sibling.id and candidates[0]["order"].id != first_order_id, candidates


def test_retired_non_t18_writeback_has_no_local_side_effect() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db:
        grant = warehouse_shipping_service.issue_approval_grant(
            db, batch_id=batch_id, user_id=user_id, grant_scope="writeback",
        )
        approved_hash = warehouse_shipping_service.consume_approval_grant_with_candidate_hash(
            db, batch_id=batch_id, user_id=user_id, grant_scope="writeback", token=grant["approval_token"],
        )
        batch = db.get(WarehouseShippingBatch, batch_id)
        row_status = batch.rows[0].row_status
        audit_before = db.query(OperationAuditLog).count()
        result = warehouse_shipping_service.execute_warehouse_batch_writeback(
            db,
            batch_id=batch_id,
            manual_approval=True,
            final_operator_confirmation=True,
            real_api_call_requested=True,
            actor_context=ACTOR,
            approved_candidate_hash=approved_hash,
        )
        assert result["status"] == "blocked" and result["skip_reason"] == "t18_shipping_pilot_execution_required", result
        db.refresh(batch)
        assert batch.status == "ready_to_writeback" and batch.rows[0].row_status == row_status
        assert db.query(OperationAuditLog).count() == audit_before


def test_safe_batch_capability_and_trial_exception_contract() -> None:
    reset_database()
    store_id, _user_id, _order_id, batch_id = fixture()
    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)):
        listing = warehouse_shipping_service.list_warehouse_batches(
            db, store_id=store_id, platform="naver", include_rows=False,
        )
        item = next(row for row in listing["items"] if row["id"] == batch_id)
        capability = item["writeback_capability"]
        assert capability["candidate_count"] == 1 and capability["status"] == "approval_required", capability
        assert TRACKING_NUMBER not in str(capability), capability

        trial_settings = SimpleNamespace(
            operator_trial_enabled=True,
            operator_trial_real_read_enabled=False,
            real_api_test_enabled=False,
            operator_trial_artificial_data_only=True,
            real_api_write_enabled=True,
            shipping_platform_write_enabled=True,
            pxg_naver_shipping_pilot_enabled=True,
            platform_order_write_enabled=False,
            ai_automatic_operations_enabled=False,
            platform_product_write_enabled=False,
            platform_inventory_write_enabled=False,
            customer_platform_write_enabled=False,
        )
        operator_trial_service.assert_trial_runtime_closed(trial_settings)
        assert "shipping.writeback.approve" in operator_trial_service.TRIAL_PERMISSION_KEYS
        assert "shipping.writeback.approve" not in operator_trial_service.FORBIDDEN_TRIAL_PERMISSION_KEYS
        operator_trial_service.assert_t18_trial_writeback_request_allowed(
            db,
            settings=trial_settings,
            path=f"/api/v1/shipping/warehouse-batches/{batch_id}/writeback",
            body={"action": "execute"},
            store_id=store_id,
        )
        operator_trial_service.assert_t18_trial_writeback_request_allowed(
            db,
            settings=trial_settings,
            path=f"/api/v1/shipping/warehouse-batches/{batch_id}/approval/writeback",
            body={"confirmation": True},
            store_id=store_id,
        )
        trial_settings.platform_order_write_enabled = True
        try:
            operator_trial_service.assert_trial_runtime_closed(trial_settings)
        except Exception as exc:
            assert getattr(exc, "error_code", None) == "trial_real_operation_enabled", exc
        else:
            raise AssertionError("generic platform-order write permission must remain closed")


def test_local_commit_failure_remains_unknown() -> None:
    reset_database()
    _store_id, user_id, order_id, batch_id = fixture()

    def successful_post(*, candidates, **_kwargs):
        return {
            "success": True,
            "http_status": 200,
            "success_product_order_ids": [candidates[0]["product_order_id"]],
            "fail_product_order_infos": [],
            "diagnostics": {"raw_response_saved": False},
        }

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", preflight("t18-product-order-001")), patch.object(
        shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", lambda _context: ("mock", 200),
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: mock_credential()), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(shipping_service, "_post_naver_shipment_dispatch", successful_post), patch.object(
        warehouse_shipping_service, "_write_workflow_audit", side_effect=RuntimeError("forced local audit failure"),
    ):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "unknown", result
        assert result["skip_reason"] == "local_commit_after_platform_success_failed", result
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "unknown"
        assert db.get(Order, order_id).order_status == "DISPATCHED"


def test_public_legacy_execute_route_is_removed() -> None:
    assert "/api/v1/shipping/shipment-writeback/execute" not in app.openapi()["paths"]


def main() -> None:
    test_closed_gates_never_read_or_write()
    test_bottom_level_gate_blocks_token_and_http()
    test_all_eight_gate_combinations_and_proof_requirement()
    test_platform_order_write_flag_remains_closed()
    test_exact_approval_execution_and_privacy()
    test_platform_state_change_invalidates_approval()
    test_capability_contract_and_platform_logistics_guards()
    test_prepost_failures_do_not_consume_attempt()
    test_token_then_expired_claim_never_posts()
    test_wrong_user_expired_token_and_restart_attempts_are_blocked()
    test_developer_actor_is_rejected_before_preflight()
    test_unknown_requires_reconciliation_without_resend()
    test_ambiguous_post_results_are_unknown_and_privacy_safe()
    test_reconcile_works_with_write_gates_closed_and_requires_exact_logistics()
    test_reconciled_not_applied_consumes_the_single_attempt()
    test_multi_row_cross_store_claim_and_concurrent_attempt_guards()
    test_product_order_reference_never_updates_a_sibling_order()
    test_retired_non_t18_writeback_has_no_local_side_effect()
    test_safe_batch_capability_and_trial_exception_contract()
    test_local_commit_failure_remains_unknown()
    test_public_legacy_execute_route_is_removed()
    print("t18 naver shipping pilot verification ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        if DB_PATH.exists():
            try:
                DB_PATH.unlink()
            except PermissionError:
                pass
