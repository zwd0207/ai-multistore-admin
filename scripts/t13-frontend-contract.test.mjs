import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (file) => readFile(new URL(`../${file}`, import.meta.url), 'utf8');
const stores = await read('src/pages/Stores.jsx');
const orders = await read('src/pages/Orders.jsx');
const api = await read('src/services/backendApi.js');
const provider = await read('src/services/dataProvider.js');
const http = await read('src/services/http.js');
const css = await read('src/styles/global.css');

assert.match(stores, /createStoreOnboarding/);
assert.match(stores, /idempotency_key/);
assert.doesNotMatch(stores, /Test connection|testConnection/i);
assert.match(stores, /getStoreOnboarding/);
assert.match(stores, /setTimeout\(poll, 1500\)/);
assert.match(stores, /sessionStorage\.getItem\(STORAGE_KEY\)/);
assert.doesNotMatch(stores, /sessionStorage\.setItem\([^,]+,\s*(?:form|.*secret)/i);
assert.match(stores, /customer_inquiries/);
assert.match(stores, /optional; not approved/);
assert.match(stores, /status === 'blocked'/);
assert.match(stores, /Edit connection details/);
assert.match(stores, /updateStoreOnboarding\(onboarding\.id/);
assert.match(stores, /setOnboarding\(result\)/);
assert.match(stores, /restartPolling\(onboarding\.id\)/);
assert.match(stores, /status === 'blocked'/);
assert.match(api, /updateStoreOnboarding: .*sendData\('patch'/);
assert.match(api, /updateStoreOnboarding: .*'patch'.*\/store-onboardings/);

assert.match(orders, /Current/);
assert.match(orders, /Historical/);
for (const parameter of ['view', 'page', 'pageSize', 'startAt', 'endAt', 'orderId', 'productOrderId', 'productId', 'productName', 'status', 'buyerName', 'buyerPhone']) {
  assert.match(orders, new RegExp(parameter), `orders must expose ${parameter}`);
}
assert.match(orders, /historicalOrderBackfill/);
assert.match(orders, /Run backfill/);
assert.match(orders, /!historical/);
assert.match(orders, /Historical mode is read-only/);
assert.match(provider, /view: params\?\.view/);
assert.match(provider, /pageSize: params\?\.pageSize/);
assert.match(api, /historicalOrderBackfill: .*historical-backfill/);

assert.match(http, /client\[_-\]\?secret/);
assert.doesNotMatch(stores, /localStorage/);
assert.doesNotMatch(stores, /console\./);
assert.match(css, /@media \(max-width: 600px\)/);
assert.match(css, /\.onboarding-form, \.order-filters \{ grid-template-columns: minmax\(0, 1fr\)/);
assert.match(css, /\.modal-card \{ width: calc\(100vw - 24px\)/);

console.log('T13 frontend contract checks passed');
