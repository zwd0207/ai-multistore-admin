import assert from 'node:assert/strict';
import fs from 'node:fs';
import { adaptStoreOverview } from '../src/services/adapters.js';
import { adaptAutomaticReadAttentionSummary, adaptAutomaticReadStatus } from '../src/utils/automaticReadStatus.js';

const read = (path) => fs.readFileSync(path, 'utf8');
const panel = read('src/components/common/StoreSyncStatusPanel.jsx');
const adapters = read('src/services/adapters.js');
const backendApi = read('src/services/backendApi.js');
const dataProvider = read('src/services/dataProvider.js');
const dashboard = read('src/pages/Dashboard.jsx');
const stores = read('src/pages/Stores.jsx');
const resourcePage = read('src/components/common/ResourcePage.jsx');
const layout = read('src/layouts/AdminLayout.jsx');

const status = adaptAutomaticReadStatus({
  orders: {
    attention_state: 'admin_action',
    operator_message: '连接资料需要验证，请联系管理员处理。',
    admin_action: 'verify_and_recover',
    recovery_eligible: true,
    action_path: '/stores?storeId=8&focus=connection',
  },
});
const ordinaryStatus = adaptAutomaticReadStatus({
  orders: {
    attention_state: 'automatic_retry',
    operator_message: '系统正在自动重试，请稍后查看。',
  },
});
assert.deepEqual(status.orders, {
  status: 'unknown',
  lastSuccessAt: '',
  nextRunAt: '',
  dataFreshUntil: '',
  automaticReadEnabled: undefined,
  retryCount: null,
  safeFailureReason: '',
  safeFailureLabel: '',
  isStale: undefined,
  lastAttemptAt: '',
  attentionState: 'admin_action',
    operatorMessage: '连接资料需要验证，请联系管理员处理。',
    adminAction: 'verify_and_recover',
    recoveryEligible: true,
  actionPath: '/stores?storeId=8&focus=connection',
});
assert.equal(ordinaryStatus.orders.operatorMessage, '系统正在自动重试，请稍后查看。');
assert.equal(ordinaryStatus.orders.adminAction, 'none');
assert.equal(ordinaryStatus.orders.recoveryEligible, false);
assert.equal(ordinaryStatus.orders.actionPath, '');
assert.deepEqual(adaptAutomaticReadAttentionSummary({
  affected_store_count: 2,
  affected_resource_count: 3,
  retrying_count: 1,
  stale_count: 1,
  admin_required_count: 1,
}), {
  affectedStoreCount: 2,
  affectedResourceCount: 3,
  retryingCount: 1,
  staleCount: 1,
  adminRequiredCount: 1,
});
assert.deepEqual(adaptStoreOverview({
  automatic_read_attention_summary: {
    affected_store_count: 2,
    affected_resource_count: 3,
    retrying_count: 1,
    stale_count: 1,
    admin_required_count: 1,
  },
}).automaticReadAttentionSummary, {
  affectedStoreCount: 2,
  affectedResourceCount: 3,
  retryingCount: 1,
  staleCount: 1,
  adminRequiredCount: 1,
});

assert.match(adapters, /automaticReadAttentionSummary: adaptAutomaticReadAttentionSummary/);
const rowAdapter = adapters.slice(adapters.indexOf('function adaptStoreOverviewRow'), adapters.indexOf('export function adaptStoreOverview'));
assert.doesNotMatch(rowAdapter, /automaticReadAttentionSummary/);
assert.match(adapters, /automaticReadStatus: adaptAutomaticReadStatus\(item\.automatic_read_status\)/);
assert.match(backendApi, /`\/stores\/\$\{encodeURIComponent\(storeId\)\}\/automatic-read\/recover`/);
assert.match(backendApi, /\{ confirmation: true \}/);
assert.match(dataProvider, /recoverAutomaticRead: async \(storeId\)/);
assert.match(panel, /attentionState !== 'none'/);
assert.match(panel, /验证通过，已安排恢复/);
assert.match(panel, /MAX_RECOVERY_POLLS = 17/);
assert.match(panel, /RECOVERY_POLL_DELAY_MS = 4000/);
assert.ok(17 * 4000 >= 65000, 'recovery polling window must cover at least 65 seconds');
assert.match(panel, /dataProvider\.getStoreOverview\(\{ includeInactive: false \}\)/);
assert.match(panel, /useState\(attentionSummary\)/);
assert.match(panel, /setVisibleAttentionSummary\(overview\?\.automaticReadAttentionSummary \|\| \{\}\)/);
assert.match(panel, /visibleAttentionSummary\.affectedStoreCount/);
assert.match(panel, /visibleAttentionSummary\.affectedResourceCount/);
assert.doesNotMatch(panel, /runManualStoreSync|runManualAllStoresSync/);
assert.match(panel, /actionPath \|\| connectionActionPath/);
assert.match(panel, /operatorMessage/);
assert.doesNotMatch(panel, /row\.automaticReadAttentionSummary/);
assert.doesNotMatch(panel, /safeFailureReason === 'not_supported'/);
assert.match(panel, /const attentionRows =/);
assert.match(panel, /attentionRows\.map/);
assert.match(panel, /store-sync-attention-stores/);
assert.match(panel, /查看全部店铺状态/);
assert.match(panel, /<AllStoreStatus rows=\{visibleRows\}/);
assert.equal((panel.match(/自动读取正常/g) || []).length, 1);
assert.doesNotMatch(panel, /!attention\.length \?/);
assert.doesNotMatch(panel, /查看完整状态/);
assert.match(dashboard, /credentials\.manage/);
assert.match(dashboard, /platform\.sync/);
assert.match(stores, /useSearchParams/);
assert.match(stores, /queryFocus === 'connection'/);
assert.match(resourcePage, /openRecordId/);
assert.doesNotMatch(layout, /notification.*3|>3<|className="notification"/);

console.log('T16 automatic-read recovery contract passed');
