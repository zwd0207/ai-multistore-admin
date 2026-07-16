#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  age \
  certbot \
  postgresql-16 \
  postgresql-client-16 \
  python3-certbot-nginx

if ! swapon --show=NAME --noheadings | grep -qx '/swapfile'; then
  if [[ ! -e /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile >/dev/null
  fi
  swapon /swapfile
fi
if ! grep -qE '^/swapfile[[:space:]]' /etc/fstab; then
  printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
fi

systemctl enable --now postgresql

install -d -m 0750 -o root -g deploy /etc/ai-multistore
POSTGRES_ENV=/etc/ai-multistore/postgresql.env
if [[ ! -f "${POSTGRES_ENV}" ]]; then
  umask 077
  DATABASE_PASSWORD="$(openssl rand -hex 32)"
  cat > "${POSTGRES_ENV}" <<EOF
DATABASE_NAME=ai_multistore
DATABASE_USER=ai_multistore
DATABASE_PASSWORD=${DATABASE_PASSWORD}
DATABASE_URL=postgresql+psycopg://ai_multistore:${DATABASE_PASSWORD}@127.0.0.1:5432/ai_multistore
EOF
fi
chmod 0600 "${POSTGRES_ENV}"

set -a
# shellcheck disable=SC1090
source "${POSTGRES_ENV}"
set +a

if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DATABASE_USER}'" | grep -qx 1; then
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 \
    -c "CREATE ROLE ${DATABASE_USER} LOGIN PASSWORD '${DATABASE_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;"
else
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 \
    -c "ALTER ROLE ${DATABASE_USER} PASSWORD '${DATABASE_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;"
fi
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DATABASE_NAME}'" | grep -qx 1; then
  runuser -u postgres -- createdb --owner "${DATABASE_USER}" "${DATABASE_NAME}"
fi

LISTEN_ADDRESSES="$(runuser -u postgres -- psql -tAc 'SHOW listen_addresses')"
if [[ "${LISTEN_ADDRESSES}" != "localhost" ]]; then
  echo "PostgreSQL must listen on localhost only; observed: ${LISTEN_ADDRESSES}" >&2
  exit 3
fi

if [[ "${HARDEN_SSH:-false}" == "true" ]]; then
  if ! id deploy >/dev/null 2>&1 || [[ ! -s /home/deploy/.ssh/authorized_keys ]]; then
    echo "deploy key login is not ready; refusing to disable root SSH" >&2
    exit 4
  fi
  cat > /etc/ssh/sshd_config.d/99-ai-multistore-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
EOF
  sshd -t
  systemctl reload ssh
fi

printf 'postgresql=ready\n'
printf 'swap_bytes=%s\n' "$(swapon --show=SIZE --bytes --noheadings | awk '{sum += $1} END {print sum + 0}')"
printf 'database_url_file=%s\n' "${POSTGRES_ENV}"
printf 'ssh_hardened=%s\n' "${HARDEN_SSH:-false}"
