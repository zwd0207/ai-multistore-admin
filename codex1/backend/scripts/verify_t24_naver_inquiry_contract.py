import os
import sys
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from pydantic import ValidationError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t24-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "REAL_API_TEST_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
    "AUTOMATIC_READ_SYNC_ENABLED": "false",
})

from sqlalchemy import select

from app.config import Settings
from app.core.exceptions import ApiError
from app.database import Base, SessionLocal, engine
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services import (
    api_credential_readiness_service,
    automatic_read_sync_service,
    naver_readonly_inquiry_service,
    sync_service,
)


def page_payload(content, *, page, total_pages, total_elements, number_base=1):
    return {
        "totalPages": total_pages,
        "totalElements": total_elements,
        "first": page == 1,
        "last": total_pages == 0 or page == total_pages,
        "number": page - 1 if number_base == 0 else page,
        "size": 200,
        "numberOfElements": len(content),
        "content": content,
        "empty": not content,
    }


class FakeClient:
    def __init__(self, response, capture):
        self.response = response
        self.capture = capture

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, *, headers, params):
        self.capture.append({"url": url, "headers": headers, "params": params})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeOrderClient(FakeClient):
    def post(self, url, *, headers, json):
        self.capture.append({"url": url, "headers": headers, "json": json})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def verify_http_contract():
    capture = []
    request = httpx.Request("GET", "https://api.test/external/v1/pay-user/inquiries")
    response = httpx.Response(
        200,
        request=request,
        json=page_payload([], page=1, total_pages=0, total_elements=0),
        headers={"GNCP-GW-Trace-ID": "trace-safe-1"},
    )
    original_client = sync_service.httpx.Client
    sync_service.httpx.Client = lambda **_kwargs: FakeClient(response, capture)
    try:
        result = sync_service._request_naver_customer_inquiries(
            api_base="https://api.test/external",
            headers={"Authorization": "Bearer token-must-not-leak"},
            start_date=date(2026, 6, 18),
            end_date=date(2026, 7, 17),
            answered=False,
            page=1,
            size=200,
        )
        assert result["success"] is True and result["payload"]["last"] is True
        assert capture == [{
            "url": "https://api.test/external/v1/pay-user/inquiries",
            "headers": {
                "Authorization": "Bearer token-must-not-leak",
                "Accept": "application/json;charset=UTF-8",
            },
            "params": {
                "page": 1,
                "size": 200,
                "startSearchDate": "2026-06-18",
                "endSearchDate": "2026-07-17",
                "answered": "false",
            },
        }]
        assert "token-must-not-leak" not in str(result)
        for invalid_page in (0, 1_000_001, True):
            try:
                sync_service._request_naver_customer_inquiries(
                    api_base="https://api.test/external", headers={}, start_date=date.today(),
                    end_date=date.today(), answered=None, page=invalid_page, size=200,
                )
            except ApiError as exc:
                assert exc.error_code == "naver_customer_inquiry_page_invalid"
            else:
                raise AssertionError("invalid page must fail locally")
        for invalid_size in (9, 201, True):
            try:
                sync_service._request_naver_customer_inquiries(
                    api_base="https://api.test/external", headers={}, start_date=date.today(),
                    end_date=date.today(), answered=None, page=1, size=invalid_size,
                )
            except ApiError as exc:
                assert exc.error_code == "naver_customer_inquiry_size_invalid"
            else:
                raise AssertionError("invalid size must fail locally")
    finally:
        sync_service.httpx.Client = original_client


