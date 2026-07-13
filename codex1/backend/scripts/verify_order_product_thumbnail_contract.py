import os
import sys
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from cryptography.fernet import Fernet
from PIL import Image


TEMP_DIR = Path(tempfile.mkdtemp(prefix="verify-order-product-thumbnail-"))
TEMP_DB = TEMP_DIR / "thumbnail-contract.db"
THUMBNAIL_ROOT = TEMP_DIR / "thumbnails"

os.environ["APP_ENV"] = "test"
os.environ["ALLOW_DEV_AUTH"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["SESSION_TOKEN_PEPPER"] = "test-only-session-pepper-32-characters-minimum"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
os.environ["CORS_ALLOWED_ORIGINS"] = '["https://erp.test"]'
os.environ["LOCAL_PRODUCT_THUMBNAIL_ROOT"] = str(THUMBNAIL_ROOT)

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.core.timezone import get_utc_now
from app.config import Settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.order import Order
from app.models.product import Product
from app.models.store import Store
from app.services.encryption import encrypt_value
from app.services.order_service import product_display_contract, serialize_order_summary
import app.services.product_thumbnail_service as thumbnail_service
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyProductCandidate
from app.services.product_thumbnail_service import (
    THUMBNAIL_ACCESS_RETENTION,
    THUMBNAIL_MAX_BYTES,
    THUMBNAIL_MAX_DIMENSION,
    THUMBNAIL_MAX_SOURCE_PIXELS,
    approved_pstatic_product_image_url,
    cleanup_local_product_thumbnail_cache,
    generate_thumbnails_from_approved_product_read,
    local_thumbnail_url,
    store_thumbnail_from_approved_product_read,
    thumbnail_requires_invalidation,
)
from app.services.session_service import generate_totp, hash_login_identifier, hash_password
from app.services.sync_service import _build_naver_order_internal_detail


ORIGIN = "https://erp.test"
PASSWORD = "UI-01A-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
def create_source_image(color: tuple[int, int, int] = (32, 96, 160)) -> bytes:
    image = Image.new("RGB", (640, 320), color=color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def seed() -> tuple[int, int]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        store = Store(name="pxg球包店", platform="naver", status="active")
        other_store = Store(name="Other Thumbnail Store", platform="naver", status="active")
        user = ErpUser(
            user_key_hash="thumbnail-contract-user",
            display_name="Thumbnail Reader",
            login_identifier_hash=hash_login_identifier("thumbnail@example.test"),
            login_identifier_masked="t***@example.test",
            status="active",
            auth_provider="password",
        )
        role = ErpRole(role_key="thumbnail_reader", role_label_zh="test", role_label_en="test", status="active")
        permission = ErpPermission(permission_key="products.read", permission_group="products", permission_label_zh="test")
        db.add_all([store, other_store, user, role, permission])
        db.flush()
        db.add(ErpUserSecurity(
            user_id=user.id,
            password_hash=hash_password(PASSWORD),
            mfa_type="totp",
            mfa_secret_encrypted=encrypt_value(TOTP_SECRET),
            mfa_enabled_at=get_utc_now(),
            password_changed_at=get_utc_now(),
        ))
        db.add(ErpRolePermission(role_id=role.id, permission_id=permission.id))
        db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id, membership_status="active"))
        product = Product(
            store_id=store.id,
            platform="naver",
            external_product_id="10001",
            name="PXG Test Bag",
            status="active",
            price=0,
            currency="KRW",
            stock_quantity=1,
            source_type="pxg_naver_readonly_local_v1",
            raw_data={
                "readonly_local": True,
            },
        )
        same_name_other_id = Product(
            store_id=store.id,
            platform="naver",
            external_product_id="10002",
            name="PXG Test Bag",
            status="active",
            price=0,
            currency="KRW",
            stock_quantity=1,
            source_type="pxg_naver_readonly_local_v1",
            raw_data={"readonly_local": True},
        )
        legacy_product = Product(
            store_id=store.id,
            platform="naver",
            external_product_id="99999",
            name="Legacy Product",
            status="active",
            price=0,
            currency="KRW",
            stock_quantity=1,
            source_type="legacy",
            raw_data={"readonly_local": False},
        )
        db.add_all([product, same_name_other_id, legacy_product])
        db.flush()
        details = store_thumbnail_from_approved_product_read(
            db,
            product=product,
            source_image_url="https://shopping-phinf.pstatic.net/main/10001.jpg",
            image_bytes=create_source_image(),
        )
        assert details["width"] <= THUMBNAIL_MAX_DIMENSION
        assert details["height"] <= THUMBNAIL_MAX_DIMENSION
        assert details["bytes"] <= THUMBNAIL_MAX_BYTES
        assert "pstatic.net" not in str(product.raw_data)
        assert "source_content" not in str(product.raw_data)

        rejected = False
        try:
            store_thumbnail_from_approved_product_read(
                db,
                product=legacy_product,
                source_image_url="https://shopping-phinf.pstatic.net/main/99999.jpg",
                image_bytes=create_source_image(),
            )
        except Exception as exc:
            rejected = getattr(exc, "error_code", None) == "product_thumbnail_source_forbidden"
        assert rejected
        assert approved_pstatic_product_image_url("https://evilpstatic.net/image.webp") is None
        assert approved_pstatic_product_image_url("https://pstatic.net/image.webp") is None
        assert approved_pstatic_product_image_url("https://other.pstatic.net/image.webp") is None
        assert approved_pstatic_product_image_url("https://shop-phinf.pstatic.net/image.webp")
        assert approved_pstatic_product_image_url("http://shopping-phinf.pstatic.net/image.webp") is None
        assert THUMBNAIL_MAX_SOURCE_PIXELS == 16_000_000
        rejected_host = False
        try:
            store_thumbnail_from_approved_product_read(
                db,
                product=product,
                source_image_url="https://evilpstatic.net/image.webp",
                image_bytes=create_source_image(),
            )
        except Exception as exc:
            rejected_host = getattr(exc, "error_code", None) == "product_thumbnail_source_forbidden"
        assert rejected_host

        canonical_detail = _build_naver_order_internal_detail({
            "orderId": "order-canonical",
            "productOrderId": "product-order-canonical",
            "productId": "origin-product-id",
            "channelProductNo": "10001",
        })
        assert canonical_detail["platform_product_id"] == "10001"
        no_canonical_detail = _build_naver_order_internal_detail({
            "orderId": "order-no-canonical",
            "productOrderId": "product-order-no-canonical",
            "productId": "origin-product-id",
        })
        assert no_canonical_detail["platform_product_id"] is None

        order = Order(
            store_id=store.id,
            platform="naver",
            external_order_id="order-10001",
            external_product_order_id="product-order-10001",
            product_name="PXG Test Bag",
            quantity=1,
            order_amount=Decimal("0"),
            currency="KRW",
            order_status="paid",
            ordered_at=get_utc_now(),
            source_type="pxg_naver_readonly_local_v1",
            raw_data={
                "platform_product_id": "10001",
                "option_name": "Black",
            },
        )
        unmatched_same_name_order = Order(
            store_id=store.id,
            platform="naver",
            external_order_id="order-unknown",
            external_product_order_id="product-order-unknown",
            product_name="PXG Test Bag",
            quantity=1,
            order_amount=Decimal("0"),
            currency="KRW",
            order_status="paid",
            ordered_at=get_utc_now(),
            source_type="pxg_naver_readonly_local_v1",
            raw_data={"platform_product_id": "77777", "option_name": "Black"},
        )
        db.add_all([order, unmatched_same_name_order])
        db.flush()
        contract = product_display_contract(db, order)
        assert contract == {
            "platform_product_id": "10001",
            "option_name": "Black",
            "product_image_url": f"/api/v1/products/{product.id}/thumbnail?store_id={store.id}",
            "product_url": "https://smartstore.naver.com/trendwaymn/products/10001",
        }
        assert product_display_contract(db, unmatched_same_name_order)["product_image_url"] is None
        assert product_display_contract(db, unmatched_same_name_order)["product_url"] is None
        summary = serialize_order_summary(order, db=db)
        assert "raw_data" not in summary

        # Source changes invalidate the old local file before a replacement can be generated.
        old_ref = product.raw_data["thumbnail"]["ref"]
        assert thumbnail_requires_invalidation(product, "https://shop-phinf.pstatic.net/main/changed.jpg")

        # A 30-day unaccessed file is removed and its product metadata is cleared.
        old_path = THUMBNAIL_ROOT / old_ref
        os.utime(old_path, (old_path.stat().st_atime, old_path.stat().st_mtime - THUMBNAIL_ACCESS_RETENTION.total_seconds() - 1))
        cleanup = cleanup_local_product_thumbnail_cache(db=db, settings=Settings(local_product_thumbnail_root=str(THUMBNAIL_ROOT)))
        assert cleanup["expired_removed"] == 1 and cleanup["metadata_cleared"] == 1, cleanup
        assert not old_path.exists() and local_thumbnail_url(product) is None

        # Capacity eviction removes the least-recent thumbnail and clears its stale URL contract.
        store_thumbnail_from_approved_product_read(
            db,
            product=product,
            source_image_url="https://shopping-phinf.pstatic.net/main/10001.jpg",
            image_bytes=create_source_image((32, 96, 160)),
        )
        original_item_limit = thumbnail_service.THUMBNAIL_CACHE_MAX_ITEMS
        thumbnail_service.THUMBNAIL_CACHE_MAX_ITEMS = 1
        try:
            store_thumbnail_from_approved_product_read(
                db,
                product=same_name_other_id,
                source_image_url="https://shop-phinf.pstatic.net/main/10002.jpg",
                image_bytes=create_source_image((160, 96, 32)),
            )
        finally:
            thumbnail_service.THUMBNAIL_CACHE_MAX_ITEMS = original_item_limit
        assert local_thumbnail_url(product) is None
        assert local_thumbnail_url(same_name_other_id) is not None

        approved_candidate = PxgNaverReadonlyProductCandidate(
            external_product_id="10001",
            name="PXG Test Bag",
            status="active",
            thumbnail_source_url="https://shopping-phinf.pstatic.net/main/10001-new.jpg",
            source_updated_at=get_utc_now(),
        )
        disabled_fetches: list[str] = []
        disabled = generate_thumbnails_from_approved_product_read(
            db,
            store_id=store.id,
            candidates=[approved_candidate],
            settings=Settings(local_product_thumbnail_root=str(THUMBNAIL_ROOT)),
            image_fetcher=lambda url: disabled_fetches.append(url) or create_source_image(),
        )
        assert disabled == {"status": "disabled", "generated": 0, "skipped": 0}
        assert not disabled_fetches
        approved_fetches: list[str] = []
        enabled = generate_thumbnails_from_approved_product_read(
            db,
            store_id=store.id,
            candidates=[approved_candidate],
            settings=Settings(
                local_product_thumbnail_root=str(THUMBNAIL_ROOT),
                pxg_naver_local_read_thumbnail_generation_enabled=True,
            ),
            image_fetcher=lambda url: approved_fetches.append(url) or create_source_image((20, 80, 180)),
        )
        assert enabled == {"status": "completed", "generated": 1, "skipped": 0}
        assert approved_fetches == ["https://shopping-phinf.pstatic.net/main/10001-new.jpg"]

        # Invalid products and unbound stores invalidate a previously generated file.
        product.status = "inactive"
        assert local_thumbnail_url(product) is None
        product.status = "active"
        store_thumbnail_from_approved_product_read(
            db,
            product=product,
            source_image_url="https://shopping-phinf.pstatic.net/main/10001-new.jpg",
            image_bytes=create_source_image((20, 80, 180)),
        )
        store.status = "inactive"
        assert local_thumbnail_url(product) is None
        store.status = "active"
        store_thumbnail_from_approved_product_read(
            db,
            product=product,
            source_image_url="https://shopping-phinf.pstatic.net/main/10001-new.jpg",
            image_bytes=create_source_image((20, 80, 180)),
        )
        db.commit()
        product_id = product.id
        store_id = store.id
    return product_id, store_id


def authenticate(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_identifier": "thumbnail@example.test", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/v1/auth/mfa/verify",
        headers={"Origin": ORIGIN},
        json={"code": generate_totp(TOTP_SECRET)},
    )
    assert response.status_code == 200, response.text


def main() -> None:
    product_id, store_id = seed()
    with TestClient(app, base_url=ORIGIN) as client:
        authenticate(client)
        response = client.get(f"/api/v1/products/{product_id}/thumbnail", params={"store_id": store_id})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("image/webp"), response.headers
        assert response.content.startswith(b"RIFF") and b"WEBP" in response.content[:16], response.content[:16]
        cross_store = client.get(f"/api/v1/products/{product_id}/thumbnail", params={"store_id": store_id + 1})
        assert cross_store.status_code == 403, cross_store.text

    engine.dispose()
    print("verify_order_product_thumbnail_contract: ok")


if __name__ == "__main__":
    main()
