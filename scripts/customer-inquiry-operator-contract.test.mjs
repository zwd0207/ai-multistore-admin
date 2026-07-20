import assert from 'node:assert/strict';
import { adaptCustomerInquiry, adaptStore } from '../src/services/adapters.js';

const withContext = adaptCustomerInquiry({
  inquiry_id: 'pxg-1', source: 'naver_readonly', store_id: 7, platform: 'naver', category: '配送咨询',
  summary: '请问什么时候发货', classification: 'unanswered', status: 'open', reply_enabled: false, reply_disabled_reason: 'read_only_source',
  order_context: { order_no: 'O-1', product_order_no: 'P-1', product_name: '高尔夫球包', order_status: 'PAID', warehouse_batch_no: 'SHIP-1', warehouse_batch_status: 'warehouse_sent', warehouse_row_status: 'warehouse_sent' },
  logistics_context: { carrier: 'CJ', tracking_number_masked: '123****789', shipment_status: '运输中' },
});
assert.equal(withContext.id, 'pxg-1');
assert.equal(withContext.ticketNo, 'pxg-1');
assert.equal(withContext.replyEnabled, false);
assert.equal(withContext.replyClassification, 'unanswered');
assert.equal(withContext.replyClassificationLabel, '未回复');
assert.equal(withContext.hasRelatedOrder, true);
assert.equal(withContext.relatedOrder.batchNo, 'SHIP-1');
assert.equal(withContext.relatedOrder.trackingNumber, '123****789');

const withoutContext = adaptCustomerInquiry({ inquiry_id: 'generic-1', source: 'generic', store_id: 7, platform: 'coupang', summary: '需要帮助', classification: 'answered', status: 'open', reply_enabled: false, reply_disabled_reason: 'legacy_readonly' });
assert.equal(withoutContext.hasRelatedOrder, false);
assert.equal(withoutContext.replyClassification, 'answered');
assert.equal(withoutContext.replyEnabled, false);

const legacy = adaptCustomerInquiry({ id: 3, external_inquiry_id: 'legacy-3', related_order: { order_no: 'OLD-3' } });
assert.equal(legacy.ticketNo, 'legacy-3');
assert.equal(legacy.hasRelatedOrder, true);
assert.equal(legacy.replyEnabled, false);
assert.equal(adaptStore({ id: 7, name: 'PXG', platform: 'naver' }).name, 'PXG');
console.log('customer inquiry runtime contract checks passed');