def verify_safe_errors_and_limits():
    original_client = sync_service.httpx.Client
    capture = []
    request = httpx.Request("GET", "https://api.test/external/v1/pay-user/inquiries")
    bad_request = httpx.Response(
        400,
        request=request,
        json={
            "code": "INVALID_PARAMETER",
            "message": "Customer Kim orderId=12345678901234567890 secret-body",
            "invalidParams": [{"field": "startSearchDate", "value": "private"}],
        },
        headers={"GNCP-GW-Trace-ID": "trace-400"},
    )
    sync_service.httpx.Client = lambda **_kwargs: FakeClient(bad_request, capture)
    try:
        result = sync_service._request_naver_customer_inquiries(
            api_base="https://api.test/external", headers={"Authorization": "Bearer hidden"},
            start_date=date(2026, 6, 18), end_date=date(2026, 7, 17),
            answered=None, page=1, size=200,
        )
        assert result["error_code"] == "naver_customer_inquiry_request_invalid"
        assert result["retryable"] is False and result["safe_error"] == {
            "platform_error_code": "INVALID_PARAMETER",
            "platform_error_fields": ["startSearchDate"],
            "trace_id": "trace-400",
            "rate_limit": {},
            "retry_after_seconds": None,
        }
        serialized = str(result)
        assert all(value not in serialized for value in ("Customer Kim", "secret-body", "12345678901234567890", "Bearer hidden"))

        limited = httpx.Response(
            429,
            request=request,
            json={"code": "GW.RATE_LIMIT", "message": "do not persist this message"},
            headers={
                "GNCP-GW-Trace-ID": "trace-429",
                "GNCP-GW-RateLimit-Limit": "10",
                "GNCP-GW-Quota-Remaining": "0",
                "Retry-After": "99999",
            },
        )
        sync_service.httpx.Client = lambda **_kwargs: FakeClient(limited, capture)
        result = sync_service._request_naver_customer_inquiries(
            api_base="https://api.test/external", headers={}, start_date=date.today(),
            end_date=date.today(), answered=None, page=1, size=200,
        )
        assert result["error_code"] == "naver_customer_inquiry_rate_limit" and result["retryable"] is True
        assert result["safe_error"]["retry_after_seconds"] == 3600
        assert sync_service._parse_bounded_retry_after("9" * 100_000) == 3600
        assert sync_service._parse_bounded_retry_after("0" * 100_000) == 0
        assert sync_service._parse_bounded_retry_after("not-a-date") is None
        assert result["safe_error"]["rate_limit"] == {
            "gncp-gw-ratelimit-limit": "10",
            "gncp-gw-quota-remaining": "0",
        }
        assert "do not persist this message" not in str(result)

        timeout = httpx.ReadTimeout("timeout", request=request)
        sync_service.httpx.Client = lambda **_kwargs: FakeClient(timeout, capture)
        result = sync_service._request_naver_customer_inquiries(
            api_base="https://api.test/external", headers={}, start_date=date.today(),
            end_date=date.today(), answered=None, page=1, size=200,
        )
        assert result["error_code"] == "naver_customer_inquiry_network_timeout" and result["retryable"] is True

        network_error = httpx.ConnectError("network", request=request)
        sync_service.httpx.Client = lambda **_kwargs: FakeClient(network_error, capture)
        result = sync_service._request_naver_customer_inquiries(
            api_base="https://api.test/external", headers={}, start_date=date.today(),
            end_date=date.today(), answered=None, page=1, size=200,
        )
        assert result["error_code"] == "naver_customer_inquiry_network_retryable"
        assert automatic_read_sync_service._retryable_error(result["error_code"])
        assert automatic_read_sync_service._retryable_error("naver_customer_inquiry_rate_limit")
    finally:
        sync_service.httpx.Client = original_client


