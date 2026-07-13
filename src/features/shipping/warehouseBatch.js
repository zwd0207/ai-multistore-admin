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
  const status = batch.status || 'created';
  return {
    id: batch.id,
    code: batch.batch_no || batch.batchNo || '-',
    storeId: batch.store_id ?? batch.storeId,
    platform: batch.platform || '-',
    status,
    stage: warehouseStage(status),
    shippedAt: batch.warehouse_sent_at ?? batch.warehouseSentAt ?? null,
    requiresWarehouseStop: ['warehouse_sent', 'warehouse_returned', 'ready_to_writeback', 'writeback_partial'].includes(status),
    failed: status === 'writeback_partial' || Number(batch.counts?.failed || 0) > 0,
    writebackCapability: adaptWarehouseWritebackCapability(batch.writeback_capability),
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
      shippedAt: row.shipped_at ?? row.shippedAt ?? null,
      isActive: row.is_active ?? row.isActive ?? true,
      removed: row.row_status === 'removed' || row.rowStatus === 'removed' || (row.is_active ?? row.isActive) === false,
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
  writeback: (approvalToken, realApiCallRequested = true) => ({ manual_approval: true, final_operator_confirmation: true, real_api_call_requested: Boolean(realApiCallRequested), approval_token: approvalToken }),
  reconcile: () => ({ action: 'reconcile', manual_approval: true, final_operator_confirmation: false, real_api_call_requested: false }),
};

export function adaptWarehouseTrackingDetail(row = {}) {
  const trackingNumber = row.tracking_number ?? row.trackingNumber ?? '';
  return {
    id: row.tracking_record_id ?? row.trackingRecordId ?? row.batch_row_id ?? row.batchRowId,
    batchRowId: row.batch_row_id ?? row.batchRowId,
    productOrderNo: row.product_order_reference ?? row.productOrderReference ?? '-',
    orderNo: row.order_reference ?? row.orderReference ?? '-',
    productName: row.product_name ?? row.productName ?? '-',
    carrier: row.carrier ?? '-',
    trackingNumber: trackingNumber || '-',
    trackingNumberTail: row.tracking_number_tail ?? row.trackingNumberTail ?? (trackingNumber ? `...${trackingNumber.slice(-4)}` : '-'),
    shippedAt: row.shipped_at ?? row.shippedAt ?? null,
    status: row.validation_status ?? row.validationStatus ?? 'blocked',
    reason: row.exception_reason ?? row.exceptionReason ?? '',
  };
}

export function adaptWarehouseWritebackCapability(data = {}) {
  const capability = data.writeback_capability || data.writebackCapability || data;
  if (!capability || typeof capability !== 'object') return null;
  return {
    status: capability.status || 'unknown',
    pilotEnabled: capability.pilot_enabled,
    maxRows: capability.max_rows,
    candidateCount: capability.candidate_count,
    operatorMessage: capability.operator_message || '',
    platformCheckedAt: capability.platform_checked_at || '-',
    approvalExpiresAt: capability.approval_expires_at || '-',
    reconciliationRequired: capability.reconciliation_required,
    allowedAction: capability.allowed_action || 'none',
    storeName: capability.store_name || capability.storeName || '-',
    productOrderNo: capability.product_order_reference || '-',
    carrier: capability.carrier || '-',
    trackingNumberMasked: capability.tracking_number_masked || '-',
    platformLatestStatus: capability.platform_latest_status || '-',
  };
}

export function writebackResultLabel(status = '') {
  if (status === 'success') return '完成';
  if (['failed', 'platform_failed', 'partial_success'].includes(status)) return '失败';
  if (status === 'platform_written') return '完成';
  if (status === 'ready_for_writeback') return '待提交';
  if (status === 'reconciled_success') return '完成';
  if (status === 'unknown') return '平台结果待核对';
  return status || '平台结果待核对';
}
