# T09 Sol Activation Policy

Status: activation blocked. Real readonly persistence must remain disabled.

## Retention

- Never persist raw platform responses, request headers, tokens, secrets, or credentials.
- Do not persist customer inquiry body content during the first sync.
- Encrypted recipient PII becomes unusable after 15 minutes.
- Delete recipient PII seven days after shipment completion or order cancellation, and never later than 30 days after collection.
- Delete encrypted full tracking numbers 30 days after delivery; retain only masked values and irreversible hashes.
- Retain product, order, masked logistics, and inquiry metadata for 90 days.
- Retain PII-free audit evidence for one year.
- Encrypted backups follow the same data lifecycle and must not preserve expired PII.
- Cleanup runs at least daily. Cleanup failure blocks display, approval, export, and activation.
- Cleanup affects only `pxg_naver_readonly_local_v1`; unfinished warehouse batches require freeze and manual review.

## First Sync

- One manual PXG/Naver sync only; no schedule, repeat refresh, or all-store sync.
- Maximum: 3 products, 3 product-order rows, 3 matching logistics records, and 10 one-day inquiry metadata records.
- Preserve all product-order rows sharing a platform order id.
- Any limit, missing product-order id, duplicate conflict, or count mismatch rolls back the complete batch.
- A second sync is forbidden until a separate operator verifies count, deduplication, masking, store scope, and warehouse usability.

## Backup And Rollback

- Create an encrypted backup with checksum, timestamp, schema version, and responsible operator.
- Restore the backup into a copy and verify order counts, uniqueness, permissions, and sessions before activation.
- Persist the first sync in one transaction; any failure rolls back the whole batch.
- Rollback must disable persistence and refresh, revoke unused approvals, isolate the batch, and restore or delete only batch-created records.
- Rollback must not remove pre-existing orders, batches, accounts, permissions, or audit evidence.
- Re-run deduplication, store isolation, privacy scan, and disabled-write verification after rollback.

## Blockers

- Automatic cleanup and cleanup audit are not implemented or verified.
- Real-data backup lifecycle and batch-specific rollback are not fully verified.
- `PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED` must remain disabled until both blockers pass Sol review.