def verify_order_safe_errors_and_limits():
    original_client = sync_service.httpx.Client
    capture = []
    feed_request = httpx.Request(
        "GET",
        "https://api.test/external/v1/pay-order/seller/product-orders/last-changed-statuses",
    )
    start_kst = datetime(2026, 7, 16, tzinfo=timezone.utc)
    end_kst = start_kst + timedelta(days=1)
    try:
        invalid = httpx.Response(
            400,
            request=feed_request,
            json={
                "code": "INVALID_PARAMETER",
                "message": "orderId=12345678901234567890 must remain masked",
                "invalidParams": [{"field": "lastChangedFrom", "value": "private"}],
            },
            headers={"GNCP-GW-Trace-ID": "trace-order-400"},
        )
        sync_service.httpx.Client = lambda **_kwargs: FakeOrderClient(invalid, capture)
        result = sync_service._request_naver_order_last_changed_feed(
            api_base="https://api.test/external",
            headers={"Authorization": "Bearer order-token-must-not-leak"},
            start_kst=start_kst,
            end_kst=end_kst,
            size=20,
            attempt="safe-contract",
            include_last_changed_to=True,
            datetime_format_shape="offset_milliseconds",
        )
        assert result["error_code"] == "readonly_request_failed"
        assert result["http_status"] == 400 and result["retry_after_seconds"] is None
        assert result["diagnostics"]["naver_error_fields"] == ["lastChangedFrom"]
        serialized = str(result)
        assert "order-token-must-not-leak" not in serialized
        assert "12345678901234567890" not in serialized

        limited = httpx.Response(
            429,
            request=feed_request,
            json={"code": "GW.RATE_LIMIT", "message": "rate limit"},
            headers={
                "GNCP-GW-Trace-ID": "trace-order-429",
                "GNCP-GW-RateLimit-Limit": "20",
                "GNCP-GW-Quota-Remaining": "0",
                "Retry-After": "99999",
            },
        )
        sync_service.httpx.Client = lambda **_kwargs: FakeOrderClient(limited, capture)
        result = sync_service._request_naver_order_last_changed_feed(
            api_base="https://api.test/external",
            headers={},
            start_kst=start_kst,
            end_kst=end_kst,
            size=20,
            attempt="safe-contract",
            include_last_changed_to=True,
            datetime_format_shape="offset_milliseconds",
        )
        assert result["error_code"] == "readonly_request_failed"
        assert result["retry_after_seconds"] == 3600
        assert result["diagnostics"]["rate_limit"] == {
            "gncp-gw-ratelimit-limit": "20",
            "gncp-gw-quota-remaining": "0",
        }

        detail_request = httpx.Request(
            "POST",
            "https://api.test/external/v1/pay-order/seller/product-orders/query",
        )
        upstream = httpx.Response(
            503,
            request=detail_request,
            json={"code": "UPSTREAM", "message": "temporarily unavailable"},
            headers={"Retry-After": "120"},
        )
        sync_service.httpx.Client = lambda **_kwargs: FakeOrderClient(upstream, capture)
        result = sync_service._request_naver_order_detail_query(
            api_base="https://api.test/external",
            headers={"Authorization": "Bearer detail-token-must-not-leak"},
            product_order_ids=["synthetic-product-order"],
        )
        assert result["error_code"] == "readonly_request_failed"
        assert result["retry_after_seconds"] == 120
        assert "detail-token-must-not-leak" not in str(result)
        assert "synthetic-product-order" not in str(result)
    finally:
        sync_service.httpx.Client = original_client


def verify_kst_window_and_pagination():
    start_date, end_date = naver_readonly_inquiry_service._recent_naver_inquiry_date_range(
        business_date=date(2026, 7, 17),
    )
    assert start_date == date(2026, 6, 18) and end_date == date(2026, 7, 17)
    calls = []
    sleeps = []
    original_request = sync_service._request_naver_customer_inquiries

    def request_page(**kwargs):
        calls.append(kwargs)
        if kwargs["page"] == 1:
            content = [{"inquiryNo": f"first-{index}"} for index in range(200)]
            return {"success": True, "payload": page_payload(content, page=1, total_pages=2, total_elements=201, number_base=0)}
        content = [{"inquiryNo": "last"}]
        return {"success": True, "payload": page_payload(content, page=2, total_pages=2, total_elements=201, number_base=0)}

    sync_service._request_naver_customer_inquiries = request_page
    try:
        result = naver_readonly_inquiry_service._fetch_naver_inquiry_pages(
            api_base="https://api.test/external",
            token="token-never-returned",
            start_date=start_date,
            end_date=end_date,
            sleep_fn=sleeps.append,
        )
        assert result["pages_read"] == 2 and result["total_elements"] == 201 and len(result["items"]) == 201
        assert sleeps == [1.0]
        assert [call["page"] for call in calls] == [1, 2]
        assert all(call["size"] == 200 for call in calls)

        repeated = [{"inquiryNo": f"repeat-{index}"} for index in range(200)]
        sync_service._request_naver_customer_inquiries = lambda **kwargs: {
            "success": True,
            "payload": page_payload(repeated, page=kwargs["page"], total_pages=2, total_elements=400),
        }
        try:
            naver_readonly_inquiry_service._fetch_naver_inquiry_pages(
                api_base="https://api.test/external", token="hidden",
                start_date=start_date, end_date=end_date, sleep_fn=lambda _seconds: None,
            )
        except ApiError as exc:
            assert exc.error_code == "naver_inquiry_duplicate_page"
        else:
            raise AssertionError("duplicate page must fail closed")

        contradictory = page_payload([], page=1, total_pages=2, total_elements=400)
        try:
            naver_readonly_inquiry_service._validate_inquiry_page(
                contradictory, requested_page=1, requested_size=200,
                expected_total_pages=None, expected_total_elements=None, response_number_base=None,
            )
        except ApiError as exc:
            assert exc.error_code == "naver_inquiry_pagination_metadata_conflict"
        else:
            raise AssertionError("empty non-final page must fail closed")

        too_many = page_payload([{"inquiryNo": "one"}], page=1, total_pages=1001, total_elements=200001)
        try:
            naver_readonly_inquiry_service._validate_inquiry_page(
                too_many, requested_page=1, requested_size=200,
                expected_total_pages=None, expected_total_elements=None, response_number_base=None,
            )
        except ApiError as exc:
            assert exc.error_code == "naver_inquiry_page_limit_reached"
        else:
            raise AssertionError("local page ceiling must fail closed")

        call_count = 0

        def limited_page(**_kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "success": False,
                "http_status": 429,
                "error_code": "naver_customer_inquiry_rate_limit",
                "retryable": True,
                "safe_error": {"trace_id": "trace-safe", "retry_after_seconds": 60},
            }

        sync_service._request_naver_customer_inquiries = limited_page
        try:
            naver_readonly_inquiry_service._fetch_naver_inquiry_pages(
                api_base="https://api.test/external", token="hidden",
                start_date=start_date, end_date=end_date, sleep_fn=lambda _seconds: None,
            )
        except ApiError as exc:
            assert exc.error_code == "naver_customer_inquiry_rate_limit" and exc.status_code == 503
            assert exc.detail == {"platform_http_status": 429, "trace_id": "trace-safe", "retry_after_seconds": 60}
        else:
            raise AssertionError("429 must leave the run immediately")
        assert call_count == 1
    finally:
        sync_service._request_naver_customer_inquiries = original_request


