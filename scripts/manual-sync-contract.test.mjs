import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function includesAll(file, phrases) {
  const text = read(file);
  for (const phrase of phrases) {
    assert.ok(
      text.includes(phrase),
      `${file} should include "${phrase}"`,
    );
  }
}

includesAll('codex1/backend/app/schemas/sync.py', [
  'ManualBatchSyncRequest',
  'NaverOrderManualRefreshRequest',
  'max_count: int = Field(default=20, ge=1, le=20)',
]);

includesAll('codex1/backend/app/models/order.py', [
  'external_product_order_id',
  'buyer_phone',
  'receiver_name',
  'receiver_phone',
  'receiver_address',
  'zip_code',
]);

includesAll('codex1/backend/app/api/v1/endpoints/sync.py', [
  '@router.post("/manual-batch")',
  'manual_batch_sync',
  '@router.post("/orders/naver/manual-refresh")',
  'manual_refresh_naver_orders',
]);

includesAll('codex1/backend/app/services/sync_service.py', [
  'def manual_batch_sync',
  'def manual_batch_sync_all_stores',
  'ip_not_allowed',
  'blocked_by_connection',
  '_manual_batch_apply_connection_blockers',
  '未执行订单同步：平台连接未通过，请先重新同步验证',
  '本次平台连接也未通过',
  'def _manual_sync_naver_orders(db: Session, store_id: int) -> dict',
  'NAVER_ORDER_MANUAL_BATCH_MAX_COUNT = 20',
  'def manual_refresh_naver_orders(',
  'def _sync_naver_order_detail_previews_batch(',
  'product_order_ids=product_order_ids[:size]',
  'json={"productOrderIds": safe_product_order_ids}',
  'external_order_id_full',
  'receiver_address',
  '"address_saved": bool(detail_preview.get("receiver_address") or detail_preview.get("zip_code"))',
  'platform_writes_enabled',
  'preview_naver_orders(',
  'include_detail=True',
  'real_sync=True',
  'source_type=NAVER_ORDER_SYNC_SOURCE_TYPE',
  '_manual_batch_resource_message("naver", "orders", local_result)',
  'platform_write',
  'sync_naver_customer_inquiries',
  'NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE',
]);

const syncServiceText = read('codex1/backend/app/services/sync_service.py');
assert.ok(
  !syncServiceText.includes('_manual_sync_customer_inquiries(store_platform)'),
  'all-store manual sync exception handling must not call customer inquiry sync with missing db/store arguments',
);
assert.ok(
  syncServiceText.includes('_manual_batch_item_from_error(store_platform, "customer_inquiries", exc)'),
  'all-store manual sync should return a safe customer inquiry error item when a store sync fails',
);

includesAll('src/services/backendApi.js', [
  'runManualStoreSync',
  "'/sync/manual-batch'",
  'manualRefreshNaverOrders',
  "'/sync/orders/naver/manual-refresh'",
]);

includesAll('src/services/dataProvider.js', [
  'runManualStoreSync',
  'manualRefreshNaverOrders',
  'manualNaverOrderRefreshResult',
  'manualBatchSyncResult',
]);

includesAll('src/services/adapters.js', [
  'manualBatchSyncResult',
  'manualNaverOrderRefreshResult',
  'fullOrderNo',
  'receiverAddress',
  'IP 白名单未通过',
  'blocked_by_connection',
  '最近一次同步：IP 白名单未通过',
  '平台连接未通过（本次手动同步结果）',
]);

const adapterText = read('src/services/adapters.js');
assert.ok(!adapterText.includes("订单编号已脱敏"), 'adapters should not hide local ERP order number after real local order sync');
assert.ok(!adapterText.includes("买家信息已脱敏"), 'adapters should not hide local ERP buyer fields after real local order sync');
assert.ok(!adapterText.includes("'未保存'"), 'adapters should not show saved receiver/order fields as unsaved');

includesAll('src/components/common/ManualStoreSyncButton.jsx', [
  '手动同步',
  '待同步',
  '正在重新验证...',
  'Coupang：IP 白名单未通过',
  '本次重新验证仍未通过',
  '服务器出口 IP',
  'customerInquiryNotOpenLabel',
]);

includesAll('src/layouts/AdminLayout.jsx', [
  'ManualStoreSyncButton',
  '<StoreSelector />',
]);

includesAll('src/pages/Orders.jsx', [
  '手动批量刷新',
  '正在刷新 Naver 订单...',
  '本地订单刷新完成',
  '不会回填平台',
  'dataProvider.manualRefreshNaverOrders',
]);

console.log('manual sync contract checks passed');
