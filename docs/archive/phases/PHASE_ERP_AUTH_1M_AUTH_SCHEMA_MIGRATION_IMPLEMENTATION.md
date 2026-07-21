# Phase ERP-Auth-1M: Auth schema migration implementation

## Result

The local ERP auth foundation schema was implemented and applied to the real local Codex1 database.

## Code Changes

Codex1 added:

- `backend/app/models/auth.py`
- `backend/scripts/upgrade_auth_schema.py`

Codex1 updated:

- `backend/app/models/__init__.py`
- `backend/app/models/store.py`
- `backend/app/database.py`
- `backend/scripts/verify_all.py`

## Pre-Migration Backup

Backup path:

```text
C:/Users/Administrator/Desktop/AI 多店铺运营系统项目/codex1-db-backups/codex1.db.backup-erp-auth-1m-20260704-124809.db
```

Manifest path:

```text
C:/Users/Administrator/Desktop/AI 多店铺运营系统项目/codex1-db-backups/codex1.db.backup-erp-auth-1m-20260704-124809.db.manifest.json
```

Backup safety:

- `backup_created=true`
- `manifest_written=true`
- `sqlite_integrity_check=ok`
- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`
- `real_restore_executed=false`

## Migration Output

`upgrade_auth_schema.py` reported:

```text
auth schema already up to date
auth seed counts: roles=5, permissions=10, role_permissions=35, users=0, store_memberships=0
```

## Boundary

This phase created auth foundation tables and safe system metadata only. It did not create real users, assign store memberships, enable login, call Naver, write products/orders/SyncLog/tested-success rows, execute restore, or open formal sync.

