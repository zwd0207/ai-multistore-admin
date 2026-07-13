from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import httpx
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.product import Product
from app.models.store import Store


THUMBNAIL_MAX_DIMENSION = 256
THUMBNAIL_MAX_BYTES = 150 * 1024
THUMBNAIL_CACHE_MAX_BYTES = 500 * 1024 * 1024
THUMBNAIL_CACHE_MAX_ITEMS = 5000
THUMBNAIL_MAX_SOURCE_BYTES = 5 * 1024 * 1024
THUMBNAIL_MAX_SOURCE_PIXELS = 16_000_000
THUMBNAIL_ACCESS_RETENTION = timedelta(days=30)
PXG_READONLY_SOURCE = "pxg_naver_readonly_local_v1"
THUMBNAIL_REF_PATTERN = re.compile(r"^[a-f0-9]{64}\.webp$")
APPROVED_PSTATIC_PRODUCT_IMAGE_HOSTS = frozenset({
    "shop-phinf.pstatic.net",
    "shopping-phinf.pstatic.net",
})
ACTIVE_PRODUCT_STATUSES = frozenset({"active", "sale", "on_sale", "on-sale", "selling"})


def approved_pstatic_product_image_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 1000:
        return None
    parsed = urlparse(value.strip())
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or hostname not in APPROVED_PSTATIC_PRODUCT_IMAGE_HOSTS
    ):
        return None
    return parsed.geturl()


def approved_product_image_source_hash(value: object) -> str | None:
    source_url = approved_pstatic_product_image_url(value)
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest() if source_url else None


def _thumbnail_root(settings: Settings, *, create: bool) -> Path:
    if not settings.local_product_thumbnail_root:
        raise ApiError("local product thumbnail storage is not configured", "product_thumbnail_storage_unavailable", 409)
    root = Path(settings.local_product_thumbnail_root).resolve()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    if not root.exists() or not root.is_dir():
        raise ApiError("local product thumbnail storage is unavailable", "product_thumbnail_storage_unavailable", 409)
    return root


def _thumbnail_file(root: Path, ref: str) -> Path:
    if not THUMBNAIL_REF_PATTERN.fullmatch(ref):
        raise ApiError("product thumbnail reference is invalid", "product_thumbnail_unavailable", 404)
    path = (root / ref).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ApiError("product thumbnail reference is invalid", "product_thumbnail_unavailable", 404) from exc
    return path


def _encode_webp(image_bytes: bytes) -> tuple[bytes, int, int]:
    if not image_bytes or len(image_bytes) > THUMBNAIL_MAX_SOURCE_BYTES:
        raise ApiError("product thumbnail source is too large", "product_thumbnail_source_invalid", 422)
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.width * source.height > THUMBNAIL_MAX_SOURCE_PIXELS:
                raise ApiError("product thumbnail source has too many pixels", "product_thumbnail_source_invalid", 422)
            image = ImageOps.exif_transpose(source)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            if image.mode == "RGBA":
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), Image.Resampling.LANCZOS)
            for quality in range(86, 35, -6):
                output = BytesIO()
                image.save(output, format="WEBP", quality=quality, method=6)
                encoded = output.getvalue()
                if len(encoded) <= THUMBNAIL_MAX_BYTES:
                    return encoded, image.width, image.height
    except UnidentifiedImageError as exc:
        raise ApiError("product thumbnail source is not an image", "product_thumbnail_source_invalid", 422) from exc
    raise ApiError("product thumbnail cannot meet the size limit", "product_thumbnail_size_exceeded", 422)


def _cache_files(root: Path) -> list[Path]:
    return [path for path in root.glob("*.webp") if path.is_file() and THUMBNAIL_REF_PATTERN.fullmatch(path.name)]


def _purge_expired_cache_files(root: Path, *, now: datetime) -> int:
    cutoff = now.timestamp() - THUMBNAIL_ACCESS_RETENTION.total_seconds()
    removed = 0
    for path in _cache_files(root):
        if path.stat().st_mtime <= cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _enforce_cache_limit(
    root: Path,
    *,
    incoming_bytes: int,
    incoming_items: int,
    keep_ref: str | None = None,
) -> list[str]:
    files = _cache_files(root)
    total_bytes = sum(path.stat().st_size for path in files)
    target_exists = bool(keep_ref and (root / keep_ref).is_file())
    required_bytes = 0 if target_exists else incoming_bytes
    additional_items = 0 if target_exists else incoming_items
    remaining_items = len(files)
    removed_refs: list[str] = []
    for path in sorted(files, key=lambda item: item.stat().st_mtime):
        if total_bytes + required_bytes <= THUMBNAIL_CACHE_MAX_BYTES and remaining_items + additional_items <= THUMBNAIL_CACHE_MAX_ITEMS:
            break
        if keep_ref and path.name == keep_ref:
            continue
        total_bytes -= path.stat().st_size
        remaining_items -= 1
        path.unlink(missing_ok=True)
        removed_refs.append(path.name)
    if total_bytes + required_bytes > THUMBNAIL_CACHE_MAX_BYTES or remaining_items + additional_items > THUMBNAIL_CACHE_MAX_ITEMS:
        raise ApiError("local product thumbnail cache is full", "product_thumbnail_cache_full", 409)
    return removed_refs


