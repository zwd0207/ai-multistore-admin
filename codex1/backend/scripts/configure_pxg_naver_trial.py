import argparse
import json
import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import SessionLocal
from app.services.operator_trial_service import (
    assert_store_has_only_artificial_customer_data,
    assert_trial_runtime_closed,
    provision_trial_operator,
    resolve_trial_store,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the isolated PXG Naver artificial-data operator trial")
    parser.add_argument("--apply", action="store_true", help="persist the trial operator assignment")
    args = parser.parse_args()
    settings = get_settings()
    assert_trial_runtime_closed(settings)
    with SessionLocal() as db:
        store = resolve_trial_store(db)
        assert_store_has_only_artificial_customer_data(db, store.id)
        result = {
            "status": "validated",
            "store_id": store.id,
            "store_name": store.name,
            "platform": store.platform,
            "store_id_source": "exact_database_match:name+platform",
            "artificial_data_only": True,
            "real_platform_calls": False,
        }
        if args.apply:
            login = os.environ.get("TRIAL_OPERATOR_LOGIN")
            password = os.environ.get("TRIAL_OPERATOR_PASSWORD")
            mfa_secret = os.environ.get("TRIAL_OPERATOR_MFA_SECRET")
            if not login or not password or not mfa_secret:
                raise RuntimeError("TRIAL_OPERATOR_LOGIN, TRIAL_OPERATOR_PASSWORD and TRIAL_OPERATOR_MFA_SECRET are required")
            result.update(provision_trial_operator(
                db,
                login_identifier=login,
                password=password,
                mfa_secret=mfa_secret,
            ))
            result["status"] = "configured"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
