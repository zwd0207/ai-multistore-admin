export const REMOVE_REASON_CODES = {
  '收件信息需要修改': 'address_issue',
  '客户要求取消': 'customer_request',
  '订单已取消': 'order_cancelled',
  '商品货号有误': 'sku_mapping_error',
  '商品缺货': 'stock_unavailable',
  '仓库异常': 'warehouse_exception',
};

export function warehouseStage(status = '') {
  if (['created', 'warehouse_sent'].includes(status)) return 'warehouse';
  if (status === 'warehouse_returned') return 'review';
  if (['ready_to_writeback', 'writeback_partial'].includes(status)) return 'confirm';
  if (['completed', 'cancelled'].includes(status)) return 'result';
  return 'prepare';
}

export function adaptWarehouseBatch(batch = {}) {
  return {
    id: batch.id,
    code: batch.batch_no || batch.batchNo || '-',
    storeId: batch.store_id ?? batch.storeId,
    platform: batch.platform || '-',
    status: batch.status || 'created',
    stage: warehouseStage(batch.status),
    rows: Array.isArray(batch.rows) ? batch.rows.map((row) => ({
      id: row.id,
      orderId: row.local_order_id ?? row.localOrderId,
      orderNo: row.order_reference ?? row.orderReference ?? '-',
      productOrderNo: row.product_order_reference ?? row.productOrderReference ?? '-',
      productName: row.product_name ?? row.productName ?? '-',
      quantity: Number(row.quantity || 0),
      inventoryCode: row.logistics_inventory_code ?? row.logisticsInventoryCode ?? '-',
      rowStatus: row.row_status ?? row.rowStatus ?? '-',
      failureReason: row.failure_reason ?? row.failureReason ?? '',
      carrier: row.carrier ?? '',
    })) : [],
    counts: batch.counts || { normal: 0, needs_confirmation: 0, blocked: 0, failed: 0 },
  };
}

export const warehouseRequest = {
  create: ({ storeId, platform, orderIds }) => ({ store_id: Number(storeId), platform, order_ids: orderIds.map(Number), manual_approval: true }),
  importSheet: ({ fileName, fileContentBase64 }) => ({ source_file_name: fileName, file_content_base64: fileContentBase64, manual_approval: true }),
  confirm: (rowIds) => ({ confirmed_row_ids: rowIds.map(Number), manual_approval: true }),
  remove: ({ reasonCode, warehouseStoppedShipping }) => ({ manual_approval: true, reason_code: reasonCode, warehouse_stopped_shipping: Boolean(warehouseStoppedShipping) }),
  manifest: (approvalToken) => ({ manual_approval: true, privacy_access_acknowledged: true, approval_token: approvalToken }),
  writeback: (approvalToken) => ({ manual_approval: true, final_operator_confirmation: true, real_api_call_requested: false, approval_token: approvalToken }),
};