def _clear_thumbnail_metadata_for_refs(db: Session, refs: Iterable[str]) -> int:
    ref_set = set(refs)
    if not ref_set:
        return 0
    cleared = 0
    for product in db.query(Product).filter(Product.source_type == PXG_READONLY_SOURCE).all():
        thumbnail = _thumbnail_metadata(product)
        if thumbnail and thumbnail.get("ref") in ref_set:
            raw_data = dict(product.raw_data or {})
            raw_data.pop("thumbnail", None)
            product.raw_data = raw_data
            cleared += 1
    if cleared:
        db.flush()
    return cleared


def cleanup_local_product_thumbnail_cache(
    *,
    db: Session | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, int | str]:
    """Remove expired files, then enforce the byte and item cache ceilings."""
    root = _thumbnail_root(settings or get_settings(), create=False)
    current = now or get_utc_now()
    expired_refs = [
        path.name for path in _cache_files(root)
        if path.stat().st_mtime <= current.timestamp() - THUMBNAIL_ACCESS_RETENTION.total_seconds()
    ]
    expired_removed = _purge_expired_cache_files(root, now=current)
    capacity_refs = _enforce_cache_limit(root, incoming_bytes=0, incoming_items=0)
    metadata_cleared = _clear_thumbnail_metadata_for_refs(db, [*expired_refs, *capacity_refs]) if db else 0
    return {
        "status": "completed",
        "expired_removed": expired_removed,
        "capacity_removed": len(capacity_refs),
        "metadata_cleared": metadata_cleared,
    }


def _thumbnail_metadata(product: Product) -> dict[str, Any] | None:
    raw_data = product.raw_data if isinstance(product.raw_data, dict) else {}
    thumbnail = raw_data.get("thumbnail")
    return thumbnail if isinstance(thumbnail, dict) else None


def _product_is_thumbnail_eligible(product: Product) -> bool:
    store = product.store
    return (
        product.source_type == PXG_READONLY_SOURCE
        and product.platform == "naver"
        and str(product.status or "").lower() in ACTIVE_PRODUCT_STATUSES
        and store is not None
        and str(store.status or "").lower() == "active"
    )


def invalidate_product_thumbnail(product: Product, *, settings: Settings | None = None) -> bool:
    """Drop only derivative cache metadata and the corresponding local file."""
    thumbnail = _thumbnail_metadata(product)
    raw_data = dict(product.raw_data or {})
    raw_data.pop("thumbnail", None)
    product.raw_data = raw_data
    ref = thumbnail.get("ref") if thumbnail else None
    if not isinstance(ref, str) or not THUMBNAIL_REF_PATTERN.fullmatch(ref):
        return False
    try:
        path = _thumbnail_file(_thumbnail_root(settings or get_settings(), create=False), ref)
    except ApiError:
        return True
    path.unlink(missing_ok=True)
    return True


def thumbnail_requires_invalidation(product: Product, source_image_url: object) -> bool:
    thumbnail = _thumbnail_metadata(product)
    if thumbnail is None:
        return False
    incoming_source_hash = approved_product_image_source_hash(source_image_url)
    stored_source_hash = thumbnail.get("source_url_hash")
    return (
        not _product_is_thumbnail_eligible(product)
        or not isinstance(stored_source_hash, str)
        or incoming_source_hash != stored_source_hash
    )


