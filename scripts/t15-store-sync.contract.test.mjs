import assert from 'node:assert/strict';
import fs from 'node:fs';
import { formatStoreSyncTime, STORE_SYNC_STATUS_LABELS } from '../src/utils/storeSyncStatus.js';
import { adaptAutomaticReadStatus } from '../src/utils/automaticReadStatus.js';

const panel = fs.readFileSync('src/components/common/StoreSyncStatusPanel.jsx', 'utf8');
const adapters = fs.readFileSync('src/services/adapters.js', 'utf8');
const styles = fs.readFileSync('src/styles/layout.css', 'utf8');
const backendSample = adaptAutomaticReadStatus({
  orders: { status: 'success', last_success_at: '2026-07-13T08:00:00+09:00', next_run_at: '2026-07-13T09:00:00+09:00', data_fresh_until: '2026-07-13T09:30:00+09:00', automatic_read_enabled: true, retry_count: 0, is_stale: false, last_attempt_at: '2026-07-13T08:00:00+09:00' },
  customer_inquiries: { status: 'running', next_run_at: '2026-07-13T08:30:00+09:00' },
  products: { status: 'retry_wait', retry_count: 2, safe_failure_reason: 'temporary_platform_or_network_failure' },
  logistics: { status: 'blocked', automatic_read_enabled: false, safe_failure_reason: 'not_supported' },
});

assert.equal(backendSample.orders.status, 'success');
assert.equal(backendSample.orders.nextRunAt, '2026-07-13T09:00:00+09:00');
assert.equal(backendSample.orders.lastAttemptAt, '2026-07-13T08:00:00+09:00');
assert.equal(backendSample.products.safeFailureLabel, '平台或网络暂时异常');
assert.equal(backendSample.logistics.safeFailureLabel, '暂未接入自动读取');
assert.equal(formatStoreSyncTime('2026-07-13T05:20:12.000000'), '2026-07-13 14:20 KST');
assert.deepEqual(Object.keys(STORE_SYNC_STATUS_LABELS), ['idle', 'due', 'running', 'retry_wait', 'blocked', 'success', 'stale', 'disabled']);
assert.match(adapters, /automaticReadStatus: adaptAutomaticReadStatus\(item\.automatic_read_status\)/);
assert.match(panel, /row\.automaticReadStatus/);
assert.doesNotMatch(panel, /row\.resources/);
assert.doesNotMatch(panel, /lastErrorCode|lease|租约|taskId|内部任务/);
assert.doesNotMatch(panel, /safeFailureReason === 'not_supported'/);
assert.doesNotMatch(panel, /暂未接入自动读取/);
assert.match(panel, /attentionState !== 'none'/);
assert.match(styles, /store-sync-resource-grid/);

console.log('T15 store sync contract passed');
