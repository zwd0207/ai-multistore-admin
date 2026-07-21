from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
from pathlib import Path


CREDENTIALS_PATH = Path(__file__).resolve().parents[1] / ".local-trial" / "config-admin-credentials.txt"


def _values() -> dict[str, str]:
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError("Configuration administrator is not provisioned.")
    return dict(
        line.split("=", 1)
        for line in CREDENTIALS_PATH.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _current_code(secret: str) -> tuple[str, int]:
    normalized = secret.strip().upper()
    normalized += "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized)
    timestamp = int(time.time())
    counter = timestamp // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 1_000_000).zfill(6), 30 - timestamp % 30


def main() -> None:
    values = _values()
    print(f"Account: {values['login_identifier']}")
    print(f"Password: {values['password']}")
    print()
    while True:
        code, remaining = _current_code(values["totp_secret"])
        print(f"\rVerification code: {code}    Valid for {remaining:02d} seconds", end="", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
