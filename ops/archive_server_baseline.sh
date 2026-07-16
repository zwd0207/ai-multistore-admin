#!/usr/bin/env bash
set -euo pipefail

ARCHIVE_ROOT="${ARCHIVE_ROOT:-/srv/release-archives}"
FRONTEND_ROOT="${FRONTEND_ROOT:-/srv/ai-multistore-admin}"
BACKEND_ROOT="${BACKEND_ROOT:-/srv/codex1-backend}"
SERVICE_NAME="${SERVICE_NAME:-ai-multistore-api.service}"
TIMESTAMP="${TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
ARCHIVE_DIR="${ARCHIVE_ROOT}/t21-baseline-${TIMESTAMP}"

case "${ARCHIVE_ROOT}" in
  /srv/release-archives|/srv/release-archives/*) ;;
  *) echo "archive root must stay under /srv/release-archives" >&2; exit 2 ;;
esac

for required_path in "${FRONTEND_ROOT}" "${BACKEND_ROOT}" "${BACKEND_ROOT}/data/codex1.db"; do
  if [[ ! -e "${required_path}" ]]; then
    echo "required path missing: ${required_path}" >&2
    exit 3
  fi
done

install -d -m 0700 "${ARCHIVE_DIR}"

tar -C "$(dirname "${FRONTEND_ROOT}")" -czf "${ARCHIVE_DIR}/frontend-source.tar.gz" \
  --exclude='ai-multistore-admin/.git' \
  --exclude='ai-multistore-admin/node_modules' \
  --exclude='ai-multistore-admin/.playwright-cli' \
  "$(basename "${FRONTEND_ROOT}")"

tar -C "$(dirname "${BACKEND_ROOT}")" -czf "${ARCHIVE_DIR}/backend-source.tar.gz" \
  --exclude='codex1-backend/.venv' \
  --exclude='codex1-backend/.env' \
  --exclude='codex1-backend/backups' \
  --exclude='codex1-backend/data' \
  --exclude='codex1-backend/logs' \
  --exclude='codex1-backend/__pycache__' \
  --exclude='codex1-backend/**/*.log' \
  "$(basename "${BACKEND_ROOT}")"

if [[ -f "${BACKEND_ROOT}/.env" ]]; then
  install -m 0600 "${BACKEND_ROOT}/.env" "${ARCHIVE_DIR}/backend.env"
fi
systemctl cat "${SERVICE_NAME}" > "${ARCHIVE_DIR}/systemd-service.txt"
nginx -T > "${ARCHIVE_DIR}/nginx-config.txt" 2>&1

python3 - "${BACKEND_ROOT}/data/codex1.db" "${ARCHIVE_DIR}/codex1.db" "${ARCHIVE_DIR}/database-verification.json" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

source_path = Path(sys.argv[1]).resolve()
backup_path = Path(sys.argv[2]).resolve()
verification_path = Path(sys.argv[3]).resolve()

with sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True) as source:
    with sqlite3.connect(backup_path) as destination:
        source.backup(destination)

def inspect(path: Path) -> tuple[str, dict[str, int]]:
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in tables
        }
    return integrity, counts

source_integrity, source_counts = inspect(source_path)
backup_integrity, backup_counts = inspect(backup_path)
verified = source_integrity == backup_integrity == "ok" and source_counts == backup_counts
verification = {
    "status": "verified" if verified else "failed",
    "source_integrity": source_integrity,
    "backup_integrity": backup_integrity,
    "source_counts": source_counts,
    "backup_counts": backup_counts,
    "production_database_modified": False,
}
verification_path.write_text(json.dumps(verification, indent=2, sort_keys=True), encoding="utf-8")
if not verified:
    raise SystemExit("database backup verification failed")
PY

chmod 0600 "${ARCHIVE_DIR}/codex1.db" "${ARCHIVE_DIR}/database-verification.json"

if git -C "${FRONTEND_ROOT}" rev-parse HEAD >/dev/null 2>&1; then
  {
    printf 'frontend_branch=%s\n' "$(git -C "${FRONTEND_ROOT}" branch --show-current)"
    printf 'frontend_commit=%s\n' "$(git -C "${FRONTEND_ROOT}" rev-parse HEAD)"
  } > "${ARCHIVE_DIR}/version-manifest.txt"
else
  printf 'frontend_commit=unknown\n' > "${ARCHIVE_DIR}/version-manifest.txt"
fi
printf 'backend_commit=untracked-deployment\n' >> "${ARCHIVE_DIR}/version-manifest.txt"
printf 'created_at=%s\n' "${TIMESTAMP}" >> "${ARCHIVE_DIR}/version-manifest.txt"

(
  cd "${ARCHIVE_DIR}"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS >/dev/null
)
chmod -R go-rwx "${ARCHIVE_DIR}"
printf '%s\n' "${ARCHIVE_DIR}"
