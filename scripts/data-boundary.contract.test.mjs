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

assert.match(source, /VITE_DATA_SOURCE \|\| 'backend'/);
assert.match(source, /requestedSource === 'mock' \? 'mock' : 'backend'/);
assert.match(source, /export const isMockSource/);
assert.match(provider, /if \(!isBackendSource\) return mockApi\[property\];/);
assert.match(provider, /未回退到 Mock/);
assert.doesNotMatch(dashboard, /loadOr\(/);
assert.doesNotMatch(sales, /import mockApi/);
assert.doesNotMatch(settings, /import mockApi/);
assert.match(sales, /dataProvider\.getSalesReport/);
assert.match(backendApi, /getSalesStats/);
assert.match(backendApi, /getSalesByPlatform/);
assert.match(backendApi, /getSalesByDate/);
assert.match(layout, /正式 Backend/);
assert.match(layout, /Demo \/ Mock 数据/);
assert.match(provider, /演示模式不提供仓库批次数据/);
assert.match(provider, /演示模式不提供仓库回填操作/);

console.log('data boundary contract checks passed');
