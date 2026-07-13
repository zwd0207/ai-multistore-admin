import os
import sys
import tempfile
import uuid
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
from app.services.operator_trial_service import TRIAL_STORE_NAME  # noqa: E402


ACTOR = {"role": "operator", "actor_id": "t18-operator"}
TRACKING_NUMBER = "T18-TRACKING-998877"


def settings(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        real_api_write_enabled=enabled,
        shipping_platform_write_enabled=enabled,
        pxg_naver_shipping_pilot_enabled=enabled,
        pxg_naver_shipping_pilot_max_rows=1,
        pxg_naver_shipping_pilot_max_attempts=1,
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


def preflight(product_order_id: str, *, status: str = "PAYED", claim: str = ""):
    def _read(*_args, **_kwargs):
        return {
            "credential_id": 1,
            "credential_binding": "mock-credential-binding",
            "platform_checked_at": shipping_service.get_utc_now(),
            "states": [{
                "product_order_id": product_order_id,
                "order_status": status,
                "claim_status": claim,
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
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: SimpleNamespace(id=1)), patch.object(
        shipping_service, "_build_naver_shipping_token_context", lambda _credential: {"api_base": "https://mock.invalid"},
    ), patch.object(shipping_service, "_post_naver_shipment_dispatch", post_dispatch):
        approval = approve(db, batch_id=batch_id, user_id=user_id)
        assert approval["status"] == "approval_granted", approval
        assert approval["writeback_capability"]["candidate_count"] == 1, approval
        result = execute(db, batch_id=batch_id, user_id=user_id, token=approval["approval_token"])
        assert result["status"] == "success", result
        assert result["real_api_called"] is True, result
        assert result["writeback_capability"]["status"] == "completed", result
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
        assert result["status"] == "failed", result
        assert result["skip_reason"] == "shipping_approval_candidate_changed", result
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "failed"
    assert post_calls["count"] == 0, post_calls


def test_unknown_requires_reconciliation_without_resend() -> None:
    reset_database()
    _store_id, user_id, _order_id, batch_id = fixture()
    post_calls = {"count": 0}
    state = {"value": "PAYED"}

    def current_preflight(*args, **kwargs):
        return preflight("t18-product-order-001", status=state["value"])(*args, **kwargs)

    def timeout_post(**_kwargs):
        post_calls["count"] += 1
        raise TimeoutError("mock timeout only")

    with SessionLocal() as db, patch.object(warehouse_shipping_service, "get_settings", lambda: settings(enabled=True)), patch.object(
        shipping_service, "get_settings", lambda: settings(enabled=True),
    ), patch.object(warehouse_shipping_service, "_t18_platform_preflight", current_preflight), patch.object(
        shipping_service.api_credential_readiness_service, "_request_naver_token_from_context", lambda _context: ("mock", 200),
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: SimpleNamespace(id=1)), patch.object(
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
        assert reconciled["status"] == "reconciled", reconciled
        assert db.query(WarehouseShippingApprovalGrant).one().attempt_status == "reconciled"
    assert post_calls["count"] == 1, post_calls


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
    ), patch.object(shipping_service, "_ensure_naver_shipping_credential", lambda *_args, **_kwargs: SimpleNamespace(id=1)), patch.object(
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
    test_exact_approval_execution_and_privacy()
    test_platform_state_change_invalidates_approval()
    test_unknown_requires_reconciliation_without_resend()
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
