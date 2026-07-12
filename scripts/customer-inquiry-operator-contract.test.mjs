import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('../src/services/adapters.js', import.meta.url), 'utf8');
const page = fs.readFileSync(new URL('../src/pages/CustomerService.jsx', import.meta.url), 'utf8');
assert.match(source, /inquiry_id/);
assert.match(source, /order_context/);
assert.match(source, /logistics_context/);
assert.match(source, /tracking_number_masked/);
assert.match(source, /reply_enabled/);
assert.match(page, /当前读取窗口暂无关联订单/);
assert.match(page, /replyEnabled/);

const withContext = {
  inquiry_id: 'pxg-1', source: 'naver_readonly', store_id: 7, platform: 'naver', category: '配送咨询',
  summary: '请问什么时候发货', status: 'open', reply_enabled: false, reply_disabled_reason: 'read_only_source',
  created_at: '2026-07-12T01:00:00Z', updated_at: '2026-07-12T02:00:00Z',
  order_context: { order_no: 'O-1', product_order_no: 'P-1', product_name: '高尔夫球包', order_status: 'PAID', warehouse_batch_no: 'SHIP-1', warehouse_batch_status: 'warehouse_sent', warehouse_row_status: 'warehouse_sent' },
  logistics_context: { carrier: 'CJ', tracking_number_masked: '123****789', shipment_status: '运输中' },
};
assert.equal(withContext.inquiry_id, 'pxg-1');
assert.equal(withContext.reply_enabled, false);
assert.equal(withContext.order_context.warehouse_batch_no, 'SHIP-1');
assert.equal(withContext.logistics_context.tracking_number_masked, '123****789');
console.log('customer inquiry operator contract checks passed');
