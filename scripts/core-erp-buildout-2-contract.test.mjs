import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const dashboard = read('src/pages/Dashboard.jsx');
const adapters = read('src/services/adapters.js');
const provider = read('src/services/dataProvider.js');

assert.ok(dashboard.includes('operatorWorkbench'), 'dashboard must render operator workbench');
assert.ok(dashboard.includes('state.overview?.operatorWorkbench'), 'dashboard queue must use store overview');
assert.ok(dashboard.includes('\u5168\u90e8\u6388\u6743\u5e97\u94fa'), 'dashboard needs all-store view');
assert.ok(dashboard.includes('\u5355\u5e97'), 'dashboard needs single-store view');
assert.ok(dashboard.includes('setSelectedStoreId(task.storeId)'), 'task navigation must set store before route');
assert.ok(!dashboard.includes('runManualAllStoresSync'), 'dashboard must not call all-store manual sync');
assert.ok(!dashboard.includes('runManualStoreSync'), 'dashboard must not call single-store manual sync');
assert.ok(!dashboard.includes('\u66f4\u65b0\u5168\u90e8\u5e97\u94fa\u6570\u636e'), 'dashboard must remove all-store update button');
assert.ok(!dashboard.includes('\u66f4\u65b0\u6570\u636e'), 'dashboard must remove single-store update button');
assert.ok(adapters.includes('adaptOperatorWorkbench'), 'adapter must expose operator workbench');
assert.ok(adapters.includes('failedStoreCount'), 'adapter must expose source failure count');
assert.ok(adapters.includes('workbenchSummary'), 'adapter must expose store workbench summary');
assert.ok(provider.includes('operator_workbench'), 'mock provider must preserve overview aggregation');
assert.ok(provider.includes('workbench_summary'), 'mock stores must preserve workbench summary');

console.log('core ERP buildout 2 contract checks passed');
