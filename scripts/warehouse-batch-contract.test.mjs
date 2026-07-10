import assert from 'node:assert/strict';
import { adaptWarehouseBatch, adaptWarehouseTrackingDetail, warehouseRequest, warehouseStage } from '../src/features/shipping/warehouseBatch.js';
assert.equal(warehouseStage('created'), 'warehouse');
assert.equal(warehouseStage('warehouse_returned'), 'review');
assert.equal(warehouseStage('ready_to_writeback'), 'confirm');
assert.equal(warehouseStage('completed'), 'result');
const batch = adaptWarehouseBatch({ id: 2, batch_no: 'SHIP-2', status: 'warehouse_returned', warehouse_sent_at: '2026-07-10', rows: [{ id: 9, local_order_id: 8, order_reference: 'O-1', product_order_reference: 'P-1', row_status: 'removed', is_active: false }] });
assert.equal(batch.stage, 'review');
assert.equal(batch.rows[0].productOrderNo, 'P-1');
assert.equal(batch.rows[0].orderId, 8);
assert.equal(batch.rows[0].removed, true);
assert.equal(batch.rows[0].isActive, false);
assert.equal(batch.requiresWarehouseStop, true);
assert.equal(batch.shippedAt, '2026-07-10');
assert.deepEqual(warehouseRequest.create({ storeId: '1', platform: 'naver', orderIds: ['4'] }), { store_id: 1, platform: 'naver', order_ids: [4], manual_approval: true });
assert.deepEqual(warehouseRequest.importSheet({ fileName: 'return.xlsx', fileContentBase64: 'YWJj' }), { source_file_name: 'return.xlsx', file_content_base64: 'YWJj', manual_approval: true });
assert.deepEqual(warehouseRequest.confirm(['9']), { confirmed_row_ids: [9], manual_approval: true });
assert.deepEqual(warehouseRequest.manifest('approval-value'), { manual_approval: true, privacy_access_acknowledged: true, approval_token: 'approval-value' });
assert.deepEqual(warehouseRequest.remove({ reasonCode: 'order_cancelled', warehouseStoppedShipping: true }), { manual_approval: true, reason_code: 'order_cancelled', warehouse_stopped_shipping: true });
assert.deepEqual(warehouseRequest.writeback('approval-value'), { manual_approval: true, final_operator_confirmation: true, real_api_call_requested: true, approval_token: 'approval-value' });
assert.deepEqual(warehouseRequest.writeback('approval-value', false), { manual_approval: true, final_operator_confirmation: true, real_api_call_requested: false, approval_token: 'approval-value' });
assert.deepEqual(adaptWarehouseTrackingDetail({ tracking_record_id: 3, batch_row_id: 9, product_order_reference: 'P-1', tracking_number: '1234', validation_status: 'ready_for_writeback' }), {
  id: 3, batchRowId: 9, productOrderNo: 'P-1', orderNo: '-', productName: '-', carrier: '-', trackingNumber: '1234', shippedAt: null, status: 'ready_for_writeback', reason: '',
});
console.log('warehouse batch contract checks passed');