def verify_shared_lease_and_safe_log():
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 17, 1, 0, tzinfo=timezone.utc)
    settings = Settings(automatic_read_sync_enabled=False)
    with SessionLocal() as db:
        store = Store(name="T24 Lease", platform="naver", status="active")
        ephemeral_store = Store(name="T24 Ephemeral", platform="naver", status="active")
        db.add_all([store, ephemeral_store])
        db.flush()
        checkpoint = SyncCheckpoint(
            store_id=store.id,
            platform="naver",
            sync_type="naver_automatic_inquiries",
            automatic_read_enabled=True,
            status="running",
            lease_token="automatic-token",
            lease_expires_at=now + timedelta(minutes=10),
        )
        db.add(checkpoint)
        db.commit()
        inherited = naver_readonly_inquiry_service._acquire_inquiry_lease(
            db, store_id=store.id, actor_id="automatic-read", settings=settings, now=now,
        )
        assert inherited["owned"] is False and inherited["token"] == "automatic-token"
        try:
            naver_readonly_inquiry_service._acquire_inquiry_lease(
                db, store_id=store.id, actor_id="manual-user", settings=settings, now=now,
            )
        except ApiError as exc:
            assert exc.error_code == "naver_inquiry_sync_in_progress"
        else:
            raise AssertionError("manual refresh must not overlap the automatic lease")

        checkpoint.lease_expires_at = now - timedelta(seconds=1)
        db.commit()
        manual = naver_readonly_inquiry_service._acquire_inquiry_lease(
            db, store_id=store.id, actor_id="manual-user", settings=settings, now=now,
        )
        heartbeat_at = now + timedelta(minutes=9)
        for _ in range(1000):
            naver_readonly_inquiry_service._renew_inquiry_lease(
                db,
                lease=manual,
                now=heartbeat_at,
            )
            heartbeat_at += timedelta(minutes=9)
        db.refresh(checkpoint)
        assert checkpoint.lease_expires_at.replace(tzinfo=timezone.utc) > heartbeat_at
        with SessionLocal() as second_db:
            try:
                naver_readonly_inquiry_service._acquire_inquiry_lease(
                    second_db, store_id=store.id, actor_id="other-user", settings=settings, now=now,
                )
            except ApiError as exc:
                assert exc.error_code == "naver_inquiry_sync_in_progress"
            else:
                raise AssertionError("one store/resource may hold only one lease")
        naver_readonly_inquiry_service._release_inquiry_lease(db, manual)
        db.refresh(checkpoint)
        assert checkpoint.lease_token is None and checkpoint.lease_expires_at is None

        ephemeral = naver_readonly_inquiry_service._acquire_inquiry_lease(
            db, store_id=ephemeral_store.id, actor_id="manual-user", settings=settings, now=now,
        )
        ephemeral_id = ephemeral["checkpoint_id"]
        naver_readonly_inquiry_service._release_inquiry_lease(db, ephemeral)
        assert db.get(SyncCheckpoint, ephemeral_id) is None

        sensitive = "private inquiry body customer-id-123 order-999 token-secret"
        exc = ApiError(
            "safe message",
            "naver_customer_inquiry_request_invalid",
            502,
            detail={
                "platform_http_status": 400,
                "platform_error_code": "INVALID_PARAMETER",
                "platform_error_fields": ["startSearchDate"],
                "trace_id": "trace-safe",
                "unsafe": sensitive,
            },
        )
        naver_readonly_inquiry_service._record_refresh_failure(db, store_id=store.id, exc=exc)
        log = db.scalar(select(SyncLog).where(SyncLog.store_id == store.id).order_by(SyncLog.id.desc()))
        assert log and sensitive not in str(log.raw_summary) and sensitive not in str(log.error_detail)
        assert log.raw_summary["trace_id"] == "trace-safe"


