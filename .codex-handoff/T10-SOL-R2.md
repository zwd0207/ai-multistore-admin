# T10 Sol R2 - Narrow Backend Boundary Re-review

## Scope

Review integration commit `ac2b687` only for the two blockers from the previous Phase C review. Do not repeat frontend implementation review and do not modify code.

## Verify

1. Ordinary `GET /api/v1/customer-inquiries` cannot return PXG/Naver persisted inquiry metadata when cleanup is disabled, missing a successful run, failed, under manual review, overdue, blocked by sync safety, or has an expired undeleted backup.
2. Unrelated stores with generic-only inquiries are not incorrectly blocked by the PXG cleanup gate.
3. Legacy `POST /api/v1/sync/customer-inquiries/naver` is denied during operator trial mode before token acquisition, Naver network access, sync-log creation, or local inquiry writes.
4. Internal callers, including manual-batch customer-inquiry sync, cannot bypass the service-level legacy-sync gate.
5. The guarded PXG/Naver readonly refresh remains default-disabled and unchanged.
6. Customer sending, platform writes, scheduled sync, AI automation, and additional persistence remain disabled.

## Commander Evidence

- Customer inquiry workflow verification passed.
- PXG/Naver retention cleanup verification passed.
- Production session verification passed.
- Full `verify_all.py` passed.

## Return Only

`STATUS passed|blocked / CLEANUP_GATE / LEGACY_SYNC_GATE / SECURITY / PRIVACY / WRITE_BOUNDARY / BLOCKER / NEXT`
