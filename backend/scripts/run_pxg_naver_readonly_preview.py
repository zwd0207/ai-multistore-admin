import argparse
import json
import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_secret_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the guarded PXG Naver real-data readonly preview")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    _load_secret_env(args.env_file)
    os.environ.update({
        "APP_ENV": "test",
        "OPERATOR_TRIAL_ENABLED": "true",
        "OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY": "false",
        "OPERATOR_TRIAL_REAL_READ_ENABLED": "true",
        "REAL_API_TEST_ENABLED": "true",
        "REAL_API_WRITE_ENABLED": "false",
        "AI_AUTOMATIC_OPERATIONS_ENABLED": "false",
        "PLATFORM_PRODUCT_WRITE_ENABLED": "false",
        "PLATFORM_INVENTORY_WRITE_ENABLED": "false",
        "PLATFORM_ORDER_WRITE_ENABLED": "false",
        "CUSTOMER_PLATFORM_WRITE_ENABLED": "false",
        "SHIPPING_PLATFORM_WRITE_ENABLED": "false",
    })

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.config import get_settings
    from app.services.pxg_naver_readonly_service import preview_pxg_naver_real_reads

    db_uri = f"sqlite:///file:{args.database.resolve().as_posix()}?mode=ro&uri=true"
    engine = create_engine(db_uri, connect_args={"uri": True}, future=True)
    try:
        with Session(engine) as db:
            result = preview_pxg_naver_real_reads(db, get_settings())
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
