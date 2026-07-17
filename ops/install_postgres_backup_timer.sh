#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi

BACKEND_ROOT="${BACKEND_ROOT:-/srv/codex1-backend}"
CONFIG_PATH="/etc/ai-multistore/postgres-backup.env"
AGE_KEY_PATH="/etc/ai-multistore/postgres-backup.agekey"
OSS_BUCKET="${BACKUP_OSS_BUCKET:-}"
OSS_ENDPOINT="${BACKUP_OSS_ENDPOINT:-https://oss-ap-northeast-2.aliyuncs.com}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for required in "${BACKEND_ROOT}/scripts/backup_postgres_to_oss.py" "${BACKEND_ROOT}/.env"; do
  [[ -f "${required}" ]] || { echo "required path missing: ${required}" >&2; exit 3; }
done
DATABASE_URL_VALUE="$(sed -n 's/^DATABASE_URL=//p' "${BACKEND_ROOT}/.env" | head -n 1)"
DATABASE_URL_VALUE="${DATABASE_URL_VALUE#\"}"
DATABASE_URL_VALUE="${DATABASE_URL_VALUE%\"}"
DATABASE_URL_VALUE="${DATABASE_URL_VALUE#\'}"
DATABASE_URL_VALUE="${DATABASE_URL_VALUE%\'}"
[[ "${DATABASE_URL_VALUE}" == postgresql://* || "${DATABASE_URL_VALUE}" == postgresql+psycopg://* ]] || {
  echo "application DATABASE_URL must use PostgreSQL before enabling backups" >&2
  exit 4
}
command -v age >/dev/null 2>&1 || { echo "age is required" >&2; exit 5; }
command -v pg_dump >/dev/null 2>&1 || { echo "pg_dump is required" >&2; exit 5; }
"${BACKEND_ROOT}/.venv/bin/python" -c 'import oss2' >/dev/null 2>&1 || { echo "oss2 is required in the backend environment" >&2; exit 5; }

install -d -m 0700 -o aiops -g aiops /var/lib/ai-multistore/backups /run/ai-multistore
install -d -m 0750 -o root -g aiops /etc/ai-multistore
if [[ ! -f "${CONFIG_PATH}" ]]; then
  [[ -n "${OSS_BUCKET}" ]] || { echo "set BACKUP_OSS_BUCKET before installing the timer" >&2; exit 6; }
  command -v age-keygen >/dev/null 2>&1 || { echo "age-keygen is required" >&2; exit 7; }
  if [[ ! -f "${AGE_KEY_PATH}" ]]; then
    umask 077
    age-keygen -o "${AGE_KEY_PATH}" >/dev/null
  fi
  chmod 0600 "${AGE_KEY_PATH}"
  AGE_RECIPIENT="$(awk '/^# public key:/{print $NF; exit}' "${AGE_KEY_PATH}")"
  [[ -n "${AGE_RECIPIENT}" ]] || { echo "could not read generated age recipient" >&2; exit 8; }
  umask 077
  cat > "${CONFIG_PATH}" <<EOF
BACKUP_OSS_BUCKET=${OSS_BUCKET}
BACKUP_OSS_ENDPOINT=${OSS_ENDPOINT}
BACKUP_OSS_ROLE_NAME=aiglxt-prod-backup-role
BACKUP_OSS_PREFIX=postgresql
BACKUP_AGE_RECIPIENT=${AGE_RECIPIENT}
BACKUP_LOCAL_ROOT=/var/lib/ai-multistore/backups
BACKUP_LOCK_PATH=/run/ai-multistore/postgres-backup.lock
EOF
fi
chmod 0600 "${CONFIG_PATH}"

install -m 0644 "${SCRIPT_DIR}/ai-multistore-postgres-backup.service" /etc/systemd/system/ai-multistore-postgres-backup.service
install -m 0644 "${SCRIPT_DIR}/ai-multistore-postgres-backup.timer" /etc/systemd/system/ai-multistore-postgres-backup.timer
systemctl daemon-reload
systemctl enable ai-multistore-postgres-backup.timer
systemctl start ai-multistore-postgres-backup.timer
systemctl is-active ai-multistore-postgres-backup.timer
