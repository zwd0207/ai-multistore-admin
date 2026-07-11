import argparse
import base64
import hashlib
import hmac
import struct
import time
from pathlib import Path


CREDENTIALS_PATH = Path(__file__).resolve().parents[1] / ".local-trial" / "operator-credentials.txt"


def current_code(secret: str) -> tuple[str, int]:
    normalized = secret.strip().upper()
    normalized += "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized)
    timestamp = int(time.time())
    counter = timestamp // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 1_000_000).zfill(6), 30 - timestamp % 30


def read_secret() -> str:
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError("请先启动 PXG 本地试运营系统。")
    values = dict(
        line.split("=", 1)
        for line in CREDENTIALS_PATH.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    return values["totp_secret"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    secret = read_secret()
    while True:
        code, remaining = current_code(secret)
        print(f"\r当前六位验证码：{code}    剩余 {remaining:02d} 秒", end="", flush=True)
        if args.once:
            print()
            return
        time.sleep(1)


if __name__ == "__main__":
    main()

