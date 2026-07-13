import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (file) => readFile(new URL(`../${file}`, import.meta.url), 'utf8');
const [stores, orders, api, provider, http, css] = await Promise.all([
  read('src/pages/Stores.jsx'),
  read('src/pages/Orders.jsx'),
  read('src/services/backendApi.js'),
  read('src/services/dataProvider.js'),
  read('src/services/http.js'),
  read('src/styles/global.css'),
]);

// The accepted store administration page remains the owner of list/create/edit behavior.
for (const marker of ['ResourcePage', 'canCreate', 'canEdit', 'prepareStoreForm', 'saveStoreCredential', 'findStoreCredential']) {
  assert.match(stores, new RegExp(marker), `Stores must preserve ${marker}`);
}
assert.match(stores, /店铺与平台连接/);
assert.match(stores, /添加 Naver 店铺/);
assert.equal((stores.match(/createStoreOnboarding\(/g) || []).length, 1, 'wizard must submit onboarding once');
assert.doesNotMatch(stores, /测试连接|Test connection|testConnection/i, 'wizard must not add a separate test action');
assert.match(stores, /idempotency_key:\s*idempotencyKeyRef\.current/);
assert.match(stores, /getStoreOnboarding\(onboardingId\)/);
assert.match(stores, /setTimeout\(poll, 1500\)/);
assert.match(stores, /updateStoreOnboarding\(onboarding\.id, payload\)/, 'blocked correction must PATCH the same id');
assert.match(stores, /setPollVersion\(\(value\) => value \+ 1\)/, 'same-id correction must restart polling');
assert.match(stores, /resumeStoreOnboarding\(onboarding\.id\)/);
assert.match(stores, /继续重试/);
assert.match(stores, /修改连接资料/);
assert.match(stores, /可选数据源，尚未批准接入/);
assert.match(stores, /商品/);
assert.match(stores, /订单/);
assert.match(stores, /客服咨询/);
assert.match(stores, /物流/);
assert.match(stores, /sessionStorage\.setItem\(ONBOARDING_STORAGE_KEY, String\(onboardingId\)\)/);
assert.doesNotMatch(stores, /(?:localStorage|sessionStorage)\.setItem\([^\n]*(?:clientSecret|client_secret)/i);
assert.doesNotMatch(stores, /console\./);

// Current orders must retain the mature accepted workflow.
for (const marker of [
  'useSearchParams', 'deepLinkOrderId', 'deepLinkStatus', 'statusTabs', 'ProductCell',
  'handleManualOrderRefresh', 'handleSingleOrderDetailRefresh', 'getOrderLogisticsTrace',
  'traceModal', 'handleCopy', 'openNote', 'copyReceiverText',
]) {
  assert.match(orders, new RegExp(marker), `Current orders must preserve ${marker}`);
}
for (const label of ['全部订单', '新订单', '待发货', '已发货', '取消订单', '退货订单', '换货订单', '异常订单']) {
  assert.match(orders, new RegExp(label), `Current status group must preserve ${label}`);
}
for (const label of ['更新平台订单', '进入仓库发货', '复制收件信息', '内部备注', '查询物流轨迹', '刷新订单详情']) {
  assert.match(orders, new RegExp(label), `Current action must preserve ${label}`);
}
assert.match(orders, /viewMode === 'current'/);
assert.match(orders, /当前订单/);
assert.match(orders, /历史订单/);

// Historical orders use the server contract and expose only detail actions.
for (const parameter of ['view', 'page', 'pageSize', 'startAt', 'endAt', 'orderId', 'productOrderId', 'productId', 'productName', 'status', 'buyerName', 'buyerPhone']) {
  assert.match(orders, new RegExp(parameter), `Historical orders must send ${parameter}`);
}
assert.match(orders, /view:\s*'historical'/);
assert.match(orders, /total=\{historyTotal\}/);
assert.ok(
  orders.includes('renderActions={(row) => <button type="button" onClick={() => setActiveOrder(row)}>详情</button>}'),
  'Historical rows must expose the detail action only',
);
assert.match(orders, /不提供平台更新、发货、复制收件信息、内部备注或智能写作操作/);
assert.match(orders, /单次最多 31 天/);
assert.match(orders, /historicalOrderBackfill\(historyOnboarding\.id/);

// A safe reconnect id may authorize backfill only after strict store association.
assert.match(orders, /String\(result\?\.storeId \|\| ''\) !== String\(storeId\)/);
assert.match(orders, /String\(historyOnboarding\.storeId\) !== String\(storeId\)/);
assert.match(orders, /保存的添加任务不属于当前店铺/);
assert.doesNotMatch(orders, /historicalOrderBackfill\(safeOnboardingId/);

assert.match(api, /updateStoreOnboarding: .*sendData\('patch'/);
assert.match(api, /historicalOrderBackfill: .*historical-backfill/);
assert.match(provider, /view: params\?\.view/);
assert.match(provider, /pageSize: params\?\.pageSize/);
assert.match(http, /client\[_-\]\?secret/);
assert.match(css, /@media \(max-width: 600px\)/);
assert.match(css, /\.onboarding-form, \.order-filters \{ grid-template-columns: minmax\(0, 1fr\)/);
assert.match(css, /\.modal-card \{ width: calc\(100vw - 24px\)/);

console.log('T13 frontend preservation and contract checks passed');
