import assert from 'node:assert/strict';
import fs from 'node:fs';
import { adaptCustomerInquiry, adaptOrder, adaptOrderLogisticsTrace } from '../src/services/adapters.js';

const read = (file) => fs.readFileSync(file, 'utf8');
const adapters = read('src/services/adapters.js');
const orders = read('src/pages/Orders.jsx');
const customerService = read('src/pages/CustomerService.jsx');
const panel = read('src/components/common/StoreSyncStatusPanel.jsx');
const css = read('src/styles/global.css');

const order = adaptOrder({
  id: 17,
  platform: 'naver',
  delivery_status: 'BACKEND_STATUS',
  delivery_status_label_zh: '平台配送中',
  delivery_company: 'CJ대한통운',
  tracking_number: '123****789',
  logistics_updated_at: '2026-07-13T08:00:00+09:00',
  logistics_stale: true,
  raw_data: { tracking_number: 'MUST_NOT_BE_USED' },
});
assert.equal(order.deliveryStatus, 'BACKEND_STATUS');
assert.equal(order.deliveryStatusLabelZh, '平台配送中');
assert.equal(order.trackingNumber, '123****789');
assert.equal(order.logisticsUpdatedAt, '2026-07-13T08:00:00+09:00');
assert.equal(order.logisticsStale, true);
assert.notEqual(order.trackingNumber, 'MUST_NOT_BE_USED');

const trace = adaptOrderLogisticsTrace({
  tracking_number: '123****789',
  realtime_tracking_open: false,
  logistics_updated_at: '2026-07-13T08:00:00+09:00',
  is_stale: true,
  events: [{ label: '已发货', observed_at: '2026-07-12T08:00:00+09:00' }],
});
assert.equal(trace.trackingNumber, '123****789');
assert.equal(trace.realtimeTrackingOpen, false);
assert.equal(trace.logisticsStale, true);
assert.equal(trace.events.length, 1);

const inquiry = adaptCustomerInquiry({
  inquiry_id: 'inquiry-17',
  logistics_context: {
    carrier: 'CJ대한통운',
    tracking_number_masked: '123****789',
    shipment_status: '平台配送中',
    shipped_at: '2026-07-12T08:00:00+09:00',
    updated_at: '2026-07-13T08:00:00+09:00',
    source_updated_at: '2026-07-13T07:59:00+09:00',
    is_stale: true,
    logistics_stale: true,
  },
});
assert.deepEqual(inquiry.relatedOrder, {
  orderNo: '', productOrderNo: '', productName: '', orderStatus: '', batchNo: '', batchStatus: '', warehouseStatus: '',
  carrier: 'CJ대한통운', trackingNumber: '123****789', trackingStatus: '平台配送中', deliveryStatus: '平台配送中',
  deliveryStatusLabelZh: '平台配送中', shippedAt: '2026-07-12T08:00:00+09:00',
  logisticsUpdatedAt: '2026-07-13T08:00:00+09:00', sourceUpdatedAt: '2026-07-13T07:59:00+09:00', logisticsStale: true, isStale: true,
});

for (const marker of ['deliveryStatusLabelZh', 'logisticsUpdatedAt', 'logisticsValidity', '尚未发货或平台暂无物流信息', 'getOrderLogisticsTrace']) {
  assert.match(orders, new RegExp(marker), `orders must expose ${marker}`);
}
for (const marker of ['logistics_context', '物流状态', '物流更新时间', '物流有效期', '尚未发货或平台暂无物流信息']) {
  assert.match(customerService, new RegExp(marker), `customer service must expose ${marker}`);
}
assert.match(adapters, /delivery_status_label_zh/);
assert.doesNotMatch(adapters, /naverBusinessStatusLabel\(naverDeliveryStatus/);
assert.doesNotMatch(panel, /暂未接入自动读取/);
assert.match(panel, /storeSyncStatusLabel\(resource\?\.status\)/);
assert.match(panel, /rows = EMPTY_ROWS/);
assert.match(panel, /attentionSummary = EMPTY_ATTENTION_SUMMARY/);
assert.match(css, /overflow-wrap: anywhere/);
assert.match(css, /html, body, #root[^\n]*overflow-x: hidden/);

console.log('T17 frontend logistics contract passed');
