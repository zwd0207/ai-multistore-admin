# T10 Terra R1 - Inquiry Retention And Legacy Sync Gates

## Status

Sol Phase C blocked T10 on two backend boundaries. Operator UI work is accepted and must not be changed.

## Purpose

Make ordinary PXG/Naver inquiry reads fail closed when retention cleanup is unhealthy, and close the legacy Naver inquiry synchronization path during the operator trial.

## Required Fixes

1. Before the ordinary `GET /api/v1/customer-inquiries` response includes any PXG/Naver persisted inquiry, enforce the existing `assert_pxg_naver_cleanup_healthy` gate.
2. Cleanup disabled, no successful run, failed cleanup, manual review, overdue cleanup, expired backup, or sync safety lock must return a privacy-safe 409 response before any PXG inquiry metadata is serialized.
3. Do not impose the PXG cleanup requirement on unrelated stores that have no PXG/Naver persisted source.
4. Disable legacy `POST /api/v1/sync/customer-inquiries/naver` during operator trial mode before token acquisition, Naver network access, sync-log creation, or local inquiry writes.
5. Enforce the legacy-sync closure at service level so `manual-batch` and other internal callers cannot bypass it. Add pre-routing denial for the direct legacy endpoint as defense in depth.
6. Keep the approved guarded `/api/v1/pxg-naver-readonly/refresh` path unchanged and default-disabled.
7. Keep customer reply, platform writes, scheduled sync, AI automation, and additional real persistence disabled.

## Required Tests

1. Extend `verify_customer_inquiry_operator_workflow.py` with a healthy cleanup state so the accepted aggregate workflow still passes.
2. Add failed, manual-review, overdue, disabled, and no-success cleanup cases. Each must block the aggregate response without returning inquiry metadata.
3. Direct legacy Naver inquiry sync with a valid session, MFA, CSRF, store membership, and `platform.sync` must be denied before external-network and local-write functions are called.
4. The manual-batch customer-inquiry path must also be unable to invoke the legacy service during trial mode.
5. Confirm unrelated generic-only stores are not incorrectly blocked by the PXG cleanup gate.
6. Run customer workflow verification, retention cleanup verification, production sessions, and `verify_all.py`.

## Ownership

- `codex1/backend/app/api/v1/endpoints/customer_inquiries.py`
- `codex1/backend/app/services/customer_inquiry_service.py`
- `codex1/backend/app/api/v1/endpoints/sync.py`
- `codex1/backend/app/services/sync_service.py`
- `codex1/backend/app/services/operator_trial_service.py`
- Directly related backend verification scripts only

Do not modify frontend files.

## Return Only

`STATUS / BRANCH / COMMIT / TESTS / CLEANUP_GATE / LEGACY_SYNC_GATE / BLOCKER`
