from __future__ import annotations

import hashlib
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.product import Product


THUMBNAIL_MAX_DIMENSION = 256
THUMBNAIL_MAX_BYTES = 150 * 1024
THUMBNAIL_CACHE_MAX_BYTES = 500 * 1024 * 1024
THUMBNAIL_CACHE_MAX_ITEMS = 5000
THUMBNAIL_MAX_SOURCE_BYTES = 5 * 1024 * 1024
THUMBNAIL_MAX_SOURCE_PIXELS = 20_000_000
PXG_READONLY_SOURCE = "pxg_naver_readonly_local_v1"
THUMBNAIL_REF_PATTERN = re.compile(r"^[a-f0-9]{64}\.webp$")


def approved_pstatic_product_image_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 1000:
        return None
    parsed = urlparse(value.strip())
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not hostname
        or not (hostname == "pstatic.net" or hostname.endswith(".pstatic.net"))
    ):
        return None
    return parsed.geturl()


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


def _enforce_cache_limit(root: Path, *, incoming_bytes: int, keep_ref: str | None = None) -> None:
    files = _cache_files(root)
    total_bytes = sum(path.stat().st_size for path in files)
    target_exists = bool(keep_ref and (root / keep_ref).is_file())
    required_bytes = 0 if target_exists else incoming_bytes
    additional_items = 0 if target_exists else 1
    remaining_items = len(files)
    for path in sorted(files, key=lambda item: item.stat().st_mtime):
        if total_bytes + required_bytes <= THUMBNAIL_CACHE_MAX_BYTES and remaining_items + additional_items <= THUMBNAIL_CACHE_MAX_ITEMS:
            break
        if keep_ref and path.name == keep_ref:
            continue
        total_bytes -= path.stat().st_size
        remaining_items -= 1
        path.unlink(missing_ok=True)
    if total_bytes + required_bytes > THUMBNAIL_CACHE_MAX_BYTES or remaining_items + additional_items > THUMBNAIL_CACHE_MAX_ITEMS:
        raise ApiError("local product thumbnail cache is full", "product_thumbnail_cache_full", 409)


def store_thumbnail_from_approved_product_read(
    db: Session,
    *,
    product: Product,
    source_image_url: object,
    image_bytes: bytes,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Persist a derived thumbnail from an approved PXG/Naver product read only."""
    if product.source_type != PXG_READONLY_SOURCE or product.platform != "naver":
        raise ApiError("product thumbnail source is not approved", "product_thumbnail_source_forbidden", 403)
    if not approved_pstatic_product_image_url(source_image_url):
        raise ApiError("product thumbnail image host is not approved", "product_thumbnail_source_forbidden", 403)
    encoded, width, height = _encode_webp(image_bytes)
    ref = f"{hashlib.sha256(encoded).hexdigest()}.webp"
    root = _thumbnail_root(settings or get_settings(), create=True)
    target = _thumbnail_file(root, ref)
    _enforce_cache_limit(root, incoming_bytes=len(encoded), keep_ref=ref)
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
    }
    product.raw_data = raw_data
    db.flush()
    return {"ref": ref, "width": width, "height": height, "bytes": len(encoded)}


def local_thumbnail_url(product: Product) -> str | None:
    raw_data = product.raw_data if isinstance(product.raw_data, dict) else {}
    thumbnail = raw_data.get("thumbnail")
    if not isinstance(thumbnail, dict) or not isinstance(thumbnail.get("ref"), str):
        return None
    if not THUMBNAIL_REF_PATTERN.fullmatch(thumbnail["ref"]):
        return None
    return f"/api/v1/products/{product.id}/thumbnail?store_id={product.store_id}"


def thumbnail_response(*, product: Product, settings: Settings | None = None) -> FileResponse:
    raw_data = product.raw_data if isinstance(product.raw_data, dict) else {}
    thumbnail = raw_data.get("thumbnail")
    if product.source_type != PXG_READONLY_SOURCE or not isinstance(thumbnail, dict):
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