def verify_server_side_approval_gate():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        store = Store(name="T24 Approval Gate", platform="naver", status="active")
        db.add(store)
        db.commit()
        store_id = store.id

        original_credential = sync_service._ensure_naver_product_preview_credential
        credential_called = False

        def forbidden_credential(*_args, **_kwargs):
            nonlocal credential_called
            credential_called = True
            raise AssertionError("credential lookup must remain unreachable")

        sync_service._ensure_naver_product_preview_credential = forbidden_credential
        try:
            for settings, expected_code in (
                (Settings(), "naver_inquiry_real_read_disabled"),
                (
                    Settings(
                        naver_readonly_inquiry_real_read_enabled=True,
                        naver_readonly_inquiry_approved_store_id=store_id + 1,
                    ),
                    "naver_inquiry_store_not_approved",
                ),
            ):
                try:
                    naver_readonly_inquiry_service.refresh_naver_readonly_inquiries(
                        db,
                        store_id=store_id,
                        actor_id="gate-test",
                        settings=settings,
                    )
                except ApiError as exc:
                    assert exc.error_code == expected_code
                else:
                    raise AssertionError("unapproved inquiry read must fail closed")
                assert db.scalar(select(SyncCheckpoint).where(
                    SyncCheckpoint.store_id == store_id,
                )) is None
                assert db.scalar(select(SyncLog).where(SyncLog.store_id == store_id)) is None
            assert credential_called is False
        finally:
            sync_service._ensure_naver_product_preview_credential = original_credential


def verify_invalid_environment_fails_closed():
    try:
        Settings(app_env="prodction")
    except ValidationError:
        pass
    else:
        raise AssertionError("unknown APP_ENV must fail settings validation")

    try:
        Settings(naver_readonly_inquiry_real_read_enabled=True)
    except ValidationError:
        pass
    else:
        raise AssertionError("real inquiry reads require one approved store id")


def verify_capability_and_write_boundary():
    capability = api_credential_readiness_service.NAVER_CAPABILITY_MAP["naver.customer_inquiry_read"]
    assert capability["docs_reference_version"] == "current/2.82.0"
    assert capability["implemented_now"] is True
    assert capability["safe_to_real_test"] is True
    assert capability["required_permission"] == "order_seller"
    assert capability["grant_confirmed"] is True
    assert capability["token_type_required"] == "SELF"
    assert capability["blocked_reason"] is None
    source = Path(naver_readonly_inquiry_service.__file__).read_text(encoding="utf-8")
    assert "reply_naver_customer_inquiry" not in source
    assert "platform_write\": False" in source


def main():
    try:
        verify_http_contract()
        verify_safe_errors_and_limits()
        verify_order_safe_errors_and_limits()
        verify_kst_window_and_pagination()
        verify_shared_lease_and_safe_log()
        verify_server_side_approval_gate()
        verify_invalid_environment_fails_closed()
        verify_capability_and_write_boundary()
        print("verify_t24_naver_inquiry_contract: ok")
    finally:
        engine.dispose()
        DB_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
