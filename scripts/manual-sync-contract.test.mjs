import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function includesAll(file, phrases) {
  const text = read(file);
  for (const phrase of phrases) {
    assert.ok(
      text.includes(phrase),
      `${file} should include "${phrase}"`,
    );
  }
}

includesAll('codex1/backend/app/schemas/sync.py', [
  'ManualBatchSyncRequest',
]);

includesAll('codex1/backend/app/api/v1/endpoints/sync.py', [
  '@router.post("/manual-batch")',
  'manual_batch_sync',
]);

includesAll('codex1/backend/app/services/sync_service.py', [
  'def manual_batch_sync',
  'ip_not_allowed',
  'platform_write',
  '客服消息暂未接入真实平台',
  '暂未开放批量订单同步',
]);

includesAll('src/services/backendApi.js', [
  'runManualStoreSync',
  "'/sync/manual-batch'",
]);

includesAll('src/services/dataProvider.js', [
  'runManualStoreSync',
  'manualBatchSyncResult',
]);

includesAll('src/services/adapters.js', [
  'manualBatchSyncResult',
  'IP 白名单未通过',
]);

includesAll('src/components/common/ManualStoreSyncButton.jsx', [
  '手动同步',
  '待同步',
  '同步中...',
  'Coupang：IP 白名单未通过',
  '客服消息暂未接入',
]);

includesAll('src/layouts/AdminLayout.jsx', [
  'ManualStoreSyncButton',
  '<StoreSelector />',
]);

console.log('manual sync contract checks passed');
