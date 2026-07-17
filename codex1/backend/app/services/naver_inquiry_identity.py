from __future__ import annotations

import hashlib


def naver_inquiry_external_id_hash(external_inquiry_id: object) -> str | None:
    normalized = str(external_inquiry_id or "").strip()
    if not normalized:
        return None
    return hashlib.sha256(f"customer-inquiry:{normalized}".encode("utf-8")).hexdigest()
