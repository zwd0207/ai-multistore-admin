import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const includesAll = (file, phrases) => {
  const text = read(file);
  for (const phrase of phrases) assert.ok(text.includes(phrase), `${file} should include "${phrase}"`);
};
const dashboard = read('src/pages/Dashboard.jsx');
const adapters = read('src/services/adapters.js');
const provider = read('src/services/dataProvider.js');

includesAll('codex1/backend/app/api/v1/endpoints/dashboard.py', [
  '@router.get("/store-overview")',
  'get_store_overview',
  'require_session',
  'require_any_store_permission',
]);
includesAll('codex1/backend/app/services/stats_service.py', [
  'def get_store_overview',
  'display_value": "?"',
  'ip_not_allowed',
  'orders_unknown_store_count',
  '_aggregate_store_overview_workbenches',
  'operator_workbench',
]);
includesAll('codex1/backend/app/api/v1/endpoints/sync.py', [
  '@router.post("/manual-batch/all")',
  'manual_batch_sync_all_stores',
]);
includesAll('codex1/backend/app/services/sync_service.py', [
  'def manual_batch_sync_all_stores',
  'store_results',
  'platform_write": False',
]);
includesAll('src/services/backendApi.js', [
  'getStoreOverview',
  "'/dashboard/store-overview'",
  'runManualAllStoresSync',
]);
includesAll('src/services/dataProvider.js', [
  'getStoreOverview',
  'runManualAllStoresSync',
  'mockStoreOverview',
]);

assert.ok(dashboard.includes('operatorWorkbench'), 'dashboard must render operator workbench');
assert.ok(dashboard.includes('state.overview?.operatorWorkbench'), 'dashboard queue must use store overview');
assert.ok(dashboard.includes('\u5168\u90e8\u6388\u6743\u5e97\u94fa'), 'dashboard needs all-store view');
assert.ok(dashboard.includes('\u5355\u5e97'), 'dashboard needs single-store view');
assert.ok(dashboard.includes('setSelectedStoreId(task.storeId)'), 'task navigation must set store before route');
assert.ok(!dashboard.includes('runManualAllStoresSync'), 'dashboard must not call all-store manual sync');
assert.ok(!dashboard.includes('runManualStoreSync'), 'dashboard must not call single-store manual sync');
assert.ok(!dashboard.includes('\u66f4\u65b0\u5168\u90e8\u5e97\u94fa\u6570\u636e'), 'dashboard must remove all-store update button');
assert.ok(!dashboard.includes('\u66f4\u65b0\u6570\u636e'), 'dashboard must remove single-store update button');
assert.ok(dashboard.includes('dashboard-store-table'), 'dashboard store table needs a mobile layout hook');
assert.ok(dashboard.includes('setSelectedStoreId(row.storeId)') && dashboard.includes('to="/orders"') && dashboard.includes('to="/shipping"'), 'dashboard store table must keep all operator actions');
const layoutStyles = read('src/styles/layout.css');
assert.match(layoutStyles, /dashboard-store-table[\s\S]*@media \(max-width: 600px\)/, 'dashboard store table needs a mobile responsive rule');
assert.match(layoutStyles, /dashboard-store-table[\s\S]*table-actions[\s\S]*flex-wrap/, 'dashboard mobile actions must wrap instead of being clipped');
assert.ok(adapters.includes('adaptOperatorWorkbench'), 'adapter must expose operator workbench');
assert.ok(adapters.includes('failedStoreCount'), 'adapter must expose source failure count');
assert.ok(adapters.includes('workbenchSummary'), 'adapter must expose store workbench summary');
assert.ok(provider.includes('operator_workbench'), 'mock provider must preserve overview aggregation');
assert.ok(provider.includes('workbench_summary'), 'mock stores must preserve workbench summary');

console.log('core ERP buildout 2 contract checks passed');