def store_thumbnail_from_approved_product_read(
    db: Session,
    *,
    product: Product,
    source_image_url: object,
    image_bytes: bytes,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Persist a derived thumbnail from an approved PXG/Naver product read only."""
    if not _product_is_thumbnail_eligible(product):
        raise ApiError("product thumbnail source is not approved", "product_thumbnail_source_forbidden", 403)
    source_url_hash = approved_product_image_source_hash(source_image_url)
    if not source_url_hash:
        raise ApiError("product thumbnail image host is not approved", "product_thumbnail_source_forbidden", 403)
    encoded, width, height = _encode_webp(image_bytes)
    ref = f"{hashlib.sha256(encoded).hexdigest()}.webp"
    root = _thumbnail_root(settings or get_settings(), create=True)
    target = _thumbnail_file(root, ref)
    current = get_utc_now()
    expired_refs = [
        path.name for path in _cache_files(root)
        if path.stat().st_mtime <= current.timestamp() - THUMBNAIL_ACCESS_RETENTION.total_seconds()
    ]
    _purge_expired_cache_files(root, now=current)
    capacity_refs = _enforce_cache_limit(root, incoming_bytes=len(encoded), incoming_items=1, keep_ref=ref)
    _clear_thumbnail_metadata_for_refs(db, [*expired_refs, *capacity_refs])
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=root, prefix=".thumbnail-", suffix=".tmp", delete=False) as stream:
            stream.write(encoded)
            temporary_path = Path(stream.name)
        try:
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)
    raw_data = dict(product.raw_data or {})
    raw_data.pop("product_image_url", None)
    raw_data["thumbnail"] = {
        "ref": ref,
        "format": "webp",
        "width": width,
        "height": height,
        "bytes": len(encoded),
        "generated_at": get_utc_now().isoformat(),
        "source_url_hash": source_url_hash,
    }
    product.raw_data = raw_data
    db.flush()
    return {"ref": ref, "width": width, "height": height, "bytes": len(encoded)}


def local_thumbnail_url(product: Product) -> str | None:
    thumbnail = _thumbnail_metadata(product)
    if not _product_is_thumbnail_eligible(product):
        if thumbnail:
            invalidate_product_thumbnail(product)
        return None
    if not thumbnail or not isinstance(thumbnail.get("ref"), str):
        return None
    if not THUMBNAIL_REF_PATTERN.fullmatch(thumbnail["ref"]):
        return None
    return f"/api/v1/products/{product.id}/thumbnail?store_id={product.store_id}"


def thumbnail_response(*, product: Product, settings: Settings | None = None) -> FileResponse:
    thumbnail = _thumbnail_metadata(product)
    if not _product_is_thumbnail_eligible(product) or not thumbnail:
        invalidate_product_thumbnail(product, settings=settings)
        raise ApiError("product thumbnail is unavailable", "product_thumbnail_unavailable", 404)
    ref = thumbnail.get("ref")
    if not isinstance(ref, str):
        raise ApiError("product thumbnail is unavailable", "product_thumbnail_unavailable", 404)
    root = _thumbnail_root(settings or get_settings(), create=False)
    path = _thumbnail_file(root, ref)
    if not path.exists() or path.stat().st_size > THUMBNAIL_MAX_BYTES:
        raise ApiError("product thumbnail is unavailable", "product_thumbnail_unavailable", 404)
    os.utime(path, None)
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, no-store"})


def _download_approved_product_image(source_url: str) -> bytes:
    with httpx.stream("GET", source_url, timeout=10.0, follow_redirects=False) as response:
        if response.status_code != 200 or not response.headers.get("content-type", "").lower().startswith("image/"):
            raise ApiError("approved product image could not be read", "product_thumbnail_source_unavailable", 502)
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > THUMBNAIL_MAX_SOURCE_BYTES:
                raise ApiError("approved product image is too large", "product_thumbnail_source_invalid", 422)
            chunks.append(chunk)
    return b"".join(chunks)


def generate_thumbnails_from_approved_product_read(
    db: Session,
    *,
    store_id: int,
    candidates: Iterable[Any],
    settings: Settings | None = None,
    image_fetcher: Callable[[str], bytes] | None = None,
) -> dict[str, int | str]:
    """Generate only during a server-approved product read, never from page access."""
    resolved_settings = settings or get_settings()
    if not resolved_settings.pxg_naver_local_read_thumbnail_generation_enabled:
        return {"status": "disabled", "generated": 0, "skipped": 0}
    store = db.get(Store, store_id)
    if store is None or store.platform != "naver" or str(store.status or "").lower() != "active":
        raise ApiError("thumbnail store is not active", "product_thumbnail_store_forbidden", 403)
    fetch = image_fetcher or _download_approved_product_image
    generated = 0
    skipped = 0
    for candidate in candidates:
        external_product_id = str(getattr(candidate, "external_product_id", "") or "").strip()
        source_url = approved_pstatic_product_image_url(getattr(candidate, "thumbnail_source_url", None))
        if not external_product_id or not source_url:
            skipped += 1
            continue
        product = db.query(Product).filter(
            Product.store_id == store_id,
            Product.platform == "naver",
            Product.external_product_id == external_product_id,
        ).one_or_none()
        if product is None or not _product_is_thumbnail_eligible(product):
            skipped += 1
            continue
        store_thumbnail_from_approved_product_read(
            db,
            product=product,
            source_image_url=source_url,
            image_bytes=fetch(source_url),
            settings=resolved_settings,
        )
        generated += 1
    return {"status": "completed", "generated": generated, "skipped": skipped}
