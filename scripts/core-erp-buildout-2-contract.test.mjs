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

includesAll('codex1/backend/app/api/v1/endpoints/dashboard.py', [
  '@router.get("/store-overview")',
  'get_store_overview',
]);

includesAll('codex1/backend/app/services/stats_service.py', [
  'def get_store_overview',
  'display_value": "?"',
  'ip_not_allowed',
  'manual_batch_sync',
  '最近一次同步无法确认',
  '最近一次同步：IP 白名单未通过',
  'orders_unknown_store_count',
]);

includesAll('codex1/backend/app/api/v1/endpoints/sync.py', [
  '@router.post("/manual-batch/all")',
  'manual_batch_sync_all_stores',
]);

includesAll('codex1/backend/app/services/sync_service.py', [
  'def manual_batch_sync_all_stores',
  'store_results',
  'if include_products',
  'if include_orders',
  'if include_customer_inquiries',
  '_manual_batch_result_status(items)',
  'platform_write": False',
]);

includesAll('src/services/backendApi.js', [
  'getStoreOverview',
  "'/dashboard/store-overview'",
  'runManualAllStoresSync',
  "'/sync/manual-batch/all'",
]);

includesAll('src/services/dataProvider.js', [
  'getStoreOverview',
  'runManualAllStoresSync',
  'mockStoreOverview',
]);

includesAll('src/services/adapters.js', [
  'storeOverview',
  'metricDisplayValue',
  'ordersUnknownStoreCount',
]);

includesAll('src/pages/Dashboard.jsx', [
  '全店铺运营总览',
  '同步全部可用店铺',
  'metricDisplayValue',
  '无法确认时显示“?”',
  '最近一次同步无法确认',
]);

console.log('core ERP buildout 2 contract checks passed');
