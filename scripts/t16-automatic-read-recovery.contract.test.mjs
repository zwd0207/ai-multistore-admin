import assert from 'node:assert/strict';
import fs from 'node:fs';
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
    operator_message: '请检查连接资料。',
    admin_action: 'manual_review',
    recovery_eligible: false,
    action_path: '/stores?storeId=8&focus=connection',
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
  operatorMessage: '请检查连接资料。',
  adminAction: 'manual_review',
  recoveryEligible: false,
  actionPath: '/stores?storeId=8&focus=connection',
});
assert.deepEqual(adaptAutomaticReadAttentionSummary({ attention_count: 1, attention_state: 'admin_action' }), {
  attentionState: 'admin_action',
  attentionCount: 1,
  attentionResources: [],
  operatorMessage: '',
  adminAction: 'none',
  recoveryEligible: false,
  actionPath: '',
});

assert.match(adapters, /automaticReadAttentionSummary: adaptAutomaticReadAttentionSummary/);
assert.match(adapters, /automaticReadStatus: adaptAutomaticReadStatus\(item\.automatic_read_status\)/);
assert.match(backendApi, /`\/stores\/\$\{encodeURIComponent\(storeId\)\}\/automatic-read\/recover`/);
assert.match(backendApi, /\{ confirmation: true \}/);
assert.match(dataProvider, /recoverAutomaticRead: async \(storeId\)/);
assert.match(panel, /attentionState !== 'none'/);
assert.match(panel, /验证通过，已安排恢复/);
assert.match(panel, /MAX_RECOVERY_POLLS = 8/);
assert.match(panel, /dataProvider\.getStoreOverview\(\{ includeInactive: false \}\)/);
assert.match(panel, /actionPath \|\| connectionActionPath/);
assert.match(panel, /operatorMessage/);
assert.match(panel, /automaticReadAttentionSummary/);
assert.doesNotMatch(panel, /safeFailureReason|lastErrorCode/);
assert.match(dashboard, /credentials\.manage/);
assert.match(dashboard, /platform\.sync/);
assert.match(stores, /useSearchParams/);
assert.match(stores, /queryFocus === 'connection'/);
assert.match(resourcePage, /openRecordId/);
assert.doesNotMatch(layout, /notification.*3|>3<|className="notification"/);

console.log('T16 automatic-read recovery contract passed');
