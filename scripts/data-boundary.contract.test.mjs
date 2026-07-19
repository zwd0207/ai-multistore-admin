import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const source = read('src/services/dataSource.js');
const provider = read('src/services/dataProvider.js');
const dashboard = read('src/pages/Dashboard.jsx');
const sales = read('src/pages/Sales.jsx');
const settings = read('src/pages/Settings.jsx');
const layout = read('src/layouts/AdminLayout.jsx');
const backendApi = read('src/services/backendApi.js');
const backendSalesProvider = provider.slice(
  provider.indexOf('async function getBackendSalesReport'),
  provider.indexOf('function normalizeSyncPlatform'),
);

assert.match(source, /VITE_DATA_SOURCE \|\| 'backend'/);
assert.match(source, /requestedSource === 'mock' \? 'mock' : 'backend'/);
assert.match(source, /export const isMockSource/);
assert.match(provider, /if \(!isBackendSource\) return mockApi\[property\];/);
assert.match(provider, /未回退到 Mock/);
assert.doesNotMatch(dashboard, /loadOr\(/);
assert.doesNotMatch(sales, /import mockApi/);
assert.doesNotMatch(settings, /import mockApi/);
assert.doesNotMatch(sales, /首尔美妆测试店/);
assert.match(sales, /dataProvider\.getSalesReport/);
assert.match(sales, /stores: availableStores/);
assert.match(sales, /availableStores\.map/);
assert.match(backendApi, /getSalesStats/);
assert.match(backendApi, /getSalesByPlatform/);
assert.match(backendApi, /getSalesByDate/);
assert.match(backendSalesProvider, /pageSize: 100/);
assert.doesNotMatch(backendSalesProvider, /pageSize: 1000/);
assert.match(provider, /withStoreName\(adapters\.list\(orders, adapters\.order\)\.data, stores\)/);
assert.match(provider, /permissionLimited \? 'permission_limited'/);
assert.match(provider, /其他运营检查结果仍然有效/);
assert.match(provider, /temporarily_unavailable/);
assert.match(provider, /后端和店铺检查结果仍然有效/);
assert.match(layout, /正式 Backend/);
assert.match(layout, /Demo \/ Mock 数据/);
assert.match(provider, /演示模式不提供仓库批次数据/);
assert.match(provider, /演示模式不提供仓库回填操作/);

console.log('data boundary contract checks passed');
