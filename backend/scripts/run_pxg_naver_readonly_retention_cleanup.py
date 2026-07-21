"""Daily PXG/Naver readonly retention entrypoint.

The default invocation is a no-write preview. A formal cleanup requires both
the configured local cleanup switch and an explicit `--confirm` supplied by an
authorised operator. This script never enables persistence or contacts Naver.
"""

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import SessionLocal
from app.services.pxg_naver_readonly_persistence_service import run_pxg_naver_readonly_retention_cleanup


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PXG/Naver readonly retention lifecycle")
    parser.add_argument("--confirm", action="store_true", help="Perform the confirmed local cleanup")
    parser.add_argument("--actor-id", default=None, help="Opaque authorised operator identifier")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = run_pxg_naver_readonly_retention_cleanup(
            db,
            settings=get_settings(),
            preview=not args.confirm,
            manual_confirmation=args.confirm,
            actor_id=args.actor_id,
        )
        db.commit()
    print(json.dumps(result, ensure_ascii=True, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
