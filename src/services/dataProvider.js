import adapters from './adapters';
import backendApi from './backendApi';
import mockApi from './mockApi';

const requestedSource = String(import.meta.env?.VITE_DATA_SOURCE || 'mock').toLowerCase();
const DATA_SOURCE = requestedSource === 'backend' ? 'backend' : 'mock';
const isBackendSource = DATA_SOURCE === 'backend';
let backendStoresPromise;

const comparable = (value) => String(value ?? '').toLowerCase();

function queryBackendRows(rows, params = {}) {
  const {
    keyword = '', status = '', platform = '', page = 1, pageSize = 5,
  } = params;
  let filtered = [...rows];

  if (keyword) {
    const expected = comparable(keyword);
    filtered = filtered.filter((item) => Object.values(item).some((value) => comparable(value).includes(expected)));
  }
  if (status) filtered = filtered.filter((item) => comparable(item.status || item.testStatus) === comparable(status));
  if (platform) {
    filtered = filtered.filter((item) => (
      comparable(item.platform) === comparable(platform)
      || comparable(item.rawPlatform) === comparable(platform)
    ));
  }
  if (params.priority) filtered = filtered.filter((item) => comparable(item.priority) === comparable(params.priority));
  if (params.module) filtered = filtered.filter((item) => comparable(item.module) === comparable(params.module));
  if (params.actionType) filtered = filtered.filter((item) => comparable(item.actionType) === comparable(params.actionType));
  if (params.operator) filtered = filtered.filter((item) => comparable(item.operator) === comparable(params.operator));
  if (params.riskLevel) filtered = filtered.filter((item) => comparable(item.riskLevel) === comparable(params.riskLevel));
  if (params.startDate || params.endDate) {
    filtered = filtered.filter((item) => {
      const sourceDate = String(item.time || item.createdAt || item.startedAt || '').slice(0, 10);
      if (params.startDate && sourceDate < params.startDate) return false;
      if (params.endDate && sourceDate > params.endDate) return false;
      return true;
    });
  }

  const start = (page - 1) * pageSize;
  const data = filtered.slice(start, start + pageSize);
  return { data, items: data, total: filtered.length, page, pageSize };
}

async function getBackendStores() {
  if (!backendStoresPromise) {
    backendStoresPromise = backendApi.getStores({ page: 1, pageSize: 100 })
      .then((result) => adapters.list(result, adapters.store).data)
      .catch((error) => {
        backendStoresPromise = undefined;
        throw error;
      });
  }
  return backendStoresPromise;
}

function resetBackendStoresCache() {
  backendStoresPromise = undefined;
}

async function resolveBackendStore(params = {}) {
  const stores = await getBackendStores();
  const requestedId = params.storeId ?? params.store_id;
  const store = requestedId ? stores.find((item) => String(item.id) === String(requestedId)) : null;
  if (!store) throw new Error('Codex1 后端暂无可用店铺，请先创建或导入店铺数据');
  return { store, stores };
}

function withStoreName(items, stores) {
  const names = new Map(stores.map((store) => [String(store.id), store.name]));
  return items.map((item) => ({ ...item, store: names.get(String(item.storeId)) || item.store }));
}

function normalizeSyncPlatform(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'naver') return 'naver';
  if (normalized === 'coupang') return 'coupang';
  return normalized;
}

function mockSyncResult(type, payload = {}) {
  return {
    platform: normalizeSyncPlatform(payload.platform),
    storeId: payload.storeId,
    syncType: type,
    message: `local frontend mock ${type} sync completed`,
  };
}

function mockManualBatchSyncResult(payload = {}) {
  const platforms = (payload.platforms || ['naver'])
    .map(normalizeSyncPlatform)
    .filter(Boolean);
  const items = [];
  for (const platform of platforms.length ? platforms : ['naver']) {
    if (payload.include_products !== false) {
      items.push({
        status: 'skipped',
        platform,
        resource: 'products',
        message: '演示模式不调用真实平台',
        error_code: 'mock_mode',
        platform_write: false,
      });
    }
    if (payload.include_orders !== false) {
      items.push({
        status: 'skipped',
        platform,
        resource: 'orders',
        message: '演示模式不调用真实平台',
        error_code: 'mock_mode',
        platform_write: false,
      });
    }
    if (payload.include_customer_inquiries !== false) {
      items.push({
        status: 'skipped',
        platform,
        resource: 'customer_inquiries',
        message: '客服消息暂未接入真实平台',
        error_code: 'not_open',
        platform_write: false,
      });
    }
  }
  return {
    status: 'skipped',
    store_id: payload.store_id || payload.storeId,
    store_platform: platforms[0] || 'naver',
    requested_platforms: platforms,
    replace_policy: payload.replace_policy || 'delete_absent_when_full_snapshot',
    delete_policy: 'delete_absent_only_when_full_snapshot_confirmed',
    platform_write: false,
    items,
    summary: {
      success_count: 0,
      failed_count: 0,
      skipped_count: items.length,
      created_count: 0,
      updated_count: 0,
      deleted_count: 0,
    },
  };
}

function overviewMetric(value, dataStatus = 'confirmed', reason = '') {
  return {
    value,
    display_value: value === null || value === undefined ? '?' : String(value),
    data_status: dataStatus,
    reason,
  };
}

function mockManualNaverOrderRefreshResult(payload = {}) {
  return {
    status: 'success',
    store_id: payload.store_id ?? payload.storeId,
    platform: 'naver',
    resource: 'orders',
    message: '本地订单刷新完成：新增 0，更新 0，跳过 0。不会回填平台。',
    created_count: 0,
    updated_count: 0,
    skipped_count: 0,
    no_change_count: 0,
    source_type: 'mock',
    platform_write: false,
    platform_writes_enabled: false,
    raw_response_saved: false,
    privacy_fields_redacted: true,
    address_saved: false,
  };
}

function mockOrderLogisticsTrace(order = {}) {
  const trackingNumber = order.trackingNumber || order.tracking_number || order.trackingNo || '';
  const deliveryCompany = order.deliveryCompany || order.delivery_company || order.logisticsCompany || '';
  return {
    status: trackingNumber ? 'local_tracking_trace' : 'tracking_number_missing',
    order_id: order.id,
    store_id: order.storeId || order.store_id,
    platform: order.rawPlatform || order.platform || 'naver',
    order_no: order.orderNo || order.external_order_id || '',
    product_order_no: order.productOrderNo || order.external_product_order_id || '',
    delivery_company: deliveryCompany,
    tracking_number: trackingNumber,
    tracking_source: 'mock_order_detail',
    realtime_tracking_open: false,
    message: trackingNumber
      ? '实时快递轨迹暂未接入；当前显示本地订单同步、物流单号导入和发货状态记录。'
      : '该订单本地还没有快递单号，无法查询物流轨迹。',
    events: [
      {
        time: order.createdAt || order.ordered_at || '',
        label: '订单已创建',
        description: '订单已保存到本地 ERP。',
        source: 'orders',
      },
      trackingNumber ? {
        time: order.updatedAt || order.lastSyncedAt || '',
        label: '物流单号已记录',
        description: `${deliveryCompany || '快递公司未记录'} / ${trackingNumber}`,
        source: 'local_tracking_trace',
      } : null,
    ].filter(Boolean),
  };
}

function mockSingleNaverOrderDetailRefresh(order = {}) {
  return {
    status: 'success',
    storeId: order.storeId || order.store_id,
    platform: 'naver',
    resource: 'orders',
    orderId: order.id,
    message: 'mock 模式已模拟读取订单详情；不会回填平台。',
    updatedCount: 0,
    noChangeCount: 1,
    platformWrite: false,
    fieldAvailability: {
      receiverPhone: Boolean(order.receiverPhone || order.receiver_phone),
      deliveryCompany: Boolean(order.deliveryCompany || order.delivery_company || order.logisticsCompany),
      trackingNumber: Boolean(order.trackingNumber || order.tracking_number || order.trackingNo),
    },
    order,
  };
}

function mockStoreOverview() {
  const stores = [
    {
      id: 8,
      store_id: 8,
      store_name: 'pxg球包店',
      platform: 'naver',
      owner_name: '运营',
      store_status: 'active',
      connection_status: '商品和订单可读',
      connection_tone: 'warning',
      connection_reason: 'Naver 商品和订单可读取并写入本地 ERP；平台写入仍关闭。',
      last_sync_at: '2026-07-08T09:10:00+09:00',
      latest_manual_sync_status: 'partial_success',
      resources: {
        products: { status: 'success', error_code: '', message: 'Naver商品本地同步完成', data_status: 'confirmed' },
        orders: { status: 'success', error_code: '', message: 'Naver订单本地同步完成', data_status: 'confirmed' },
        customer_inquiries: { status: 'not_open', error_code: 'not_open', message: '客服消息暂未接入真实平台', data_status: 'not_open' },
      },
      metrics: {
        today_orders: overviewMetric(3, 'confirmed'),
        pending_shipments: overviewMetric(1, 'confirmed'),
        abnormal_orders: overviewMetric(0, 'confirmed'),
        inventory_alerts: overviewMetric(4, 'confirmed'),
      },
    },
    {
      id: 9,
      store_id: 9,
      store_name: '韩国本土运动鞋店',
      platform: 'coupang',
      owner_name: '运营',
      store_status: 'active',
      connection_status: '最近一次同步：IP 白名单未通过',
      connection_tone: 'danger',
      connection_reason: '最近一次同步无法确认：IP 白名单未通过',
      last_sync_at: '2026-07-08T09:05:00+09:00',
      latest_manual_sync_status: 'failed',
      resources: {
        products: { status: 'failed', error_code: 'ip_not_allowed', message: '最近一次同步无法确认：IP 白名单未通过', data_status: 'unknown' },
        orders: { status: 'failed', error_code: 'ip_not_allowed', message: '最近一次同步无法确认：IP 白名单未通过', data_status: 'unknown' },
        customer_inquiries: { status: 'not_open', error_code: 'not_open', message: '客服消息暂未接入真实平台', data_status: 'not_open' },
      },
      metrics: {
        today_orders: overviewMetric(null, 'unknown', '最近一次同步无法确认：IP 白名单未通过'),
        pending_shipments: overviewMetric(null, 'unknown', '最近一次同步无法确认：IP 白名单未通过'),
        abnormal_orders: overviewMetric(null, 'unknown', '最近一次同步无法确认：IP 白名单未通过'),
        inventory_alerts: overviewMetric(null, 'unknown', '最近一次同步无法确认：IP 白名单未通过'),
      },
    },
    {
      id: 10,
      store_id: 10,
      store_name: 'Naver 日常运营店',
      platform: 'naver',
      owner_name: '运营',
      store_status: 'active',
      connection_status: '商品和订单可读',
      connection_tone: 'success',
      connection_reason: '商品和订单已可读取并写入本地 ERP。',
      last_sync_at: '2026-07-08T09:00:00+09:00',
      latest_manual_sync_status: 'success',
      resources: {
        products: { status: 'success', error_code: '', message: '本地同步完成', data_status: 'confirmed' },
        orders: { status: 'success', error_code: '', message: '本地同步完成', data_status: 'confirmed' },
        customer_inquiries: { status: 'not_open', error_code: 'not_open', message: '客服消息暂未接入真实平台', data_status: 'not_open' },
      },
      metrics: {
        today_orders: overviewMetric(12, 'confirmed'),
        pending_shipments: overviewMetric(5, 'confirmed'),
        abnormal_orders: overviewMetric(1, 'confirmed'),
        inventory_alerts: overviewMetric(2, 'confirmed'),
      },
    },
  ];
  return {
    status: 'store_overview_ready',
    data_policy: '无法确认真实平台数据时显示 ?，避免把未知误判为 0。',
    business_timezone: 'Asia/Seoul',
    business_date: '2026-07-08',
    stores,
    summary: {
      store_count: stores.length,
      connected_store_count: 1,
      attention_store_count: 2,
      ip_blocked_store_count: 1,
      orders_unknown_store_count: 2,
      inventory_unknown_store_count: 1,
      today_order_count: 12,
      pending_shipment_count: 5,
      abnormal_order_count: 1,
      inventory_alert_count: 6,
    },
  };
}

const NAVER_ORDER_PREVIEW_WINDOWS = {
  '24h': { key: '24h', label: '最近 24 小时', hours: 24 },
  '3d': { key: '3d', label: '最近 3 天', hours: 72 },
  '7d': { key: '7d', label: '最近 7 天', hours: 168 },
};

function getNaverOrderPreviewWindow(value = '24h') {
  return NAVER_ORDER_PREVIEW_WINDOWS[value] || NAVER_ORDER_PREVIEW_WINDOWS['24h'];
}

function naverOrderPreviewDateTime(hoursOffset = 0) {
  const timestamp = Date.now() + Number(hoursOffset || 0) * 60 * 60 * 1000;
  const kst = new Date(timestamp + 9 * 60 * 60 * 1000);
  return `${kst.toISOString().slice(0, 19)}+09:00`;
}

function withNaverOrderPreviewWindowMetadata(result, windowConfig, startDateTime, endDateTime) {
  return {
    ...result,
    previewWindow: windowConfig.key,
    previewWindowLabel: windowConfig.label,
    windowHours: windowConfig.hours,
    startDateTime,
    endDateTime,
  };
}

async function mockNaverOrderCompletePreview(payload = {}) {
  const windowConfig = getNaverOrderPreviewWindow(payload.previewWindow || payload.windowKey);
  const startDateTime = payload.startDateTime || naverOrderPreviewDateTime(-windowConfig.hours);
  const endDateTime = payload.endDateTime || naverOrderPreviewDateTime(0);
  const result = await mockApi.getOrders({ storeId: payload.storeId, platform: 'naver', page: 1, pageSize: 1 });
  const order = (result.data || result.items || [])[0] || {};
  return withNaverOrderPreviewWindowMetadata(adapters.naverOrderCompletePreview({
    store_id: payload.storeId,
    credential_id: payload.credentialId || 7,
    platform: 'naver',
    preview_status: order.id ? 'success' : 'success_empty',
    business_message: order.id
      ? `mock 模式展示 ${windowConfig.label} Naver 订单完整字段预览，不请求平台。`
      : `mock 模式${windowConfig.label}没有可展示的 Naver 订单。`,
    field_observation: {
      feed_called: false,
      detail_called: Boolean(order.id),
      detail_http_status: order.id ? 200 : null,
    },
    complete_field_preview: {
      requested: true,
      preview_only: true,
      available: Boolean(order.id),
      complete_fields: order.id ? {
        external_order_id: order.external_order_id || order.orderNo,
        external_product_order_id: order.external_product_order_id || order.productOrderNo,
        platform_product_id: order.platform_product_id || order.platformProductId,
        product_name: order.product_name || order.product,
        option_name: order.option_name || order.optionName,
        quantity: order.quantity,
        order_amount: order.order_amount || order.amount,
        currency: order.currency || 'KRW',
        order_status: order.order_status,
        order_status_label_zh: order.status,
        payment_status: order.payment_status,
        delivery_status: order.delivery_status,
        delivery_status_label_zh: order.delivery_status_label_zh,
        claim_status: order.claim_status,
        claim_status_label_zh: order.claim_status_label_zh,
        buyer_name: order.buyer_name || order.customer,
        buyer_phone: order.buyer_phone || order.buyerPhone || order.phone,
        receiver_name: order.receiver_name || order.receiverName,
        receiver_phone: order.receiver_phone || order.receiverPhone,
        receiver_address: order.receiver_address || order.receiverAddress,
        zip_code: order.zip_code || order.zipCode,
        ordered_at: order.ordered_at || order.createdAt,
        paid_at: order.paid_at,
        raw_response_saved: false,
        mapping_version: order.raw_data?.mapping_version || 'mock_naver_order_complete_field_preview_v1',
      } : {},
      field_availability: {
        external_order_id: Boolean(order.external_order_id || order.orderNo),
        external_product_order_id: Boolean(order.external_product_order_id || order.productOrderNo),
        platform_product_id: Boolean(order.platform_product_id || order.platformProductId),
        buyer_name: Boolean(order.buyer_name || order.customer),
        buyer_phone: Boolean(order.buyer_phone || order.buyerPhone || order.phone),
        receiver_name: Boolean(order.receiver_name || order.receiverName),
        receiver_phone: Boolean(order.receiver_phone || order.receiverPhone),
        receiver_address: Boolean(order.receiver_address || order.receiverAddress),
        zip_code: Boolean(order.zip_code || order.zipCode),
      },
      save_plan: {
        codex1_schema_write_enabled: false,
        requires_user_approval: true,
        requires_db_backup: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        orders_written: false,
        sync_log_written: false,
        tested_success_written: false,
        raw_response_saved: false,
      },
    },
  }), windowConfig, startDateTime, endDateTime);
}

function withMockFinancialSummary(summary = {}) {
  if (summary.financialSummary) return summary;
  return {
    ...summary,
    financialSummary: {
      available: true,
      orderSalesSummary: {
        scope: 'order_amount_from_orders',
        totalOrders: Number(summary.todayOrderCount || summary.scopeOrderCount || 0),
        totalOrderSalesAmount: Number(summary.todaySalesAmount || summary.scopeSalesAmount || 0),
        currency: summary.currency || 'KRW',
        latestOrderedAt: null,
      },
      platformSalesDetailSummary: {
        scope: 'platform_sales_details',
        salesDetailRows: 0,
        totalSaleAmount: 0,
        totalSettlementTargetAmount: 0,
        totalSettlementAmount: 0,
        latestRecognitionDate: null,
        currency: 'KRW',
        dataStatus: 'local_persisted_rows',
      },
      settlementSummary: {
        scope: 'platform_settlement_details',
        settlementRows: 0,
        totalSettlementAmount: 0,
        totalFinalAmount: 0,
        totalServiceFee: 0,
        latestRevenueRecognitionYearMonth: null,
        latestSettlementDate: null,
        currency: 'KRW',
        dataStatus: 'local_persisted_rows',
      },
      sourceBoundaries: {
        orderSalesScope: 'Mock mode keeps order amount scope separate from sales confirmation and settlement scope.',
        platformSalesDetailScope: 'Mock mode does not persist real Coupang sales detail rows.',
        settlementScope: 'Mock mode does not persist real Coupang settlement rows.',
        settlementMonthGranularityNotice: 'Settlement uses revenueRecognitionYearMonth and is not day-precise.',
        finalAmountNotice: 'finalAmount is not profit and is not withdrawable balance.',
        zeroDataNotice: 'Zero rows only mean local persisted data is currently empty.',
      },
    },
  };
}

const mockApiCapabilities = [
  { id: 9101, platform: 'Naver', rawPlatform: 'naver', capabilityKey: 'naver.token_auth', capabilityName: '平台授权检测', apiCategory: 'auth', testStatus: 'tested_success', testMode: 'real_readonly' },
  { id: 9102, platform: 'Naver', rawPlatform: 'naver', capabilityKey: 'naver.seller_account_read', capabilityName: '卖家账号信息读取', apiCategory: 'seller', testStatus: 'tested_success', testMode: 'real_readonly' },
  { id: 9103, platform: 'Naver', rawPlatform: 'naver', capabilityKey: 'naver.seller_channels_read', capabilityName: '店铺频道信息读取', apiCategory: 'seller', testStatus: 'tested_success', testMode: 'real_readonly' },
  { id: 9104, platform: 'Naver', rawPlatform: 'naver', capabilityKey: 'naver.product_read', capabilityName: '商品读取', apiCategory: 'products', testStatus: 'not_tested', testMode: 'docs_only' },
  { id: 9105, platform: 'Naver', rawPlatform: 'naver', capabilityKey: 'naver.order_read', capabilityName: '订单读取', apiCategory: 'orders', testStatus: 'not_tested', testMode: 'docs_only' },
  { id: 9201, platform: 'Coupang', rawPlatform: 'coupang', capabilityKey: 'coupang.product_read', capabilityName: '商品读取/同步', apiCategory: 'products', testStatus: 'tested_success', testMode: 'real_readonly' },
  { id: 9202, platform: 'Coupang', rawPlatform: 'coupang', capabilityKey: 'coupang.order_read', capabilityName: '订单读取/同步', apiCategory: 'orders', testStatus: 'tested_success', testMode: 'real_readonly' },
  { id: 9203, platform: 'Coupang', rawPlatform: 'coupang', capabilityKey: 'coupang.sales_read', capabilityName: '销售明细', apiCategory: 'sales', testStatus: 'tested_success', testMode: 'real_readonly' },
  { id: 9204, platform: 'Coupang', rawPlatform: 'coupang', capabilityKey: 'coupang.settlement_read', capabilityName: '结算明细', apiCategory: 'settlements', testStatus: 'tested_success', testMode: 'real_readonly' },
];

function mockApiCapabilityResults(storeId) {
  if (Number(storeId) === 5) {
    return [
      {
        id: 9311,
        storeId,
        capabilityId: 9101,
        credentialId: 7,
        testMode: 'real_readonly',
        testStatus: 'tested_success',
        httpStatus: 200,
        responseFieldsObserved: 'token_test=success; capability_scope=token_auth; path_kind=store_bound',
        testedAt: '2026-07-02T07:10:00+00:00',
      },
      {
        id: 9312,
        storeId,
        capabilityId: 9102,
        credentialId: 7,
        testMode: 'real_readonly',
        testStatus: 'tested_success',
        httpStatus: 200,
        responseFieldsObserved: 'seller_or_account_test=success; capability_scope=seller_account; path_kind=store_bound',
        testedAt: '2026-07-02T07:11:00+00:00',
      },
      {
        id: 9313,
        storeId,
        capabilityId: 9103,
        credentialId: 7,
        testMode: 'real_readonly',
        testStatus: 'tested_success',
        httpStatus: 200,
        responseFieldsObserved: 'seller_or_account_test=success; capability_scope=seller_channels; path_kind=store_bound; channel_no_source=seller_channels; channel_no_configured=True; channel_no_persisted=True',
        testedAt: '2026-07-02T07:12:00+00:00',
      },
      {
        id: 9314,
        storeId,
        capabilityId: 9104,
        credentialId: 7,
        testMode: 'real_readonly',
        testStatus: 'tested_failed',
        httpStatus: 403,
        errorCode: 'product_api_not_allowed',
        businessErrorHint: '请检查 Naver Commerce API Center 中商品 API 的使用权限。',
        safeKeywordFlags: { permission: true, forbidden: true, ip: false, allowed: false },
        capabilityScope: 'product_read',
        pathKind: 'store_bound',
        responseFieldsObserved: 'product_read_test=failed; capability_scope=product_read; path_kind=store_bound; http_status=403; error_code=product_api_not_allowed',
        testedAt: '2026-07-02T07:13:00+00:00',
      },
      {
        id: 9315,
        storeId,
        capabilityId: 9101,
        credentialId: 7,
        testMode: 'real_readonly',
        testStatus: 'tested_failed',
        httpStatus: 403,
        errorCode: 'ip_not_allowed',
        businessErrorHint: '请在 Naver Commerce API Center 检查 API 使用 IP / 允许 IP 设置。',
        safeKeywordFlags: { ip: true, allowed: true, gateway_ip: true },
        capabilityScope: 'token_auth',
        pathKind: 'store_bound',
        responseFieldsObserved: 'token_test=failed; capability_scope=token_auth; path_kind=store_bound; http_status=403; error_code=ip_not_allowed',
        testedAt: '2026-06-30T08:20:00+00:00',
      },
      {
        id: 9316,
        storeId,
        capabilityId: 9101,
        credentialId: 7,
        testMode: 'real_readonly',
        testStatus: 'tested_failed',
        httpStatus: 403,
        errorCode: 'credential_invalid',
        businessErrorHint: '请检查 Client ID / Client Secret 是否正确，或是否被重新生成。',
        safeKeywordFlags: { invalid_client: true, client_secret: true },
        capabilityScope: 'token_auth',
        pathKind: 'store_bound',
        responseFieldsObserved: 'token_test=failed; capability_scope=token_auth; path_kind=store_bound; http_status=403; error_code=credential_invalid',
        testedAt: '2026-06-29T08:20:00+00:00',
      },
      {
        id: 9317,
        storeId,
        capabilityId: 9101,
        credentialId: 7,
        testMode: 'real_readonly',
        testStatus: 'tested_failed',
        httpStatus: 403,
        errorCode: 'token_auth_failed',
        businessErrorHint: '请检查连接资料、平台权限或 Naver API 设置。',
        safeKeywordFlags: { forbidden: true },
        capabilityScope: 'token_auth',
        pathKind: 'store_bound',
        responseFieldsObserved: 'token_test=failed; capability_scope=token_auth; path_kind=store_bound; http_status=403; error_code=token_auth_failed',
        testedAt: '2026-06-28T08:20:00+00:00',
      },
    ];
  }

  const testedAt = '2026-07-01T13:35:04+00:00';
  return [
    { id: 9301, storeId, capabilityId: 9101, credentialId: 7, testMode: 'real_readonly', testStatus: 'tested_success', httpStatus: 200, responseFieldsObserved: 'token_test=success; capability_scope=token_auth; path_kind=store_bound', testedAt },
    { id: 9302, storeId, capabilityId: 9102, credentialId: 7, testMode: 'real_readonly', testStatus: 'tested_success', httpStatus: 200, responseFieldsObserved: 'seller_or_account_test=success; capability_scope=seller_account; path_kind=store_bound', testedAt },
    { id: 9303, storeId, capabilityId: 9103, credentialId: 7, testMode: 'real_readonly', testStatus: 'tested_success', httpStatus: 200, responseFieldsObserved: 'seller_or_account_test=success; capability_scope=seller_channels; path_kind=store_bound; channel_no_source=seller_channels; channel_no_configured=True; channel_no_persisted=True', testedAt },
  ];
}

function mockApiCredentialReadiness(params = {}) {
  const targetStoreId = params?.storeId || params?.store_id || 8;
  return {
    semantic_notice: 'Mock mode shows seller-facing example states only.',
    real_api_test_enabled: false,
    real_api_write_enabled: false,
    platforms: [
      { platform: 'naver', credential_status: 'configured', readiness_status: 'configured', fields: { client_id: 'configured', secret_key: 'configured', api_base: 'configured' } },
      { platform: 'coupang', credential_status: 'configured', readiness_status: 'configured', fields: { vendor_id: 'configured', access_key: 'configured', secret_key: 'configured' } },
    ],
    store_bound_readiness: {
      store_id: targetStoreId,
      platform: 'naver',
      credential_id: 7,
      credential_name: Number(targetStoreId) === 5 ? 'Mock Naver credential - permission review' : 'Mock Naver credential',
      configured: true,
      client_id_configured: true,
      secret_key_configured: true,
      secret_key_decryptable: true,
      api_base: 'https://api.commerce.naver.com/external',
      channel_no_configured: true,
      access_token_status: 'missing',
      refresh_token_configured: false,
      token_expires_at: null,
      auth_status: Number(targetStoreId) === 5 ? 'needs_test' : 'configured',
      missing_fields: [],
      warnings: Number(targetStoreId) === 5
        ? ['access_token_missing', 'product_api_permission_check_required']
        : ['access_token_missing'],
    },
  };
}

async function getMockDashboardData() {
  const [summary, risks, todos, activities] = await Promise.all([
    mockApi.getDashboardSummary(),
    mockApi.getDashboardRisks(),
    mockApi.getDashboardTodos(),
    mockApi.getDashboardActivities(),
  ]);
  return { summary: withMockFinancialSummary(summary), risks, todos, activities };
}

async function getBackendDashboardData(params) {
  const adapted = adapters.dashboardSummary(await backendApi.getDashboardSummary(params));
  return {
    summary: adapted.summary,
    risks: adapted.risks,
    todos: adapted.todos,
    activities: adapted.activities,
  };
}

const mockRolePermissions = {
  owner: {
    store_scope: 'all',
    permissions: ['*'],
    sensitive_approval_actions: ['*'],
  },
  admin: {
    store_scope: 'assigned',
    permissions: [
      'dashboard.read',
      'products.read',
      'products.preview',
      'products.batch_sync_write',
      'orders.read',
      'orders.preview',
      'orders.local_write',
      'orders.batch_sync_write',
      'orders.refresh_batch_write',
      'audit.read',
      'backup.read',
      'backup.create',
      'store_membership.assign',
    ],
    sensitive_approval_actions: [
      'products.batch_sync_write',
      'orders.batch_sync_write',
      'orders.local_write',
      'orders.refresh_batch_write',
      'backup.create',
      'store_membership.assign',
    ],
  },
  operator: {
    store_scope: 'assigned',
    permissions: ['dashboard.read', 'products.read', 'products.preview', 'orders.read', 'orders.preview', 'audit.read', 'backup.read'],
    sensitive_approval_actions: [],
  },
  auditor: {
    store_scope: 'assigned',
    permissions: ['dashboard.read', 'orders.read', 'products.read', 'audit.read', 'backup.read'],
    sensitive_approval_actions: [],
  },
  viewer: {
    store_scope: 'assigned',
    permissions: ['dashboard.read', 'orders.read', 'products.read'],
    sensitive_approval_actions: [],
  },
};

function permissionSafetyFlags(extra = {}) {
  return {
    mockPermissionApi: true,
    publicEndpointEnabled: Boolean(extra.public_endpoint_enabled ?? extra.publicEndpointEnabled ?? true),
    realAuthSessionCreated: false,
    realDatabaseWritten: false,
    ordersWritten: false,
    productsWritten: false,
    syncLogWritten: false,
    capabilityTestedSuccessWritten: false,
    rawResponseSaved: false,
    secretsSaved: false,
    privacyFieldsRedacted: true,
    formalSyncOpen: false,
    platformWritesEnabled: false,
  };
}

function normalizeMockRole(actorContext = {}) {
  const role = String(actorContext.role || '').trim().toLowerCase();
  return mockRolePermissions[role] ? role : '';
}

function normalizeStoreIds(actorContext = {}) {
  if (actorContext.store_ids === 'all' || actorContext.storeIds === 'all') return [-1];
  const ids = actorContext.store_ids || actorContext.storeIds || [];
  return Array.isArray(ids)
    ? ids.map((value) => Number(value)).filter((value) => Number.isInteger(value) && value > 0)
    : [];
}

function mockPermissionGate({ actorContext = {}, storeId, operationKey }) {
  const role = normalizeMockRole(actorContext);
  const requestedStoreId = Number(storeId);
  const roleDefinition = mockRolePermissions[role] || {};
  const assignedStoreIds = normalizeStoreIds(actorContext);
  const storeScopeVerified = roleDefinition.store_scope === 'all'
    || assignedStoreIds.includes(-1)
    || assignedStoreIds.includes(requestedStoreId);
  const permissions = roleDefinition.permissions || [];
  const operation = String(operationKey || '').trim().toLowerCase();
  const permissionVerified = storeScopeVerified && (permissions.includes('*') || permissions.includes(operation));
  let status = 'blocked';
  let skipReason = null;
  let businessMessage = '当前权限检查未通过，请检查角色、店铺范围或操作类型。';

  if (!role) {
    skipReason = 'role_not_allowed';
  } else if (!storeScopeVerified) {
    skipReason = 'store_scope_mismatch';
    businessMessage = '当前角色未被分配到该店铺，不能访问该店铺数据。';
  } else if (!permissionVerified) {
    skipReason = 'permission_denied';
    businessMessage = '当前角色没有该操作权限，请联系管理员处理。';
  } else {
    status = 'access_allowed';
    businessMessage = '当前角色可查看该店铺的对应功能。';
  }

  return {
    phase: 'ERP-Auth-1F',
    status,
    skipReason,
    actorRole: role || null,
    requestedStoreId,
    operationKey: operation,
    storeScopeVerified,
    permissionVerified,
    sensitiveAction: ['orders.local_write', 'orders.refresh_batch_write', 'backup.create'].includes(operation),
    manualApproval: false,
    approvalRoleVerified: false,
    approvalStatus: 'blocked',
    businessMessage,
    ...permissionSafetyFlags(),
  };
}

function mockSensitiveActionGate({ actorContext = {}, storeId, actionKey, manualApproval = false }) {
  const access = mockPermissionGate({ actorContext, storeId, operationKey: actionKey });
  const action = String(actionKey || '').trim().toLowerCase();
  const roleDefinition = mockRolePermissions[access.actorRole] || {};
  const approvalActions = roleDefinition.sensitive_approval_actions || [];
  let result = {
    ...access,
    actionKey: action,
    manualApproval: Boolean(manualApproval),
    sensitiveActionApprovalGate: true,
  };

  if (access.status !== 'access_allowed') {
    return {
      ...result,
      approvalStatus: 'blocked',
      businessMessage: '当前角色不能批准该敏感操作，请由管理员或负责人审批。',
    };
  }
  if (!manualApproval) {
    return {
      ...result,
      status: 'approval_blocked',
      approvalStatus: 'blocked',
      skipReason: 'manual_approval_required',
      businessMessage: '该操作属于敏感操作，需要管理员人工批准后才能进入后续执行阶段。',
    };
  }
  if (!approvalActions.includes('*') && !approvalActions.includes(action)) {
    return {
      ...result,
      status: 'approval_blocked',
      approvalStatus: 'blocked',
      skipReason: 'approval_role_required',
      businessMessage: '当前角色不能批准该敏感操作，请由管理员或负责人审批。',
    };
  }
  return {
    ...result,
    status: 'approval_allowed_mock',
    approvalStatus: 'approved_in_mock_gate',
    approvalRoleVerified: true,
    businessMessage: '管理员审批条件在 mock gate 中通过；真实写入仍需要单独阶段执行。',
  };
}

function mockStoreMembershipReadonlyGate(payload = {}) {
  const access = mockSensitiveActionGate({
    actorContext: payload.actor_context || payload.actorContext || {},
    storeId: payload.target_store_id ?? payload.targetStoreId,
    actionKey: 'store_membership.assign',
    manualApproval: payload.manual_approval ?? payload.manualApproval,
  });
  const targetUserHash = payload.target_user_key_hash || payload.targetUserKeyHash || '';
  const targetRole = String(payload.target_role || payload.targetRole || '').trim().toLowerCase();
  const targetStoreId = Number(payload.target_store_id ?? payload.targetStoreId ?? 0);
  const validUserHash = /^user-hash-[a-f0-9]{8,64}$/.test(targetUserHash);
  const roleExists = ['owner', 'admin', 'operator', 'auditor', 'viewer'].includes(targetRole);
  const duplicate = targetUserHash === 'user-hash-aaaaaaaaaaaaaaaa';

  let status = 'blocked';
  let skipReason = null;
  let businessMessage = '店铺成员分配只读检查未通过，请管理员查看折叠详情。';
  if (!validUserHash) {
    skipReason = 'target_user_hash_invalid';
  } else if (!targetStoreId) {
    skipReason = 'target_store_invalid';
  } else if (!roleExists) {
    skipReason = 'target_role_not_allowed';
  } else if (duplicate) {
    skipReason = 'duplicate_active_membership';
    businessMessage = '该用户已经拥有相同店铺角色，不需要重复分配。';
  } else if (access.status !== 'approval_allowed_mock') {
    skipReason = access.skipReason || 'membership_assignment_runtime_gate_blocked';
  } else {
    status = 'membership_assignment_runtime_mock_ready';
    businessMessage = '店铺成员分配只读检查已通过。当前不会创建用户或店铺成员关系。';
  }

  return {
    phase: 'ERP-Multistore-1G',
    store_membership_readonly_api_mock_gate: true,
    readonly_api_mock_gate: true,
    public_endpoint_enabled: true,
    status,
    skip_reason: skipReason,
    target_user_key_hash: targetUserHash,
    target_store_id: targetStoreId,
    target_role: roleExists ? targetRole : null,
    manual_approval: Boolean(payload.manual_approval ?? payload.manualApproval),
    assignment_reason_present: Boolean(payload.assignment_reason || payload.assignmentReason),
    target_user_exists: validUserHash && !duplicate,
    target_role_exists: roleExists,
    existing_active_membership_count: duplicate ? 1 : 0,
    duplicate_active_membership: duplicate,
    membership_would_create: status === 'membership_assignment_runtime_mock_ready',
    membership_written: false,
    business_message: businessMessage,
    ...permissionSafetyFlags(),
  };
}

function mockUserInvitationReadonlyGate(payload = {}) {
  const actorContext = payload.actor_context || payload.actorContext || {};
  const targetStoreIds = Array.isArray(payload.target_store_ids || payload.targetStoreIds)
    ? (payload.target_store_ids || payload.targetStoreIds).map((value) => Number(value)).filter((value) => Number.isInteger(value) && value > 0)
    : [];
  const firstStoreId = targetStoreIds[0] || 0;
  const access = mockSensitiveActionGate({
    actorContext,
    storeId: firstStoreId,
    actionKey: 'store_membership.assign',
    manualApproval: payload.manual_approval ?? payload.manualApproval,
  });
  const targetUserHash = payload.target_user_key_hash || payload.targetUserKeyHash || '';
  const loginHash = payload.login_identifier_hash || payload.loginIdentifierHash || '';
  const maskedLogin = payload.login_identifier_masked || payload.loginIdentifierMasked || '';
  const existingHashes = Array.isArray(payload.existing_user_hashes || payload.existingUserHashes)
    ? (payload.existing_user_hashes || payload.existingUserHashes)
    : [];
  const targetRole = String(payload.target_role || payload.targetRole || '').trim().toLowerCase();
  const validUserHash = /^user-hash-[a-f0-9]{8,64}$/.test(targetUserHash);
  const validLoginHash = /^login-hash-[a-f0-9]{8,64}$/.test(loginHash);
  const loginMasked = Boolean(maskedLogin && (!maskedLogin.includes('@') || maskedLogin.includes('*')) && !/\b01[016789]-?\d{3,4}-?\d{4}\b/.test(maskedLogin));
  const roleExists = ['owner', 'admin', 'operator', 'auditor', 'viewer'].includes(targetRole);
  const duplicate = existingHashes.includes(targetUserHash);
  const backupPlanned = Boolean(payload.backup_evidence_planned ?? payload.backupEvidencePlanned);
  const auditPlanned = Boolean(payload.audit_evidence_planned ?? payload.auditEvidencePlanned);
  const membershipPlanReady = Boolean(payload.membership_assignment_plan_ready ?? payload.membershipAssignmentPlanReady);

  let status = 'blocked';
  let skipReason = null;
  let businessMessage = '用户邀请只读检查未通过，请管理员查看折叠详情。';
  if (!validUserHash) {
    skipReason = 'target_user_hash_invalid';
  } else if (!validLoginHash) {
    skipReason = 'login_identifier_hash_invalid';
  } else if (!loginMasked) {
    skipReason = 'login_identifier_must_be_masked';
    businessMessage = '登录标识必须脱敏后才能展示。';
  } else if (!targetStoreIds.length) {
    skipReason = 'target_store_ids_required';
  } else if (!roleExists) {
    skipReason = 'target_role_not_allowed';
  } else if (!payload.invitation_reason && !payload.invitationReason) {
    skipReason = 'invitation_reason_required';
  } else if (!backupPlanned) {
    skipReason = 'backup_evidence_plan_required';
  } else if (!auditPlanned) {
    skipReason = 'audit_evidence_plan_required';
  } else if (!membershipPlanReady) {
    skipReason = 'membership_assignment_plan_required';
  } else if (duplicate) {
    skipReason = 'target_user_already_exists';
    businessMessage = '目标用户已存在，当前不会重复创建邀请。';
  } else if (access.status !== 'approval_allowed_mock') {
    skipReason = access.skipReason || 'user_invitation_approval_blocked';
    businessMessage = access.businessMessage || businessMessage;
  } else {
    status = 'user_invitation_mock_ready';
    businessMessage = '用户邀请只读检查已通过。当前不会创建用户、发送邀请或分配店铺成员。';
  }

  return {
    phase: 'ERP-Multistore-1P',
    user_invitation_readonly_api_mock_gate: true,
    readonly_api_mock_gate: true,
    public_endpoint_enabled: false,
    status,
    skip_reason: skipReason,
    target_user_key_hash: validUserHash ? targetUserHash : null,
    login_identifier_hash: validLoginHash ? loginHash : null,
    login_identifier_masked: loginMasked ? maskedLogin : null,
    target_store_ids: targetStoreIds,
    target_role: roleExists ? targetRole : null,
    manual_approval: Boolean(payload.manual_approval ?? payload.manualApproval),
    approval_results: access.status === 'approval_allowed_mock' ? [{
      store_id: firstStoreId,
      status: access.status,
      skip_reason: access.skipReason || null,
      actor_role: access.actorRole || null,
      actor_id_hash: access.actorIdHash || null,
      store_scope_verified: access.storeScopeVerified,
      permission_verified: access.permissionVerified,
      approval_role_verified: access.approvalRoleVerified,
    }] : [],
    invitation_reason_present: Boolean(payload.invitation_reason || payload.invitationReason),
    backup_evidence_planned: backupPlanned,
    audit_evidence_planned: auditPlanned,
    membership_assignment_plan_ready: membershipPlanReady,
    invitation_would_create_user: status === 'user_invitation_mock_ready',
    invitation_would_send: status === 'user_invitation_mock_ready',
    invitation_sent: false,
    users_written: false,
    membership_written: false,
    role_assignment_written: false,
    operation_audit_rows_planned: true,
    operation_audit_rows_written: false,
    business_message: businessMessage,
    ...permissionSafetyFlags(),
  };
}

function mockUserInvitationApprovalChecklistReadonlyGate(payload = {}) {
  const approvalChecklist = payload.approval_checklist || payload.approvalChecklist || {};
  const readonlyApiContext = payload.readonly_api_context || payload.readonlyApiContext || {};
  const requiredChecklistFlags = [
    'backup_evidence_ready',
    'audit_evidence_plan_ready',
    'membership_assignment_plan_ready',
    'invite_expiry_configured',
    'one_time_invite_configured',
    'post_create_readback_required',
    'disable_user_rollback_ready',
    'privacy_display_verified',
    'formal_login_boundary_acknowledged',
  ];
  const requiredApiFlags = [
    'readonly_api_contract_planned',
    'business_wording_required',
    'technical_details_folded',
    'send_invitation_button_excluded',
    'write_endpoint_excluded',
    'masked_identifier_required',
    'route_requires_separate_implementation',
    'real_invitation_remains_closed',
  ];
  const baseGate = mockUserInvitationReadonlyGate({
    ...payload,
    backup_evidence_planned: true,
    audit_evidence_planned: true,
    membership_assignment_plan_ready: true,
  });
  const missingChecklistFlags = requiredChecklistFlags.filter((flag) => approvalChecklist[flag] !== true);
  const missingApiFlags = requiredApiFlags.filter((flag) => readonlyApiContext[flag] !== true);
  let status = 'blocked';
  let skipReason = baseGate.skip_reason || null;
  let businessMessage = '用户邀请审批清单只读检查暂未通过，请管理员补齐审批材料。';
  if (baseGate.status !== 'user_invitation_mock_ready') {
    skipReason = baseGate.skip_reason || 'user_invitation_base_gate_blocked';
    businessMessage = baseGate.business_message || businessMessage;
  } else if (missingChecklistFlags.length) {
    skipReason = 'approval_checklist_incomplete';
  } else if (approvalChecklist.invitation_sent || approvalChecklist.users_written || approvalChecklist.membership_written) {
    skipReason = 'real_invitation_not_allowed_in_readonly_gate';
  } else if (missingApiFlags.length) {
    skipReason = 'readonly_api_context_incomplete';
  } else if (readonlyApiContext.public_endpoint_enabled || readonlyApiContext.backend_route_implemented) {
    skipReason = 'readonly_api_context_should_describe_pre_route_boundary';
  } else if (readonlyApiContext.invitation_sent || readonlyApiContext.users_written) {
    skipReason = 'real_invitation_not_allowed_in_readonly_gate';
  } else {
    status = 'user_invitation_approval_checklist_readonly_api_ready';
    businessMessage = '用户邀请审批清单只读检查已通过。当前只展示审批材料，不会创建用户、发送邀请或分配店铺权限。';
  }
  return {
    ...baseGate,
    phase: 'ERP-Multistore-2L',
    status,
    skip_reason: skipReason,
    user_invitation_approval_checklist_readonly_api_local: true,
    checklist_ready: status === 'user_invitation_approval_checklist_readonly_api_ready',
    required_checklist_flags: requiredChecklistFlags,
    missing_checklist_flags: missingChecklistFlags,
    required_api_flags: requiredApiFlags,
    missing_api_flags: missingApiFlags,
    route_path: '/api/v1/permissions/user-invitation/approval-checklist/readonly-check',
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    backup_evidence_ready: approvalChecklist.backup_evidence_ready === true,
    audit_evidence_plan_ready: approvalChecklist.audit_evidence_plan_ready === true,
    invite_expiry_configured: approvalChecklist.invite_expiry_configured === true,
    one_time_invite_configured: approvalChecklist.one_time_invite_configured === true,
    post_create_readback_required: approvalChecklist.post_create_readback_required === true,
    disable_user_rollback_ready: approvalChecklist.disable_user_rollback_ready === true,
    privacy_display_verified: approvalChecklist.privacy_display_verified === true,
    formal_login_boundary_acknowledged: approvalChecklist.formal_login_boundary_acknowledged === true,
    invitation_would_create_user: false,
    invitation_would_send: false,
    invitation_sent: false,
    users_written: false,
    membership_written: false,
    role_assignment_written: false,
    operation_audit_rows_written: false,
    real_auth_session_created: false,
    real_database_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    platform_writes_enabled: false,
    business_message: businessMessage,
    next_action: '真实邀请仍必须另开审批和写入阶段，并重新确认备份、审计、回读和撤销证据。',
  };
}

function mockUserInvitationApprovalAuditLinkageReadonlyGate(payload = {}) {
  const invitationApproval = payload.invitation_approval || payload.invitationApproval || {};
  const auditLinkageContext = payload.audit_linkage_context || payload.auditLinkageContext || {};
  const readonlyApiContext = payload.readonly_api_context || payload.readonlyApiContext || {};
  const requiredLinkageFlags = [
    'invitation_decision_id_planned',
    'target_user_hash_planned',
    'masked_login_identifier_planned',
    'store_scope_planned',
    'target_role_planned',
    'approval_actor_hash_planned',
    'permission_evidence_reference_planned',
    'backup_evidence_reference_planned',
    'invitation_expiry_policy_reference_planned',
    'readback_plan_reference_planned',
    'rollback_plan_reference_planned',
    'audit_correlation_id_planned',
    'append_only_audit_rows_planned',
    'real_invitation_remains_closed',
  ];
  const requiredApiFlags = [
    'readonly_api_contract_planned',
    'business_wording_required',
    'technical_details_folded',
    'send_invitation_button_excluded',
    'write_endpoint_excluded',
    'masked_identifier_required',
    'audit_row_write_excluded',
    'route_requires_separate_implementation',
    'real_invitation_remains_closed',
  ];
  const hasSensitiveMarker = JSON.stringify(payload).toLowerCase().includes('authorization')
    || JSON.stringify(payload).toLowerCase().includes('rawresponse')
    || JSON.stringify(payload).toLowerCase().includes('client_secret')
    || JSON.stringify(payload).toLowerCase().includes('bearer ');
  const missingLinkageFlags = requiredLinkageFlags.filter((flag) => auditLinkageContext[flag] !== true);
  const missingApiFlags = requiredApiFlags.filter((flag) => readonlyApiContext[flag] !== true);
  const targetStoreIds = Array.isArray(invitationApproval.target_store_ids || invitationApproval.targetStoreIds)
    ? (invitationApproval.target_store_ids || invitationApproval.targetStoreIds)
    : [];
  const targetRole = invitationApproval.target_role || invitationApproval.targetRole || null;
  let status = 'blocked';
  let skipReason = null;
  let businessMessage = '邀请审批审计链路只读检查暂未通过，请管理员查看折叠详情。';

  if (hasSensitiveMarker) {
    skipReason = 'invitation_approval_audit_linkage_sensitive_material_blocked';
  } else if (![
    'user_invitation_approval_checklist_readonly_api_ready',
    'user_invitation_approval_checklist_readonly_route_mock_ready',
    'user_invitation_approval_checklist_readonly_api_mock_ready',
    'user_invitation_approval_checklist_mock_ready',
  ].includes(invitationApproval.status)) {
    skipReason = 'invitation_approval_not_ready';
  } else if (missingLinkageFlags.length) {
    skipReason = 'invitation_approval_audit_linkage_incomplete';
  } else if (missingApiFlags.length) {
    skipReason = 'readonly_api_context_incomplete';
  } else if (readonlyApiContext.public_endpoint_enabled || readonlyApiContext.backend_route_implemented) {
    skipReason = 'readonly_api_context_should_describe_pre_route_boundary';
  } else if (auditLinkageContext.invitation_sent || auditLinkageContext.users_written || auditLinkageContext.membership_written) {
    skipReason = 'real_invitation_not_allowed_in_linkage_mock_gate';
  } else if (auditLinkageContext.operation_audit_rows_written || readonlyApiContext.operation_audit_rows_written) {
    skipReason = 'audit_write_not_allowed_in_readonly_api_mock_gate';
  } else {
    status = 'user_invitation_approval_audit_linkage_readonly_api_ready';
    businessMessage = '邀请审批和审计证据链路已可只读复核。当前不会发送邀请、创建用户、分配店铺权限或写入审计记录。';
  }

  return {
    phase: 'ERP-Multistore-2T',
    status,
    skip_reason: skipReason,
    real_user_invitation_approval_audit_linkage_readonly_api_local: true,
    audit_linkage_ready: status === 'user_invitation_approval_audit_linkage_readonly_api_ready',
    required_linkage_flags: requiredLinkageFlags,
    missing_linkage_flags: missingLinkageFlags,
    required_api_flags: requiredApiFlags,
    missing_api_flags: missingApiFlags,
    target_user_key_hash: invitationApproval.target_user_key_hash || invitationApproval.targetUserKeyHash || null,
    login_identifier_hash: invitationApproval.login_identifier_hash || invitationApproval.loginIdentifierHash || null,
    login_identifier_masked: invitationApproval.login_identifier_masked || invitationApproval.loginIdentifierMasked || null,
    target_store_ids: targetStoreIds,
    target_role: targetRole,
    backend_route_implemented: true,
    public_endpoint_enabled: true,
    route_path: '/api/v1/permissions/user-invitation/approval-audit-linkage/readonly-check',
    http_method: 'POST',
    invitation_sent: false,
    users_written: false,
    membership_written: false,
    role_assignment_written: false,
    real_auth_session_created: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    operation_audit_rows_planned: true,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    platform_writes_enabled: false,
    business_message: businessMessage,
    next_action: '真实邀请仍需单独审批和写入阶段；当前只作为管理员复核证据。',
  };
}

function adaptPermissionGateResult(data = {}) {
  return {
    ...data,
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    actorRole: data.actor_role ?? data.actorRole ?? null,
    actorIdHash: data.actor_id_hash ?? data.actorIdHash ?? null,
    requestedStoreId: data.requested_store_id ?? data.requestedStoreId ?? null,
    operationKey: data.operation_key ?? data.operationKey ?? data.action_key ?? data.actionKey ?? null,
    storeScopeVerified: Boolean(data.store_scope_verified ?? data.storeScopeVerified),
    permissionVerified: Boolean(data.permission_verified ?? data.permissionVerified),
    manualApproval: Boolean(data.manual_approval ?? data.manualApproval),
    approvalRoleVerified: Boolean(data.approval_role_verified ?? data.approvalRoleVerified),
    approvalStatus: data.approval_status ?? data.approvalStatus ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    mockPermissionApi: Boolean(data.mock_permission_api ?? data.mockPermissionApi),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    realAuthSessionCreated: Boolean(data.real_auth_session_created ?? data.realAuthSessionCreated),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: Boolean(data.privacy_fields_redacted ?? data.privacyFieldsRedacted ?? true),
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function adaptShippingMapping(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id ?? item.storeId,
    platform: item.platform || 'naver',
    productName: item.match_product_name ?? item.productName ?? '',
    optionName: item.match_option_name ?? item.optionName ?? '',
    normalizedProductName: item.normalized_product_name ?? item.normalizedProductName ?? '',
    normalizedOptionName: item.normalized_option_name ?? item.normalizedOptionName ?? '',
    platformProductIdHash: item.platform_product_id_hash ?? item.platformProductIdHash ?? null,
    platformOptionIdHash: item.platform_option_id_hash ?? item.platformOptionIdHash ?? null,
    internalSku: item.internal_sku ?? item.internalSku ?? '',
    logisticsInventoryCode: item.logistics_inventory_code ?? item.logisticsInventoryCode ?? '',
    logisticsProviderName: item.logistics_provider_name ?? item.logisticsProviderName ?? '',
    currentStockQuantity: Number(item.current_stock_quantity ?? item.currentStockQuantity ?? 0),
    stockStatus: item.stock_status ?? item.stockStatus ?? 'unknown',
    matchPriority: Number(item.match_priority ?? item.matchPriority ?? 100),
    isActive: item.is_active ?? item.isActive ?? true,
    mappingVersion: item.mapping_version ?? item.mappingVersion ?? 'shipping_mapping_v1',
    lastManualCheckedAt: item.last_manual_checked_at ?? item.lastManualCheckedAt ?? null,
    createdAt: item.created_at ?? item.createdAt ?? null,
    updatedAt: item.updated_at ?? item.updatedAt ?? null,
  };
}

function adaptShippingMappingResult(data = {}) {
  const rows = (data.items || data.data || []).map(adaptShippingMapping);
  return {
    ...data,
    data: rows,
    items: rows,
    total: Number(data.total ?? rows.length),
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    mappingRowsReady: Number(data.mapping_rows_ready ?? data.mappingRowsReady ?? 0),
    inventoryRowsReady: Number(data.inventory_rows_ready ?? data.inventoryRowsReady ?? 0),
    createdMappings: Number(data.created_mappings ?? data.createdMappings ?? 0),
    updatedMappings: Number(data.updated_mappings ?? data.updatedMappings ?? 0),
    createdInventoryItems: Number(data.created_inventory_items ?? data.createdInventoryItems ?? 0),
    updatedInventoryItems: Number(data.updated_inventory_items ?? data.updatedInventoryItems ?? 0),
    shippingMappingsWritten: Boolean(data.shipping_mappings_written ?? data.shippingMappingsWritten),
    shippingInventoryWritten: Boolean(data.shipping_inventory_written ?? data.shippingInventoryWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: Boolean(data.privacy_fields_redacted ?? data.privacyFieldsRedacted ?? true),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function toBackendShippingMappingPayload(payload = {}) {
  return {
    store_id: Number(payload.storeId || payload.store_id),
    platform: payload.platform || 'naver',
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    actor_context: payload.actorContext || payload.actor_context || {},
    mappings: (payload.mappings || []).map((item) => ({
      match_product_name: item.productName || item.match_product_name || item.matchProductName || '',
      match_option_name: item.optionName || item.match_option_name || item.matchOptionName || '',
      platform_product_id_hash: item.platformProductIdHash || item.platform_product_id_hash || null,
      platform_option_id_hash: item.platformOptionIdHash || item.platform_option_id_hash || null,
      internal_sku: item.internalSku || item.internal_sku || '',
      logistics_inventory_code: item.logisticsInventoryCode || item.logistics_inventory_code || '',
      logistics_provider_name: item.logisticsProviderName || item.logistics_provider_name || '',
      current_stock_quantity: Number(item.currentStockQuantity ?? item.current_stock_quantity ?? 0),
      stock_status: item.stockStatus || item.stock_status || null,
      match_priority: Number(item.matchPriority ?? item.match_priority ?? 100),
      note: item.note || '',
      is_active: item.isActive ?? item.is_active ?? true,
    })),
  };
}

function adaptShippingExcelExportResult(data = {}) {
  const rows = data.export_rows_preview || data.rows || [];
  return {
    ...data,
    phase: data.phase || 'Shipping-3D',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    exportBatchId: data.export_batch_id ?? data.exportBatchId ?? null,
    exportBatchRowCount: Number(data.export_batch_row_count ?? data.exportBatchRowCount ?? rows.length),
    fileName: data.file_name ?? data.fileName ?? data.file_name_preview ?? data.fileNamePreview ?? '',
    filePath: data.file_path ?? data.filePath ?? '',
    fileHash: data.file_sha256 ?? data.fileHash ?? data.file_hash_planned ?? data.fileHashPlanned ?? '',
    fileSha256: data.file_sha256 ?? data.fileSha256 ?? '',
    fileSizeBytes: Number(data.file_size_bytes ?? data.fileSizeBytes ?? 0),
    fileType: data.file_type ?? data.fileType ?? 'shipping_request',
    fileFormat: data.file_format ?? data.fileFormat ?? 'xlsx',
    rowCount: Number(data.row_count ?? data.rowCount ?? rows.length),
    matchedRowCount: Number(data.matched_row_count ?? data.matchedRowCount ?? rows.length),
    unmatchedRowCount: Number(data.unmatched_row_count ?? data.unmatchedRowCount ?? 0),
    fileGenerated: Boolean(data.file_generated ?? data.fileGenerated),
    filePersisted: Boolean(data.file_persisted ?? data.filePersisted),
    exportRecordWritten: Boolean(data.export_record_written ?? data.exportRecordWritten),
    downloadRecordWritten: Boolean(data.download_record_written ?? data.downloadRecordWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    operationAuditLogId: data.operation_audit_log_id ?? data.operationAuditLogId ?? null,
    auditCorrelationId: data.audit_correlation_id ?? data.auditCorrelationId ?? null,
    exportRecordSchemaPlanned: Boolean(data.export_record_schema_planned ?? data.exportRecordSchemaPlanned ?? true),
    auditLinkagePlanned: Boolean(data.audit_linkage_planned ?? data.auditLinkagePlanned ?? true),
    trackingImportContractPlanned: Boolean(data.tracking_import_contract_planned ?? data.trackingImportContractPlanned ?? true),
    trackingNumberImportOpen: Boolean(data.tracking_number_import_open ?? data.trackingNumberImportOpen),
    includeReceiverPrivacy: Boolean(data.include_receiver_privacy ?? data.includeReceiverPrivacy),
    receiverPrivacyIncluded: Boolean(data.receiver_privacy_included ?? data.receiverPrivacyIncluded),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: Boolean(data.privacy_fields_redacted ?? data.privacyFieldsRedacted ?? true),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    rows: rows.map((row) => ({
      platform: row.platform || 'naver',
      orderNo: row.order_reference ?? row.orderNo ?? '',
      productName: row.product_name ?? row.productName ?? '',
      optionName: row.option_name ?? row.optionName ?? '',
      quantity: Number(row.quantity ?? 0),
      logisticsInventoryCode: row.logistics_inventory_code ?? row.logisticsInventoryCode ?? '',
      logisticsProviderName: row.logistics_provider_name ?? row.logisticsProviderName ?? '',
      logisticsCurrentStock: Number(row.logistics_current_stock ?? row.logisticsCurrentStock ?? 0),
      matchStatus: row.match_status ?? row.matchStatus ?? 'matched',
      note: row.note || '本地 Excel 已生成。',
    })),
  };
}

function toBackendShippingExcelExportPayload(payload = {}) {
  return {
    store_id: Number(payload.storeId || payload.store_id),
    platform: payload.platform || 'naver',
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    include_receiver_privacy: Boolean(payload.includeReceiverPrivacy ?? payload.include_receiver_privacy),
    actor_context: payload.actorContext || payload.actor_context || {},
    export_rows: (payload.rows || payload.exportRows || payload.export_rows || []).map((item) => ({
      order_reference: item.orderReference || item.orderNo || item.order_reference || '',
      product_name: item.productName || item.product_name || '',
      option_name: item.optionName || item.option_name || '',
      quantity: Number(item.quantity || 0),
      logistics_inventory_code: item.logisticsInventoryCode || item.logistics_inventory_code || '',
      logistics_provider_name: item.logisticsProviderName || item.logistics_provider_name || '',
      logistics_current_stock: Number(item.logisticsCurrentStock ?? item.currentStockQuantity ?? item.logistics_current_stock ?? 0),
      platform_product_id_hash: item.platformProductIdHash || item.platform_product_id_hash || null,
      platform_option_id_hash: item.platformOptionIdHash || item.platform_option_id_hash || null,
      internal_sku: item.internalSku || item.internal_sku || '',
    })),
  };
}

function adaptShippingExportHistoryItem(item = {}) {
  const rows = Array.isArray(item.rows) ? item.rows : [];
  return {
    id: item.id,
    storeId: item.store_id ?? item.storeId,
    platform: item.platform || 'naver',
    fileType: item.file_type ?? item.fileType ?? 'shipping_request',
    fileFormat: item.file_format ?? item.fileFormat ?? 'xlsx',
    fileName: item.file_name ?? item.fileName ?? '',
    filePath: item.file_path ?? item.filePath ?? '',
    fileSha256: item.file_sha256 ?? item.fileSha256 ?? '',
    rowCount: Number(item.row_count ?? item.rowCount ?? rows.length),
    matchedRowCount: Number(item.matched_row_count ?? item.matchedRowCount ?? rows.length),
    unmatchedRowCount: Number(item.unmatched_row_count ?? item.unmatchedRowCount ?? 0),
    auditCorrelationId: item.audit_correlation_id ?? item.auditCorrelationId ?? '',
    exportStatus: item.export_status ?? item.exportStatus ?? 'generated',
    includeReceiverPrivacy: Boolean(item.include_receiver_privacy ?? item.includeReceiverPrivacy),
    fileGenerated: Boolean(item.file_generated ?? item.fileGenerated),
    filePersisted: Boolean(item.file_persisted ?? item.filePersisted),
    rawResponseSaved: Boolean(item.raw_response_saved ?? item.rawResponseSaved),
    secretsSaved: Boolean(item.secrets_saved ?? item.secretsSaved),
    privacyFieldsRedacted: item.privacy_fields_redacted !== false && item.privacyFieldsRedacted !== false,
    mappingVersion: item.mapping_version ?? item.mappingVersion ?? 'shipping_export_v1',
    createdAt: item.created_at ?? item.createdAt ?? null,
    updatedAt: item.updated_at ?? item.updatedAt ?? null,
    rows: rows.map((row) => ({
      id: row.id,
      exportBatchId: row.export_batch_id ?? row.exportBatchId,
      orderNo: row.order_reference ?? row.orderNo ?? '',
      productName: row.product_name ?? row.productName ?? '',
      optionName: row.option_name ?? row.optionName ?? '',
      quantity: Number(row.quantity ?? 0),
      logisticsInventoryCode: row.logistics_inventory_code ?? row.logisticsInventoryCode ?? '',
      logisticsProviderName: row.logistics_provider_name ?? row.logisticsProviderName ?? '',
      internalSku: row.internal_sku ?? row.internalSku ?? '',
      rowStatus: row.row_status ?? row.rowStatus ?? 'ready',
      createdAt: row.created_at ?? row.createdAt ?? null,
    })),
  };
}

function adaptShippingExportHistoryResult(data = {}) {
  const rows = (data.items || data.data || []).map(adaptShippingExportHistoryItem);
  return {
    ...data,
    phase: data.phase || 'Shipping-4D',
    status: data.status || 'shipping_export_history_ready',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    data: rows,
    items: rows,
    total: Number(data.total ?? rows.length),
    limit: Number(data.limit ?? 20),
    offset: Number(data.offset ?? 0),
    includeRows: Boolean(data.include_rows ?? data.includeRows),
    readonlyRoute: Boolean(data.readonly_route ?? data.readonlyRoute ?? true),
    exportHistoryReadonly: Boolean(data.export_history_readonly ?? data.exportHistoryReadonly ?? true),
    trackingNumberImportOpen: Boolean(data.tracking_number_import_open ?? data.trackingNumberImportOpen),
    shipmentWritebackOpen: Boolean(data.shipment_writeback_open ?? data.shipmentWritebackOpen),
    importRecordWritten: Boolean(
      data.import_record_written
      ?? data.importRecordWritten
      ?? data.tracking_import_records_written
      ?? data.trackingImportRecordsWritten
    ),
    trackingImportBatchWritten: Boolean(data.tracking_import_batch_written ?? data.trackingImportBatchWritten),
    trackingImportRowsWritten: Boolean(data.tracking_import_rows_written ?? data.trackingImportRowsWritten),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function toBackendShippingTrackingImportPayload(payload = {}) {
  return {
    store_id: Number(payload.storeId || payload.store_id),
    platform: payload.platform || 'naver',
    file_type: payload.fileType || payload.file_type || 'tracking_upload',
    file_format: payload.fileFormat || payload.file_format || 'xlsx',
    source_file_name: payload.sourceFileName || payload.source_file_name || null,
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    parser_contract_acknowledged: Boolean(payload.parserContractAcknowledged ?? payload.parser_contract_acknowledged),
    actor_context: payload.actorContext || payload.actor_context || {},
    tracking_rows: (payload.rows || payload.trackingRows || payload.tracking_rows || []).map((item) => ({
      order_reference: item.orderReference || item.orderNo || item.order_reference || '',
      product_order_reference: item.productOrderReference || item.productOrderNo || item.product_order_reference || '',
      logistics_inventory_code: item.logisticsInventoryCode || item.logistics_inventory_code || '',
      carrier: item.carrier || '',
      tracking_number: item.trackingNumber || item.tracking_number || '',
      shipped_at: item.shippedAt || item.shipped_at || '',
      operator_note: item.operatorNote || item.operator_note || '',
    })),
  };
}

function toBackendShippingTrackingImportXlsxParsePayload(payload = {}) {
  return {
    store_id: Number(payload.storeId || payload.store_id),
    platform: payload.platform || 'naver',
    file_type: payload.fileType || payload.file_type || 'tracking_upload',
    file_format: payload.fileFormat || payload.file_format || 'xlsx',
    source_file_name: payload.sourceFileName || payload.source_file_name || '',
    file_content_base64: payload.fileContentBase64 || payload.file_content_base64 || '',
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    parser_contract_acknowledged: Boolean(payload.parserContractAcknowledged ?? payload.parser_contract_acknowledged),
    actor_context: payload.actorContext || payload.actor_context || {},
  };
}

function adaptShippingTrackingImportMockParseResult(data = {}) {
  const rows = data.tracking_rows_preview || data.rows || [];
  return {
    ...data,
    phase: data.phase || 'Shipping-4B',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    fileType: data.file_type ?? data.fileType ?? 'tracking_upload',
    fileFormat: data.file_format ?? data.fileFormat ?? 'xlsx',
    sourceFileName: data.source_file_name ?? data.sourceFileName ?? '',
    parserVersion: data.parser_version ?? data.parserVersion ?? '',
    fileReceived: Boolean(data.file_received ?? data.fileReceived),
    fileContentSaved: Boolean(data.file_content_saved ?? data.fileContentSaved),
    parsedRowsWritten: Boolean(data.parsed_rows_written ?? data.parsedRowsWritten),
    integrationPlanReady: Boolean(data.integration_plan_ready ?? data.integrationPlanReady),
    nextAction: data.next_action ?? data.nextAction ?? '',
    fileSizeBytes: Number(data.file_size_bytes ?? data.fileSizeBytes ?? 0),
    mappedColumns: Array.isArray(data.mapped_columns) ? data.mapped_columns : (Array.isArray(data.mappedColumns) ? data.mappedColumns : []),
    unknownColumns: Array.isArray(data.unknown_columns) ? data.unknown_columns : (Array.isArray(data.unknownColumns) ? data.unknownColumns : []),
    rowCount: Number(data.row_count ?? data.rowCount ?? rows.length),
    readyRowCount: Number(data.ready_row_count ?? data.readyRowCount ?? 0),
    duplicateRowCount: Number(data.duplicate_row_count ?? data.duplicateRowCount ?? 0),
    importBatchId: data.import_batch_id ?? data.importBatchId ?? null,
    auditCorrelationId: data.audit_correlation_id ?? data.auditCorrelationId ?? null,
    operationAuditLogId: data.operation_audit_log_id ?? data.operationAuditLogId ?? null,
    fileParsed: Boolean(data.file_parsed ?? data.fileParsed),
    parserContractAcknowledged: Boolean(data.parser_contract_acknowledged ?? data.parserContractAcknowledged),
    trackingNumberImportOpen: Boolean(data.tracking_number_import_open ?? data.trackingNumberImportOpen),
    trackingNumbersWritten: Boolean(data.tracking_numbers_written ?? data.trackingNumbersWritten),
    shipmentWritebackOpen: Boolean(data.shipment_writeback_open ?? data.shipmentWritebackOpen),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
    importRecordWritten: Boolean(data.import_record_written ?? data.importRecordWritten),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    rows: rows.map((row) => ({
      rowIndex: row.row_index ?? row.rowIndex,
      orderNo: row.order_reference ?? row.orderNo ?? '',
      productOrderNo: row.product_order_reference ?? row.productOrderNo ?? '',
      logisticsInventoryCode: row.logistics_inventory_code ?? row.logisticsInventoryCode ?? '',
      carrier: row.carrier || '',
      trackingNumber: row.tracking_number ?? row.trackingNumber ?? '',
      shippedAt: row.shipped_at ?? row.shippedAt ?? null,
      rowStatus: row.row_status ?? row.rowStatus ?? '',
      operatorNote: row.operator_note ?? row.operatorNote ?? '',
      futureWriteAllowed: Boolean(row.future_write_allowed ?? row.futureWriteAllowed),
    })),
  };
}

function adaptShippingTrackingImportHistoryItem(item = {}) {
  const rows = item.rows || [];
  return {
    id: item.id,
    storeId: item.store_id ?? item.storeId,
    platform: item.platform || 'naver',
    fileType: item.file_type ?? item.fileType ?? 'tracking_upload',
    fileFormat: item.file_format ?? item.fileFormat ?? 'xlsx',
    sourceFileName: item.source_file_name ?? item.sourceFileName ?? '',
    rowCount: Number(item.row_count ?? item.rowCount ?? 0),
    readyRowCount: Number(item.ready_row_count ?? item.readyRowCount ?? 0),
    duplicateRowCount: Number(item.duplicate_row_count ?? item.duplicateRowCount ?? 0),
    blockedRowCount: Number(item.blocked_row_count ?? item.blockedRowCount ?? 0),
    auditCorrelationId: item.audit_correlation_id ?? item.auditCorrelationId ?? '',
    importStatus: item.import_status ?? item.importStatus ?? '',
    parserContractAcknowledged: Boolean(item.parser_contract_acknowledged ?? item.parserContractAcknowledged),
    trackingNumberImportOpen: Boolean(item.tracking_number_import_open ?? item.trackingNumberImportOpen),
    shipmentWritebackCalled: Boolean(item.shipment_writeback_called ?? item.shipmentWritebackCalled),
    ordersUpdated: Boolean(item.orders_updated ?? item.ordersUpdated),
    rawResponseSaved: Boolean(item.raw_response_saved ?? item.rawResponseSaved),
    secretsSaved: Boolean(item.secrets_saved ?? item.secretsSaved),
    privacyFieldsRedacted: item.privacy_fields_redacted !== false && item.privacyFieldsRedacted !== false,
    mappingVersion: item.mapping_version ?? item.mappingVersion ?? 'shipping_tracking_import_v1',
    createdAt: item.created_at ?? item.createdAt ?? null,
    updatedAt: item.updated_at ?? item.updatedAt ?? null,
    rows: rows.map((row) => ({
      id: row.id,
      importBatchId: row.import_batch_id ?? row.importBatchId,
      orderNo: row.order_reference ?? row.orderNo ?? '',
      productOrderNo: row.product_order_reference ?? row.productOrderNo ?? '',
      logisticsInventoryCode: row.logistics_inventory_code ?? row.logisticsInventoryCode ?? '',
      carrier: row.carrier || '',
      trackingNumber: row.tracking_number ?? row.trackingNumber ?? '',
      shippedAt: row.shipped_at ?? row.shippedAt ?? null,
      rowStatus: row.row_status ?? row.rowStatus ?? '',
      operatorNote: row.operator_note ?? row.operatorNote ?? '',
      futureWriteAllowed: Boolean(row.future_write_allowed ?? row.futureWriteAllowed),
      createdAt: row.created_at ?? row.createdAt ?? null,
    })),
  };
}

function adaptShippingTrackingImportHistoryResult(data = {}) {
  const rows = (data.items || data.data || []).map(adaptShippingTrackingImportHistoryItem);
  return {
    ...data,
    phase: data.phase || 'Shipping-5E',
    status: data.status || 'tracking_import_history_ready',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    data: rows,
    items: rows,
    total: Number(data.total ?? rows.length),
    limit: Number(data.limit ?? 20),
    offset: Number(data.offset ?? 0),
    includeRows: Boolean(data.include_rows ?? data.includeRows),
    readonlyRoute: Boolean(data.readonly_route ?? data.readonlyRoute ?? true),
    trackingImportHistoryReadonly: Boolean(data.tracking_import_history_readonly ?? data.trackingImportHistoryReadonly ?? true),
    trackingNumberImportOpen: Boolean(data.tracking_number_import_open ?? data.trackingNumberImportOpen),
    shipmentWritebackOpen: Boolean(data.shipment_writeback_open ?? data.shipmentWritebackOpen),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
    ordersUpdated: Boolean(data.orders_updated ?? data.ordersUpdated),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function adaptShippingTrackingOrderMatchResult(data = {}) {
  const rows = Array.isArray(data.match_rows) ? data.match_rows : (Array.isArray(data.matchRows) ? data.matchRows : []);
  return {
    ...data,
    phase: data.phase || 'Shipping-6B',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    readonlyRoute: Boolean(data.readonly_route ?? data.readonlyRoute ?? true),
    trackingOrderMatchReadonly: Boolean(data.tracking_order_match_readonly ?? data.trackingOrderMatchReadonly ?? true),
    matchingContractAcknowledged: Boolean(data.matching_contract_acknowledged ?? data.matchingContractAcknowledged),
    importBatchId: data.import_batch_id ?? data.importBatchId ?? null,
    totalTrackingRows: Number(data.total_tracking_rows ?? data.totalTrackingRows ?? rows.length),
    matchedOrderCount: Number(data.matched_order_count ?? data.matchedOrderCount ?? 0),
    unmatchedOrderCount: Number(data.unmatched_order_count ?? data.unmatchedOrderCount ?? 0),
    duplicateTrackingRowCount: Number(data.duplicate_tracking_row_count ?? data.duplicateTrackingRowCount ?? 0),
    trackingNumberImportOpen: Boolean(data.tracking_number_import_open ?? data.trackingNumberImportOpen),
    shipmentWritebackOpen: Boolean(data.shipment_writeback_open ?? data.shipmentWritebackOpen),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
    ordersUpdated: Boolean(data.orders_updated ?? data.ordersUpdated),
    trackingRowsWritten: Boolean(data.tracking_rows_written ?? data.trackingRowsWritten),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    rows: rows.map((row) => ({
      rowIndex: row.row_index ?? row.rowIndex,
      orderNo: row.order_reference ?? row.orderNo ?? '',
      productOrderNo: row.product_order_reference ?? row.productOrderNo ?? '',
      logisticsInventoryCode: row.logistics_inventory_code ?? row.logisticsInventoryCode ?? '',
      carrier: row.carrier || '',
      trackingNumber: row.tracking_number ?? row.trackingNumber ?? '',
      shippedAt: row.shipped_at ?? row.shippedAt ?? null,
      rowStatus: row.row_status ?? row.rowStatus ?? '',
      matchStatus: row.match_status ?? row.matchStatus ?? '',
      matchMethod: row.match_method ?? row.matchMethod ?? '',
      futureWriteAllowed: Boolean(row.future_write_allowed ?? row.futureWriteAllowed),
      orderSummary: row.order_summary || row.orderSummary || null,
    })),
  };
}

function toBackendShippingTrackingOrderMatchPayload(payload = {}) {
  return {
    store_id: Number(payload.storeId || payload.store_id),
    platform: payload.platform || 'naver',
    import_batch_id: payload.importBatchId || payload.import_batch_id || null,
    matching_contract_acknowledged: Boolean(payload.matchingContractAcknowledged ?? payload.matching_contract_acknowledged),
    actor_context: payload.actorContext || payload.actor_context || {},
    tracking_rows: toBackendShippingTrackingImportPayload(payload).tracking_rows,
  };
}

function adaptShippingTrackingOrderStatusLocalUpdateResult(data = {}) {
  const updateCandidates = Array.isArray(data.update_candidates)
    ? data.update_candidates
    : (Array.isArray(data.updateCandidates) ? data.updateCandidates : []);
  const blockedOrders = Array.isArray(data.blocked_orders)
    ? data.blocked_orders
    : (Array.isArray(data.blockedOrders) ? data.blockedOrders : []);
  return {
    ...data,
    phase: data.phase || 'Shipping-8B',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    manualApproval: Boolean(data.manual_approval ?? data.manualApproval),
    matchingContractAcknowledged: Boolean(data.matching_contract_acknowledged ?? data.matchingContractAcknowledged),
    backupEvidenceAcknowledged: Boolean(data.backup_evidence_acknowledged ?? data.backupEvidenceAcknowledged),
    auditEvidenceAcknowledged: Boolean(data.audit_evidence_acknowledged ?? data.auditEvidenceAcknowledged),
    operatorChecklistAcknowledged: Boolean(data.operator_checklist_acknowledged ?? data.operatorChecklistAcknowledged),
    trackingOrderStatusLocalUpdateGate: Boolean(
      data.tracking_order_status_local_update_gate ?? data.trackingOrderStatusLocalUpdateGate,
    ),
    trackingOrderStatusLocalUpdate: Boolean(
      data.tracking_order_status_local_update ?? data.trackingOrderStatusLocalUpdate,
    ),
    targetOrderStatus: data.target_order_status ?? data.targetOrderStatus ?? 'DISPATCHED',
    targetOrderStatusLabelZh: data.target_order_status_label_zh ?? data.targetOrderStatusLabelZh ?? '已发货 / 配送中',
    importBatchId: data.import_batch_id ?? data.importBatchId ?? null,
    matchedOrderCount: Number(data.matched_order_count ?? data.matchedOrderCount ?? 0),
    updateCandidateCount: Number(data.update_candidate_count ?? data.updateCandidateCount ?? updateCandidates.length),
    alreadyUpdatedCount: Number(data.already_updated_count ?? data.alreadyUpdatedCount ?? 0),
    blockedOrderCount: Number(data.blocked_order_count ?? data.blockedOrderCount ?? blockedOrders.length),
    duplicateTrackingRowCount: Number(data.duplicate_tracking_row_count ?? data.duplicateTrackingRowCount ?? 0),
    unmatchedOrderCount: Number(data.unmatched_order_count ?? data.unmatchedOrderCount ?? 0),
    updatedOrderCount: Number(data.updated_order_count ?? data.updatedOrderCount ?? 0),
    skippedOrderCount: Number(data.skipped_order_count ?? data.skippedOrderCount ?? 0),
    eventRowsWritten: Number(data.event_rows_written ?? data.eventRowsWritten ?? 0),
    updatedOrderIds: Array.isArray(data.updated_order_ids)
      ? data.updated_order_ids
      : (Array.isArray(data.updatedOrderIds) ? data.updatedOrderIds : []),
    auditCorrelationId: data.audit_correlation_id ?? data.auditCorrelationId ?? null,
    operationAuditLogId: data.operation_audit_log_id ?? data.operationAuditLogId ?? null,
    ordersUpdated: Boolean(data.orders_updated ?? data.ordersUpdated),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    orderStatusEventsWritten: Boolean(data.order_status_events_written ?? data.orderStatusEventsWritten),
    trackingImportBatchUpdated: Boolean(data.tracking_import_batch_updated ?? data.trackingImportBatchUpdated),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
    updateCandidates: updateCandidates.map((item) => ({
      localOrderId: item.local_order_id ?? item.localOrderId ?? null,
      currentOrderStatus: item.current_order_status ?? item.currentOrderStatus ?? '',
      nextOrderStatus: item.next_order_status ?? item.nextOrderStatus ?? '',
      trackingNumberHash: item.tracking_number_hash ?? item.trackingNumberHash ?? '',
      carrier: item.carrier || '',
      shippedAt: item.shipped_at ?? item.shippedAt ?? null,
    })),
    blockedOrders: blockedOrders.map((item) => ({
      localOrderId: item.local_order_id ?? item.localOrderId ?? null,
      currentOrderStatus: item.current_order_status ?? item.currentOrderStatus ?? '',
      blockReason: item.block_reason ?? item.blockReason ?? '',
    })),
  };
}

function toBackendShippingTrackingOrderStatusLocalUpdatePayload(payload = {}) {
  const request = toBackendShippingTrackingOrderMatchPayload(payload);
  return {
    ...request,
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    backup_evidence_acknowledged: Boolean(payload.backupEvidenceAcknowledged ?? payload.backup_evidence_acknowledged),
    audit_evidence_acknowledged: Boolean(payload.auditEvidenceAcknowledged ?? payload.audit_evidence_acknowledged),
    operator_checklist_acknowledged: Boolean(payload.operatorChecklistAcknowledged ?? payload.operator_checklist_acknowledged),
    target_order_status: payload.targetOrderStatus || payload.target_order_status || 'DISPATCHED',
  };
}

function adaptShippingShipmentWritebackBoundaryResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'Shipping-6C',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    readonlyRoute: Boolean(data.readonly_route ?? data.readonlyRoute ?? true),
    shipmentWritebackBoundaryReview: Boolean(data.shipment_writeback_boundary_review ?? data.shipmentWritebackBoundaryReview ?? true),
    manualApproval: Boolean(data.manual_approval ?? data.manualApproval),
    matchedOrderCount: Number(data.matched_order_count ?? data.matchedOrderCount ?? 0),
    totalTrackingRows: Number(data.total_tracking_rows ?? data.totalTrackingRows ?? 0),
    matchingEvidenceAcknowledged: Boolean(data.matching_evidence_acknowledged ?? data.matchingEvidenceAcknowledged),
    backupEvidenceAcknowledged: Boolean(data.backup_evidence_acknowledged ?? data.backupEvidenceAcknowledged),
    auditEvidenceAcknowledged: Boolean(data.audit_evidence_acknowledged ?? data.auditEvidenceAcknowledged),
    naverWritebackBoundaryAcknowledged: Boolean(data.naver_writeback_boundary_acknowledged ?? data.naverWritebackBoundaryAcknowledged),
    operatorChecklistAcknowledged: Boolean(data.operator_checklist_acknowledged ?? data.operatorChecklistAcknowledged),
    requiredActions: Array.isArray(data.required_actions) ? data.required_actions : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    missingActions: Array.isArray(data.missing_actions) ? data.missing_actions : (Array.isArray(data.missingActions) ? data.missingActions : []),
    trackingNumberImportOpen: Boolean(data.tracking_number_import_open ?? data.trackingNumberImportOpen),
    shipmentWritebackOpen: Boolean(data.shipment_writeback_open ?? data.shipmentWritebackOpen),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
    ordersUpdated: Boolean(data.orders_updated ?? data.ordersUpdated),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function toBackendShippingShipmentWritebackBoundaryPayload(payload = {}) {
  return {
    store_id: Number(payload.storeId || payload.store_id),
    platform: payload.platform || 'naver',
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    matched_order_count: Number(payload.matchedOrderCount ?? payload.matched_order_count ?? 0),
    total_tracking_rows: Number(payload.totalTrackingRows ?? payload.total_tracking_rows ?? 0),
    matching_evidence_acknowledged: Boolean(payload.matchingEvidenceAcknowledged ?? payload.matching_evidence_acknowledged),
    backup_evidence_acknowledged: Boolean(payload.backupEvidenceAcknowledged ?? payload.backup_evidence_acknowledged),
    audit_evidence_acknowledged: Boolean(payload.auditEvidenceAcknowledged ?? payload.audit_evidence_acknowledged),
    naver_writeback_boundary_acknowledged: Boolean(payload.naverWritebackBoundaryAcknowledged ?? payload.naver_writeback_boundary_acknowledged),
    operator_checklist_acknowledged: Boolean(payload.operatorChecklistAcknowledged ?? payload.operator_checklist_acknowledged),
    actor_context: payload.actorContext || payload.actor_context || {},
  };
}

function adaptShippingShipmentWritebackDryRunGateResult(data = {}) {
  const candidates = Array.isArray(data.dry_run_candidates)
    ? data.dry_run_candidates
    : (Array.isArray(data.dryRunCandidates) ? data.dryRunCandidates : []);
  const blockedOrders = Array.isArray(data.blocked_orders)
    ? data.blocked_orders
    : (Array.isArray(data.blockedOrders) ? data.blockedOrders : []);
  return {
    ...data,
    phase: data.phase || 'Shipping-8F',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    readonlyRoute: Boolean(data.readonly_route ?? data.readonlyRoute ?? true),
    shipmentWritebackDryRunGate: Boolean(data.shipment_writeback_dry_run_gate ?? data.shipmentWritebackDryRunGate ?? true),
    shipmentWritebackDryRunReady: Boolean(data.shipment_writeback_dry_run_ready ?? data.shipmentWritebackDryRunReady),
    futurePlatformWriteRequiresSeparateApproval: (
      data.future_platform_write_requires_separate_approval !== false
      && data.futurePlatformWriteRequiresSeparateApproval !== false
    ),
    manualApproval: Boolean(data.manual_approval ?? data.manualApproval),
    matchingContractAcknowledged: Boolean(data.matching_contract_acknowledged ?? data.matchingContractAcknowledged),
    backupEvidenceAcknowledged: Boolean(data.backup_evidence_acknowledged ?? data.backupEvidenceAcknowledged),
    auditEvidenceAcknowledged: Boolean(data.audit_evidence_acknowledged ?? data.auditEvidenceAcknowledged),
    localStatusEvidenceAcknowledged: Boolean(data.local_status_evidence_acknowledged ?? data.localStatusEvidenceAcknowledged),
    naverWritebackBoundaryAcknowledged: Boolean(data.naver_writeback_boundary_acknowledged ?? data.naverWritebackBoundaryAcknowledged),
    operatorChecklistAcknowledged: Boolean(data.operator_checklist_acknowledged ?? data.operatorChecklistAcknowledged),
    targetDeliveryStatus: data.target_delivery_status ?? data.targetDeliveryStatus ?? 'DISPATCHED',
    targetDeliveryStatusLabelZh: data.target_delivery_status_label_zh ?? data.targetDeliveryStatusLabelZh ?? '已发货 / 配送中',
    importBatchId: data.import_batch_id ?? data.importBatchId ?? null,
    totalTrackingRows: Number(data.total_tracking_rows ?? data.totalTrackingRows ?? 0),
    matchedOrderCount: Number(data.matched_order_count ?? data.matchedOrderCount ?? 0),
    unmatchedOrderCount: Number(data.unmatched_order_count ?? data.unmatchedOrderCount ?? 0),
    duplicateTrackingRowCount: Number(data.duplicate_tracking_row_count ?? data.duplicateTrackingRowCount ?? 0),
    dryRunCandidateCount: Number(data.dry_run_candidate_count ?? data.dryRunCandidateCount ?? candidates.length),
    blockedOrderCount: Number(data.blocked_order_count ?? data.blockedOrderCount ?? blockedOrders.length),
    trackingNumberImportOpen: Boolean(data.tracking_number_import_open ?? data.trackingNumberImportOpen),
    shipmentWritebackOpen: Boolean(data.shipment_writeback_open ?? data.shipmentWritebackOpen),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
    ordersUpdated: Boolean(data.orders_updated ?? data.ordersUpdated),
    orderStatusEventsWritten: Boolean(data.order_status_events_written ?? data.orderStatusEventsWritten),
    trackingImportBatchUpdated: Boolean(data.tracking_import_batch_updated ?? data.trackingImportBatchUpdated),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    dryRunCandidates: candidates.map((item) => ({
      localOrderId: item.local_order_id ?? item.localOrderId ?? null,
      orderReferenceHash: item.order_reference_hash ?? item.orderReferenceHash ?? '',
      productOrderReferenceHash: item.product_order_reference_hash ?? item.productOrderReferenceHash ?? '',
      trackingNumberHash: item.tracking_number_hash ?? item.trackingNumberHash ?? '',
      carrier: item.carrier || '',
      shippedAt: item.shipped_at ?? item.shippedAt ?? null,
      currentOrderStatus: item.current_order_status ?? item.currentOrderStatus ?? '',
      targetDeliveryStatus: item.target_delivery_status ?? item.targetDeliveryStatus ?? 'DISPATCHED',
      payloadPreviewSaved: Boolean(item.payload_preview_saved ?? item.payloadPreviewSaved),
      rawResponseSaved: Boolean(item.raw_response_saved ?? item.rawResponseSaved),
      futureWriteAllowed: Boolean(item.future_write_allowed ?? item.futureWriteAllowed),
    })),
    blockedOrders: blockedOrders.map((item) => ({
      localOrderId: item.local_order_id ?? item.localOrderId ?? null,
      currentOrderStatus: item.current_order_status ?? item.currentOrderStatus ?? '',
      blockReason: item.block_reason ?? item.blockReason ?? '',
    })),
  };
}

function adaptShippingShipmentWritebackExecutionMockGateResult(data = {}) {
  const candidates = Array.isArray(data.execution_candidates)
    ? data.execution_candidates
    : (Array.isArray(data.executionCandidates) ? data.executionCandidates : []);
  return {
    ...data,
    phase: data.phase || 'Shipping-9B',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    readonlyRoute: Boolean(data.readonly_route ?? data.readonlyRoute ?? true),
    shipmentWritebackExecutionMockGate: Boolean(
      data.shipment_writeback_execution_mock_gate ?? data.shipmentWritebackExecutionMockGate ?? true,
    ),
    shipmentWritebackExecutionReady: Boolean(
      data.shipment_writeback_execution_ready ?? data.shipmentWritebackExecutionReady,
    ),
    executionApproval: Boolean(data.execution_approval ?? data.executionApproval),
    dryRunEvidenceAcknowledged: Boolean(
      data.dry_run_evidence_acknowledged ?? data.dryRunEvidenceAcknowledged,
    ),
    permissionEvidenceAcknowledged: Boolean(
      data.permission_evidence_acknowledged ?? data.permissionEvidenceAcknowledged,
    ),
    finalOperatorConfirmation: Boolean(
      data.final_operator_confirmation ?? data.finalOperatorConfirmation,
    ),
    realApiCallRequested: Boolean(data.real_api_call_requested ?? data.realApiCallRequested),
    futureRealWriteRequiresSeparateApproval: (
      data.future_real_write_requires_separate_approval !== false
      && data.futureRealWriteRequiresSeparateApproval !== false
    ),
    importBatchId: data.import_batch_id ?? data.importBatchId ?? null,
    matchedOrderCount: Number(data.matched_order_count ?? data.matchedOrderCount ?? 0),
    unmatchedOrderCount: Number(data.unmatched_order_count ?? data.unmatchedOrderCount ?? 0),
    dryRunStatus: data.dry_run_status ?? data.dryRunStatus ?? '',
    dryRunSkipReason: data.dry_run_skip_reason ?? data.dryRunSkipReason ?? null,
    dryRunCandidateCount: Number(data.dry_run_candidate_count ?? data.dryRunCandidateCount ?? 0),
    executionCandidateCount: Number(data.execution_candidate_count ?? data.executionCandidateCount ?? candidates.length),
    executionCandidates: candidates.map((item) => ({
      localOrderId: item.local_order_id ?? item.localOrderId ?? null,
      orderReferenceHash: item.order_reference_hash ?? item.orderReferenceHash ?? '',
      productOrderReferenceHash: item.product_order_reference_hash ?? item.productOrderReferenceHash ?? '',
      trackingNumberHash: item.tracking_number_hash ?? item.trackingNumberHash ?? '',
      carrier: item.carrier || '',
      shippedAt: item.shipped_at ?? item.shippedAt ?? null,
      currentOrderStatus: item.current_order_status ?? item.currentOrderStatus ?? '',
      targetDeliveryStatus: item.target_delivery_status ?? item.targetDeliveryStatus ?? 'DISPATCHED',
      executionAllowed: Boolean(item.execution_allowed ?? item.executionAllowed),
      futureWriteAllowed: Boolean(item.future_write_allowed ?? item.futureWriteAllowed),
      payloadPreviewSaved: Boolean(item.payload_preview_saved ?? item.payloadPreviewSaved),
      rawResponseSaved: Boolean(item.raw_response_saved ?? item.rawResponseSaved),
    })),
    shipmentWritebackOpen: Boolean(data.shipment_writeback_open ?? data.shipmentWritebackOpen),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    ordersUpdated: Boolean(data.orders_updated ?? data.ordersUpdated),
    orderStatusEventsWritten: Boolean(data.order_status_events_written ?? data.orderStatusEventsWritten),
    trackingImportBatchUpdated: Boolean(data.tracking_import_batch_updated ?? data.trackingImportBatchUpdated),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
  };
}

function adaptShippingShipmentWritebackExecuteResult(data = {}) {
  return {
    ...adaptShippingShipmentWritebackExecutionMockGateResult(data),
    phase: data.phase || 'Shipping-10A',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    shipmentWritebackExecute: Boolean(data.shipment_writeback_execute ?? data.shipmentWritebackExecute ?? true),
    platformWrite: Boolean(data.platform_write ?? data.platformWrite),
    platformWriteAttempted: Boolean(data.platform_write_attempted ?? data.platformWriteAttempted),
    dispatchCandidateCount: Number(data.dispatch_candidate_count ?? data.dispatchCandidateCount ?? 0),
    successCount: Number(data.success_count ?? data.successCount ?? 0),
    failedCount: Number(data.failed_count ?? data.failedCount ?? 0),
    updatedOrderCount: Number(data.updated_order_count ?? data.updatedOrderCount ?? 0),
    operationAuditLogId: data.operation_audit_log_id ?? data.operationAuditLogId ?? null,
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    shipmentWritebackCalled: Boolean(data.shipment_writeback_called ?? data.shipmentWritebackCalled),
  };
}

function toBackendShippingShipmentWritebackDryRunGatePayload(payload = {}) {
  const request = toBackendShippingTrackingOrderMatchPayload(payload);
  return {
    ...request,
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    backup_evidence_acknowledged: Boolean(payload.backupEvidenceAcknowledged ?? payload.backup_evidence_acknowledged),
    audit_evidence_acknowledged: Boolean(payload.auditEvidenceAcknowledged ?? payload.audit_evidence_acknowledged),
    local_status_evidence_acknowledged: Boolean(payload.localStatusEvidenceAcknowledged ?? payload.local_status_evidence_acknowledged),
    naver_writeback_boundary_acknowledged: Boolean(payload.naverWritebackBoundaryAcknowledged ?? payload.naver_writeback_boundary_acknowledged),
    operator_checklist_acknowledged: Boolean(payload.operatorChecklistAcknowledged ?? payload.operator_checklist_acknowledged),
    target_delivery_status: payload.targetDeliveryStatus || payload.target_delivery_status || 'DISPATCHED',
  };
}

function toBackendShippingShipmentWritebackExecutionMockGatePayload(payload = {}) {
  const request = toBackendShippingShipmentWritebackDryRunGatePayload(payload);
  return {
    ...request,
    execution_approval: Boolean(payload.executionApproval ?? payload.execution_approval),
    dry_run_evidence_acknowledged: Boolean(
      payload.dryRunEvidenceAcknowledged ?? payload.dry_run_evidence_acknowledged,
    ),
    permission_evidence_acknowledged: Boolean(
      payload.permissionEvidenceAcknowledged ?? payload.permission_evidence_acknowledged,
    ),
    final_operator_confirmation: Boolean(
      payload.finalOperatorConfirmation ?? payload.final_operator_confirmation,
    ),
    real_api_call_requested: Boolean(payload.realApiCallRequested ?? payload.real_api_call_requested),
  };
}

function adaptStoreMembershipReadonlyResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'ERP-Multistore-1G',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    targetUserKeyHash: data.target_user_key_hash ?? data.targetUserKeyHash ?? null,
    targetStoreId: Number(data.target_store_id ?? data.targetStoreId ?? 0),
    targetRole: data.target_role ?? data.targetRole ?? null,
    manualApproval: Boolean(data.manual_approval ?? data.manualApproval),
    assignmentReasonPresent: Boolean(data.assignment_reason_present ?? data.assignmentReasonPresent),
    targetUserExists: Boolean(data.target_user_exists ?? data.targetUserExists),
    targetRoleExists: Boolean(data.target_role_exists ?? data.targetRoleExists),
    duplicateActiveMembership: Boolean(data.duplicate_active_membership ?? data.duplicateActiveMembership),
    existingActiveMembershipCount: Number(data.existing_active_membership_count ?? data.existingActiveMembershipCount ?? 0),
    membershipWouldCreate: Boolean(data.membership_would_create ?? data.membershipWouldCreate),
    membershipWritten: Boolean(data.membership_written ?? data.membershipWritten),
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    readonlyApiMockGate: Boolean(data.readonly_api_mock_gate ?? data.readonlyApiMockGate),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    realAuthSessionCreated: Boolean(data.real_auth_session_created ?? data.realAuthSessionCreated),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function adaptUserInvitationReadonlyResult(data = {}) {
  const rawApprovalResults = Array.isArray(data.approval_results)
    ? data.approval_results
    : (Array.isArray(data.approvalResults) ? data.approvalResults : []);
  const approvalResults = rawApprovalResults.map((item) => ({
    storeId: item.store_id ?? item.storeId ?? null,
    status: item.status || 'blocked',
    skipReason: item.skip_reason ?? item.skipReason ?? null,
    actorRole: item.actor_role ?? item.actorRole ?? null,
    actorIdHash: item.actor_id_hash ?? item.actorIdHash ?? null,
    storeScopeVerified: Boolean(item.store_scope_verified ?? item.storeScopeVerified),
    permissionVerified: Boolean(item.permission_verified ?? item.permissionVerified),
    approvalRoleVerified: Boolean(item.approval_role_verified ?? item.approvalRoleVerified),
  }));
  const approvalRoleVerified = approvalResults.length
    ? approvalResults.every((item) => item.approvalRoleVerified)
    : Boolean(data.approval_role_verified ?? data.approvalRoleVerified);
  return {
    ...data,
    phase: data.phase || 'ERP-Multistore-1P',
    status: data.status || 'blocked',
    skipReason: data.skip_reason ?? data.skipReason ?? null,
    targetUserKeyHash: data.target_user_key_hash ?? data.targetUserKeyHash ?? null,
    loginIdentifierHash: data.login_identifier_hash ?? data.loginIdentifierHash ?? null,
    loginIdentifierMasked: data.login_identifier_masked ?? data.loginIdentifierMasked ?? null,
    targetStoreIds: Array.isArray(data.target_store_ids || data.targetStoreIds) ? (data.target_store_ids || data.targetStoreIds) : [],
    targetRole: data.target_role ?? data.targetRole ?? null,
    manualApproval: Boolean(data.manual_approval ?? data.manualApproval),
    approvalResults,
    approvalRoleVerified,
    invitationReasonPresent: Boolean(data.invitation_reason_present ?? data.invitationReasonPresent),
    backupEvidencePlanned: Boolean(data.backup_evidence_planned ?? data.backupEvidencePlanned),
    auditEvidencePlanned: Boolean(data.audit_evidence_planned ?? data.auditEvidencePlanned),
    membershipAssignmentPlanReady: Boolean(data.membership_assignment_plan_ready ?? data.membershipAssignmentPlanReady),
    invitationWouldCreateUser: Boolean(data.invitation_would_create_user ?? data.invitationWouldCreateUser),
    invitationWouldSend: Boolean(data.invitation_would_send ?? data.invitationWouldSend),
    invitationSent: Boolean(data.invitation_sent ?? data.invitationSent),
    usersWritten: Boolean(data.users_written ?? data.usersWritten),
    membershipWritten: Boolean(data.membership_written ?? data.membershipWritten),
    roleAssignmentWritten: Boolean(data.role_assignment_written ?? data.roleAssignmentWritten),
    operationAuditRowsPlanned: data.operation_audit_rows_planned !== false && data.operationAuditRowsPlanned !== false,
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    businessMessage: data.business_message ?? data.businessMessage ?? '',
    readonlyApiMockGate: Boolean(data.readonly_api_mock_gate ?? data.readonlyApiMockGate),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    realAuthSessionCreated: Boolean(data.real_auth_session_created ?? data.realAuthSessionCreated),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function adaptUserInvitationApprovalChecklistReadonlyResult(data = {}) {
  const base = adaptUserInvitationReadonlyResult(data);
  return {
    ...base,
    phase: data.phase || base.phase || 'ERP-Multistore-2J',
    checklistReady: Boolean(data.checklist_ready ?? data.checklistReady),
    requiredChecklistFlags: Array.isArray(data.required_checklist_flags)
      ? data.required_checklist_flags
      : (Array.isArray(data.requiredChecklistFlags) ? data.requiredChecklistFlags : []),
    missingChecklistFlags: Array.isArray(data.missing_checklist_flags)
      ? data.missing_checklist_flags
      : (Array.isArray(data.missingChecklistFlags) ? data.missingChecklistFlags : []),
    requiredApiFlags: Array.isArray(data.required_api_flags)
      ? data.required_api_flags
      : (Array.isArray(data.requiredApiFlags) ? data.requiredApiFlags : []),
    missingApiFlags: Array.isArray(data.missing_api_flags)
      ? data.missing_api_flags
      : (Array.isArray(data.missingApiFlags) ? data.missingApiFlags : []),
    routePath: data.route_path || data.routePath || data.route_path_planned || data.routePathPlanned || '',
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    backupEvidenceReady: Boolean(data.backup_evidence_ready ?? data.backupEvidenceReady ?? data.backup_evidence_planned ?? data.backupEvidencePlanned),
    auditEvidencePlanReady: Boolean(data.audit_evidence_plan_ready ?? data.auditEvidencePlanReady ?? data.audit_evidence_planned ?? data.auditEvidencePlanned),
    inviteExpiryConfigured: Boolean(data.invite_expiry_configured ?? data.inviteExpiryConfigured),
    oneTimeInviteConfigured: Boolean(data.one_time_invite_configured ?? data.oneTimeInviteConfigured),
    postCreateReadbackRequired: Boolean(data.post_create_readback_required ?? data.postCreateReadbackRequired),
    disableUserRollbackReady: Boolean(data.disable_user_rollback_ready ?? data.disableUserRollbackReady),
    privacyDisplayVerified: Boolean(data.privacy_display_verified ?? data.privacyDisplayVerified),
    formalLoginBoundaryAcknowledged: Boolean(data.formal_login_boundary_acknowledged ?? data.formalLoginBoundaryAcknowledged),
    nextAction: data.next_action || data.nextAction || '',
  };
}

function adaptUserInvitationApprovalAuditLinkageReadonlyResult(data = {}) {
  const base = adaptUserInvitationReadonlyResult(data);
  return {
    ...base,
    phase: data.phase || base.phase || 'ERP-Multistore-2T',
    auditLinkageReady: Boolean(data.audit_linkage_ready ?? data.auditLinkageReady),
    requiredLinkageFlags: Array.isArray(data.required_linkage_flags)
      ? data.required_linkage_flags
      : (Array.isArray(data.requiredLinkageFlags) ? data.requiredLinkageFlags : []),
    missingLinkageFlags: Array.isArray(data.missing_linkage_flags)
      ? data.missing_linkage_flags
      : (Array.isArray(data.missingLinkageFlags) ? data.missingLinkageFlags : []),
    requiredApiFlags: Array.isArray(data.required_api_flags)
      ? data.required_api_flags
      : (Array.isArray(data.requiredApiFlags) ? data.requiredApiFlags : []),
    missingApiFlags: Array.isArray(data.missing_api_flags)
      ? data.missing_api_flags
      : (Array.isArray(data.missingApiFlags) ? data.missingApiFlags : []),
    routePath: data.route_path || data.routePath || data.route_path_planned || data.routePathPlanned || '',
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    auditCorrelationIdPlanned: Boolean(data.audit_correlation_id_planned ?? data.auditCorrelationIdPlanned),
    appendOnlyAuditRowsPlanned: Boolean(data.append_only_audit_rows_planned ?? data.appendOnlyAuditRowsPlanned),
    invitationDecisionIdPlanned: Boolean(data.invitation_decision_id_planned ?? data.invitationDecisionIdPlanned),
    approvalActorHashPlanned: Boolean(data.approval_actor_hash_planned ?? data.approvalActorHashPlanned),
    nextAction: data.next_action || data.nextAction || '',
  };
}

function adaptBatchReadonlyEvidenceResult(data = {}) {
  const items = (Array.isArray(data.items) ? data.items : []).map((item, index) => ({
    evidenceId: item.evidence_id || item.evidenceId || `evidence-${index + 1}`,
    storeId: Number(item.store_id ?? item.storeId ?? 0),
    platform: item.platform || 'naver',
    syncKind: item.sync_kind || item.syncKind || '',
    target: item.target || '',
    windowLabel: item.window_label || item.windowLabel || '只读窗口',
    candidateCount: Number(item.candidate_count ?? item.candidateCount ?? 0),
    wouldCreate: Number(item.would_create ?? item.wouldCreate ?? 0),
    wouldUpdate: Number(item.would_update ?? item.wouldUpdate ?? 0),
    wouldRefreshOnly: Number(item.would_refresh_only ?? item.wouldRefreshOnly ?? 0),
    wouldSkip: Number(item.would_skip ?? item.wouldSkip ?? 0),
    changedFieldNames: Array.isArray(item.changed_field_names)
      ? item.changed_field_names
      : (Array.isArray(item.changedFieldNames) ? item.changedFieldNames : []),
    duplicateCheckPassed: Boolean(item.duplicate_check_passed ?? item.duplicateCheckPassed),
    fieldWhitelistVerified: Boolean(item.field_whitelist_verified ?? item.fieldWhitelistVerified),
    backupRequired: item.backup_required !== false && item.backupRequired !== false,
    permissionRequired: item.permission_required !== false && item.permissionRequired !== false,
    auditRequired: item.audit_required !== false && item.auditRequired !== false,
    operationAuditRowsPlanned: item.operation_audit_rows_planned !== false && item.operationAuditRowsPlanned !== false,
    businessMessage: item.business_message || item.businessMessage || '只读证据已整理，等待人工审核。',
    nextAction: item.next_action || item.nextAction || 'manual_review_required',
  }));
  return {
    phase: data.phase || 'ERP-Batch-1J',
    status: data.status || 'readonly_evidence_api_ready',
    businessMessage: data.business_message || data.businessMessage || '批量同步只读证据已整理，本次不会写入商品或订单。',
    skipReason: data.skip_reason || data.skipReason || null,
    evidenceCount: Number(data.evidence_count ?? data.evidenceCount ?? items.length),
    maxItems: Number(data.max_items ?? data.maxItems ?? 10),
    items,
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    operationAuditRowsPlanned: Boolean(data.operation_audit_rows_planned ?? data.operationAuditRowsPlanned),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function adaptBatchApprovalAuditEvidenceResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-1S',
    status: data.status || 'blocked',
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    evidenceCount: Number(data.evidence_count ?? data.evidenceCount ?? 0),
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    requiredActions: Array.isArray(data.required_actions) ? data.required_actions : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    missingAuditPlanFlags: Array.isArray(data.missing_audit_plan_flags) ? data.missing_audit_plan_flags : (Array.isArray(data.missingAuditPlanFlags) ? data.missingAuditPlanFlags : []),
    manualApprovalPlanned: Boolean(data.manual_approval_planned ?? data.manualApprovalPlanned),
    permissionEvidencePlanned: Boolean(data.permission_evidence_planned ?? data.permissionEvidencePlanned),
    backupEvidenceRequired: data.backup_evidence_required !== false && data.backupEvidenceRequired !== false,
    rollbackEvidenceRequired: data.rollback_evidence_required !== false && data.rollbackEvidenceRequired !== false,
    postWriteReadbackRequired: data.post_write_readback_required !== false && data.postWriteReadbackRequired !== false,
    sensitiveScanRequired: data.sensitive_scan_required !== false && data.sensitiveScanRequired !== false,
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    operationAuditRowsPlanned: data.operation_audit_rows_planned !== false && data.operationAuditRowsPlanned !== false,
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    routePath: data.route_path || data.routePath || data.route_path_planned || data.routePathPlanned || '',
  };
}

function adaptBatchApprovalDecisionReadonlyResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-2L',
    status: data.status || 'blocked',
    decisionStatus: data.decision_status || data.decisionStatus || 'blocked',
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    evidenceCount: Number(data.evidence_count ?? data.evidenceCount ?? 0),
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    requiredActions: Array.isArray(data.required_actions) ? data.required_actions : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    requiredDecisionFlags: Array.isArray(data.required_decision_flags)
      ? data.required_decision_flags
      : (Array.isArray(data.requiredDecisionFlags) ? data.requiredDecisionFlags : []),
    missingDecisionFlags: Array.isArray(data.missing_decision_flags)
      ? data.missing_decision_flags
      : (Array.isArray(data.missingDecisionFlags) ? data.missingDecisionFlags : []),
    requiredApiFlags: Array.isArray(data.required_api_flags)
      ? data.required_api_flags
      : (Array.isArray(data.requiredApiFlags) ? data.requiredApiFlags : []),
    missingApiFlags: Array.isArray(data.missing_api_flags)
      ? data.missing_api_flags
      : (Array.isArray(data.missingApiFlags) ? data.missingApiFlags : []),
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    decisionRecordPlanned: Boolean(data.decision_record_planned ?? data.decisionRecordPlanned),
    backupManifestVerified: Boolean(data.backup_manifest_verified ?? data.backupManifestVerified),
    rollbackReportReady: Boolean(data.rollback_report_ready ?? data.rollbackReportReady),
    permissionGateVerified: Boolean(data.permission_gate_verified ?? data.permissionGateVerified),
    readonlyEvidenceFresh: Boolean(data.readonly_evidence_fresh ?? data.readonlyEvidenceFresh),
    fieldWhitelistVerified: Boolean(data.field_whitelist_verified ?? data.fieldWhitelistVerified),
    duplicateCheckPassed: Boolean(data.duplicate_check_passed ?? data.duplicateCheckPassed),
    sensitiveScanPassed: Boolean(data.sensitive_scan_passed ?? data.sensitiveScanPassed),
    auditCorrelationPlanned: Boolean(data.audit_correlation_planned ?? data.auditCorrelationPlanned),
    operationAuditRowsPlanned: data.operation_audit_rows_planned !== false && data.operationAuditRowsPlanned !== false,
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    routePath: data.route_path || data.routePath || data.route_path_planned || data.routePathPlanned || '',
  };
}

function adaptBatchApprovalDecisionAuditLinkageReadonlyResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-2U',
    status: data.status || 'blocked',
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    auditLinkageReady: Boolean(data.audit_linkage_ready ?? data.auditLinkageReady),
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    requiredActions: Array.isArray(data.required_actions) ? data.required_actions : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    requiredLinkageFlags: Array.isArray(data.required_linkage_flags)
      ? data.required_linkage_flags
      : (Array.isArray(data.requiredLinkageFlags) ? data.requiredLinkageFlags : []),
    missingLinkageFlags: Array.isArray(data.missing_linkage_flags)
      ? data.missing_linkage_flags
      : (Array.isArray(data.missingLinkageFlags) ? data.missingLinkageFlags : []),
    requiredApiFlags: Array.isArray(data.required_api_flags)
      ? data.required_api_flags
      : (Array.isArray(data.requiredApiFlags) ? data.requiredApiFlags : []),
    missingApiFlags: Array.isArray(data.missing_api_flags)
      ? data.missing_api_flags
      : (Array.isArray(data.missingApiFlags) ? data.missingApiFlags : []),
    approvalDecisionIdPlanned: Boolean(data.approval_decision_id_planned ?? data.approvalDecisionIdPlanned),
    readonlyEvidenceHashPlanned: Boolean(data.readonly_evidence_hash_planned ?? data.readonlyEvidenceHashPlanned),
    backupManifestReferencePlanned: Boolean(data.backup_manifest_reference_planned ?? data.backupManifestReferencePlanned),
    permissionEvidenceReferencePlanned: Boolean(data.permission_evidence_reference_planned ?? data.permissionEvidenceReferencePlanned),
    sensitiveScanReferencePlanned: Boolean(data.sensitive_scan_reference_planned ?? data.sensitiveScanReferencePlanned),
    readbackResultReferencePlanned: Boolean(data.readback_result_reference_planned ?? data.readbackResultReferencePlanned),
    rollbackReportReferencePlanned: Boolean(data.rollback_report_reference_planned ?? data.rollbackReportReferencePlanned),
    operatorIdentityHashPlanned: Boolean(data.operator_identity_hash_planned ?? data.operatorIdentityHashPlanned),
    storeScopePlanned: Boolean(data.store_scope_planned ?? data.storeScopePlanned),
    auditCorrelationIdPlanned: Boolean(data.audit_correlation_id_planned ?? data.auditCorrelationIdPlanned),
    appendOnlyAuditRowsPlanned: Boolean(data.append_only_audit_rows_planned ?? data.appendOnlyAuditRowsPlanned),
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    operationAuditRowsPlanned: data.operation_audit_rows_planned !== false && data.operationAuditRowsPlanned !== false,
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    routePath: data.route_path || data.routePath || data.route_path_planned || data.routePathPlanned || '',
  };
}

function adaptFormalBatchExecutionPreflightReadonlyResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-3A',
    status: data.status || 'blocked',
    preflightStatus: data.preflight_status || data.preflightStatus || 'blocked',
    preflightReady: Boolean(data.preflight_ready ?? data.preflightReady),
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    executionApprovalCount: Number(data.execution_approval_count ?? data.executionApprovalCount ?? 0),
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    targets: Array.isArray(data.targets) ? data.targets : [],
    requiredActions: Array.isArray(data.required_actions)
      ? data.required_actions
      : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    requiredPreflightFlags: Array.isArray(data.required_preflight_flags)
      ? data.required_preflight_flags
      : (Array.isArray(data.requiredPreflightFlags) ? data.requiredPreflightFlags : []),
    missingPreflightFlags: Array.isArray(data.missing_preflight_flags)
      ? data.missing_preflight_flags
      : (Array.isArray(data.missingPreflightFlags) ? data.missingPreflightFlags : []),
    routePath: data.route_path || data.routePath || '/api/v1/batch/execution-preflight/readonly-check',
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    batchExecutionEnabled: Boolean(data.batch_execution_enabled ?? data.batchExecutionEnabled),
    writeEndpointEnabled: Boolean(data.write_endpoint_enabled ?? data.writeEndpointEnabled),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformOrderWritesEnabled: Boolean(data.platform_order_writes_enabled ?? data.platformOrderWritesEnabled),
    platformProductWritesEnabled: Boolean(data.platform_product_writes_enabled ?? data.platformProductWritesEnabled),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
  };
}

function adaptFormalBatchExecutionDryRunReadonlyResult(data = {}) {
  const candidateSummaries = Array.isArray(data.candidate_summaries)
    ? data.candidate_summaries
    : (Array.isArray(data.candidateSummaries) ? data.candidateSummaries : []);
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-3D',
    status: data.status || 'blocked',
    dryRunStatus: data.dry_run_status || data.dryRunStatus || 'blocked',
    dryRunReady: Boolean(data.dry_run_ready ?? data.dryRunReady),
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    targets: Array.isArray(data.targets) ? data.targets : [],
    requiredDryRunFlags: Array.isArray(data.required_dry_run_flags)
      ? data.required_dry_run_flags
      : (Array.isArray(data.requiredDryRunFlags) ? data.requiredDryRunFlags : []),
    missingDryRunFlags: Array.isArray(data.missing_dry_run_flags)
      ? data.missing_dry_run_flags
      : (Array.isArray(data.missingDryRunFlags) ? data.missingDryRunFlags : []),
    candidateSummaryCount: Number(data.candidate_summary_count ?? data.candidateSummaryCount ?? candidateSummaries.length),
    totalCandidateCount: Number(data.total_candidate_count ?? data.totalCandidateCount ?? 0),
    totalWouldCreate: Number(data.total_would_create ?? data.totalWouldCreate ?? 0),
    totalWouldUpdate: Number(data.total_would_update ?? data.totalWouldUpdate ?? 0),
    totalWouldRefreshOnly: Number(data.total_would_refresh_only ?? data.totalWouldRefreshOnly ?? 0),
    totalWouldSkip: Number(data.total_would_skip ?? data.totalWouldSkip ?? 0),
    changedFields: Array.isArray(data.changed_fields)
      ? data.changed_fields
      : (Array.isArray(data.changedFields) ? data.changedFields : []),
    candidateSummaries: candidateSummaries.map((item = {}) => ({
      syncKind: item.sync_kind || item.syncKind || '',
      target: item.target || '',
      storeIds: Array.isArray(item.store_ids) ? item.store_ids : (Array.isArray(item.storeIds) ? item.storeIds : []),
      candidateCount: Number(item.candidate_count ?? item.candidateCount ?? 0),
      wouldCreate: Number(item.would_create ?? item.wouldCreate ?? 0),
      wouldUpdate: Number(item.would_update ?? item.wouldUpdate ?? 0),
      wouldRefreshOnly: Number(item.would_refresh_only ?? item.wouldRefreshOnly ?? 0),
      wouldSkip: Number(item.would_skip ?? item.wouldSkip ?? 0),
      changedFields: Array.isArray(item.changed_fields)
        ? item.changed_fields
        : (Array.isArray(item.changedFields) ? item.changedFields : []),
    })),
    routePath: data.route_path || data.routePath || '/api/v1/batch/execution-dry-run/readonly-check',
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    dryRunOnly: data.dry_run_only !== false && data.dryRunOnly !== false,
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    batchExecutionEnabled: Boolean(data.batch_execution_enabled ?? data.batchExecutionEnabled),
    writeEndpointEnabled: Boolean(data.write_endpoint_enabled ?? data.writeEndpointEnabled),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformOrderWritesEnabled: Boolean(data.platform_order_writes_enabled ?? data.platformOrderWritesEnabled),
    platformProductWritesEnabled: Boolean(data.platform_product_writes_enabled ?? data.platformProductWritesEnabled),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    shipmentWriteEnabled: Boolean(data.shipment_write_enabled ?? data.shipmentWriteEnabled),
    cancelWriteEnabled: Boolean(data.cancel_write_enabled ?? data.cancelWriteEnabled),
    returnWriteEnabled: Boolean(data.return_write_enabled ?? data.returnWriteEnabled),
    exchangeWriteEnabled: Boolean(data.exchange_write_enabled ?? data.exchangeWriteEnabled),
  };
}

function adaptFormalBatchExecutionApprovalReadonlyResult(data = {}) {
  const candidateSummaries = Array.isArray(data.candidate_summaries)
    ? data.candidate_summaries
    : (Array.isArray(data.candidateSummaries) ? data.candidateSummaries : []);
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-3J',
    status: data.status || 'blocked',
    approvalStatus: data.approval_status || data.approvalStatus || 'blocked',
    finalApprovalReady: Boolean(data.final_approval_ready ?? data.finalApprovalReady),
    privateHelperOnly: Boolean(data.private_helper_only ?? data.privateHelperOnly),
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    targets: Array.isArray(data.targets) ? data.targets : [],
    requiredActions: Array.isArray(data.required_actions)
      ? data.required_actions
      : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    requiredFinalApprovalFlags: Array.isArray(data.required_final_approval_flags)
      ? data.required_final_approval_flags
      : (Array.isArray(data.requiredFinalApprovalFlags) ? data.requiredFinalApprovalFlags : []),
    missingFinalApprovalFlags: Array.isArray(data.missing_final_approval_flags)
      ? data.missing_final_approval_flags
      : (Array.isArray(data.missingFinalApprovalFlags) ? data.missingFinalApprovalFlags : []),
    candidateSummaryCount: Number(data.candidate_summary_count ?? data.candidateSummaryCount ?? candidateSummaries.length),
    totalCandidateCount: Number(data.total_candidate_count ?? data.totalCandidateCount ?? 0),
    totalWouldCreate: Number(data.total_would_create ?? data.totalWouldCreate ?? 0),
    totalWouldUpdate: Number(data.total_would_update ?? data.totalWouldUpdate ?? 0),
    totalWouldRefreshOnly: Number(data.total_would_refresh_only ?? data.totalWouldRefreshOnly ?? 0),
    totalWouldSkip: Number(data.total_would_skip ?? data.totalWouldSkip ?? 0),
    changedFields: Array.isArray(data.changed_fields)
      ? data.changed_fields
      : (Array.isArray(data.changedFields) ? data.changedFields : []),
    candidateSummaries: candidateSummaries.map((item = {}) => ({
      syncKind: item.sync_kind || item.syncKind || '',
      target: item.target || '',
      storeIds: Array.isArray(item.store_ids) ? item.store_ids : (Array.isArray(item.storeIds) ? item.storeIds : []),
      candidateCount: Number(item.candidate_count ?? item.candidateCount ?? 0),
      wouldCreate: Number(item.would_create ?? item.wouldCreate ?? 0),
      wouldUpdate: Number(item.would_update ?? item.wouldUpdate ?? 0),
      wouldRefreshOnly: Number(item.would_refresh_only ?? item.wouldRefreshOnly ?? 0),
      wouldSkip: Number(item.would_skip ?? item.wouldSkip ?? 0),
      changedFields: Array.isArray(item.changed_fields)
        ? item.changed_fields
        : (Array.isArray(item.changedFields) ? item.changedFields : []),
    })),
    routePath: data.route_path || data.routePath || '/api/v1/batch/execution-approval/readonly-check',
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    batchExecutionEnabled: Boolean(data.batch_execution_enabled ?? data.batchExecutionEnabled),
    writeEndpointEnabled: Boolean(data.write_endpoint_enabled ?? data.writeEndpointEnabled),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformOrderWritesEnabled: Boolean(data.platform_order_writes_enabled ?? data.platformOrderWritesEnabled),
    platformProductWritesEnabled: Boolean(data.platform_product_writes_enabled ?? data.platformProductWritesEnabled),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    shipmentWriteEnabled: Boolean(data.shipment_write_enabled ?? data.shipmentWriteEnabled),
    cancelWriteEnabled: Boolean(data.cancel_write_enabled ?? data.cancelWriteEnabled),
    returnWriteEnabled: Boolean(data.return_write_enabled ?? data.returnWriteEnabled),
    exchangeWriteEnabled: Boolean(data.exchange_write_enabled ?? data.exchangeWriteEnabled),
  };
}

function adaptFormalBatchExecutionWriteBoundaryReadonlyResult(data = {}) {
  const candidateSummaries = Array.isArray(data.candidate_summaries)
    ? data.candidate_summaries
    : (Array.isArray(data.candidateSummaries) ? data.candidateSummaries : []);
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-4C',
    status: data.status || 'blocked',
    approvalStatus: data.approval_status || data.approvalStatus || 'blocked',
    writeBoundaryPlanReady: Boolean(data.write_boundary_plan_ready ?? data.writeBoundaryPlanReady),
    readonlyApiMockGate: Boolean(data.readonly_api_mock_gate ?? data.readonlyApiMockGate),
    privateHelperOnly: Boolean(data.private_helper_only ?? data.privateHelperOnly),
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    targets: Array.isArray(data.targets) ? data.targets : [],
    requiredActions: Array.isArray(data.required_actions)
      ? data.required_actions
      : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    requiredWriteBoundaryFlags: Array.isArray(data.required_write_boundary_flags)
      ? data.required_write_boundary_flags
      : (Array.isArray(data.requiredWriteBoundaryFlags) ? data.requiredWriteBoundaryFlags : []),
    missingWriteBoundaryFlags: Array.isArray(data.missing_write_boundary_flags)
      ? data.missing_write_boundary_flags
      : (Array.isArray(data.missingWriteBoundaryFlags) ? data.missingWriteBoundaryFlags : []),
    requiredApiFlags: Array.isArray(data.required_api_flags)
      ? data.required_api_flags
      : (Array.isArray(data.requiredApiFlags) ? data.requiredApiFlags : []),
    missingApiFlags: Array.isArray(data.missing_api_flags)
      ? data.missing_api_flags
      : (Array.isArray(data.missingApiFlags) ? data.missingApiFlags : []),
    candidateSummaryCount: Number(data.candidate_summary_count ?? data.candidateSummaryCount ?? candidateSummaries.length),
    totalCandidateCount: Number(data.total_candidate_count ?? data.totalCandidateCount ?? 0),
    totalWouldCreate: Number(data.total_would_create ?? data.totalWouldCreate ?? 0),
    totalWouldUpdate: Number(data.total_would_update ?? data.totalWouldUpdate ?? 0),
    totalWouldRefreshOnly: Number(data.total_would_refresh_only ?? data.totalWouldRefreshOnly ?? 0),
    totalWouldSkip: Number(data.total_would_skip ?? data.totalWouldSkip ?? 0),
    maxBatchSize: Number(data.max_batch_size ?? data.maxBatchSize ?? 0),
    changedFields: Array.isArray(data.changed_fields)
      ? data.changed_fields
      : (Array.isArray(data.changedFields) ? data.changedFields : []),
    candidateSummaries: candidateSummaries.map((item = {}) => ({
      syncKind: item.sync_kind || item.syncKind || '',
      target: item.target || '',
      storeIds: Array.isArray(item.store_ids) ? item.store_ids : (Array.isArray(item.storeIds) ? item.storeIds : []),
      candidateCount: Number(item.candidate_count ?? item.candidateCount ?? 0),
      wouldCreate: Number(item.would_create ?? item.wouldCreate ?? 0),
      wouldUpdate: Number(item.would_update ?? item.wouldUpdate ?? 0),
      wouldRefreshOnly: Number(item.would_refresh_only ?? item.wouldRefreshOnly ?? 0),
      wouldSkip: Number(item.would_skip ?? item.wouldSkip ?? 0),
      changedFields: Array.isArray(item.changed_fields)
        ? item.changed_fields
        : (Array.isArray(item.changedFields) ? item.changedFields : []),
    })),
    routePath: data.route_path || data.routePath || '/api/v1/batch/execution-write-boundary/readonly-check',
    routePathPlanned: data.route_path_planned || data.routePathPlanned || '/api/v1/batch/execution-write-boundary/readonly-check',
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    batchExecutionEnabled: Boolean(data.batch_execution_enabled ?? data.batchExecutionEnabled),
    writeEndpointEnabled: Boolean(data.write_endpoint_enabled ?? data.writeEndpointEnabled),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformOrderWritesEnabled: Boolean(data.platform_order_writes_enabled ?? data.platformOrderWritesEnabled),
    platformProductWritesEnabled: Boolean(data.platform_product_writes_enabled ?? data.platformProductWritesEnabled),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    shipmentWriteEnabled: Boolean(data.shipment_write_enabled ?? data.shipmentWriteEnabled),
    cancelWriteEnabled: Boolean(data.cancel_write_enabled ?? data.cancelWriteEnabled),
    returnWriteEnabled: Boolean(data.return_write_enabled ?? data.returnWriteEnabled),
    exchangeWriteEnabled: Boolean(data.exchange_write_enabled ?? data.exchangeWriteEnabled),
  };
}

function adaptFormalBatchPreExecutionRefreshReadonlyResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'ERP-Batch-4G',
    status: data.status || 'blocked',
    approvalStatus: data.approval_status || data.approvalStatus || 'blocked',
    preExecutionBackupAuditRefreshGateReady: Boolean(
      data.pre_execution_backup_audit_refresh_gate_ready
      ?? data.preExecutionBackupAuditRefreshGateReady,
    ),
    backupRefreshVerified: Boolean(data.backup_refresh_verified ?? data.backupRefreshVerified),
    auditRefreshVerified: Boolean(data.audit_refresh_verified ?? data.auditRefreshVerified),
    readonlyApiMockGate: Boolean(data.readonly_api_mock_gate ?? data.readonlyApiMockGate),
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    requiredBackupFlags: Array.isArray(data.required_backup_flags)
      ? data.required_backup_flags
      : (Array.isArray(data.requiredBackupFlags) ? data.requiredBackupFlags : []),
    missingBackupFlags: Array.isArray(data.missing_backup_flags)
      ? data.missing_backup_flags
      : (Array.isArray(data.missingBackupFlags) ? data.missingBackupFlags : []),
    requiredAuditFlags: Array.isArray(data.required_audit_flags)
      ? data.required_audit_flags
      : (Array.isArray(data.requiredAuditFlags) ? data.requiredAuditFlags : []),
    missingAuditFlags: Array.isArray(data.missing_audit_flags)
      ? data.missing_audit_flags
      : (Array.isArray(data.missingAuditFlags) ? data.missingAuditFlags : []),
    requiredApiFlags: Array.isArray(data.required_api_flags)
      ? data.required_api_flags
      : (Array.isArray(data.requiredApiFlags) ? data.requiredApiFlags : []),
    missingApiFlags: Array.isArray(data.missing_api_flags)
      ? data.missing_api_flags
      : (Array.isArray(data.missingApiFlags) ? data.missingApiFlags : []),
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    syncKinds: Array.isArray(data.sync_kinds) ? data.sync_kinds : (Array.isArray(data.syncKinds) ? data.syncKinds : []),
    targets: Array.isArray(data.targets) ? data.targets : [],
    requiredActions: Array.isArray(data.required_actions)
      ? data.required_actions
      : (Array.isArray(data.requiredActions) ? data.requiredActions : []),
    candidateSummaryCount: Number(data.candidate_summary_count ?? data.candidateSummaryCount ?? 0),
    totalCandidateCount: Number(data.total_candidate_count ?? data.totalCandidateCount ?? 0),
    backupSha256Abbrev: data.backup_sha256_abbrev || data.backupSha256Abbrev || null,
    auditCorrelationReference: data.audit_correlation_reference || data.auditCorrelationReference || null,
    routePath: data.route_path || data.routePath || '/api/v1/batch/pre-execution-refresh/readonly-check',
    routePathPlanned: data.route_path_planned || data.routePathPlanned || '/api/v1/batch/pre-execution-refresh/readonly-check',
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    batchExecutionEnabled: Boolean(data.batch_execution_enabled ?? data.batchExecutionEnabled),
    writeEndpointEnabled: Boolean(data.write_endpoint_enabled ?? data.writeEndpointEnabled),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformOrderWritesEnabled: Boolean(data.platform_order_writes_enabled ?? data.platformOrderWritesEnabled),
    platformProductWritesEnabled: Boolean(data.platform_product_writes_enabled ?? data.platformProductWritesEnabled),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    shipmentWriteEnabled: Boolean(data.shipment_write_enabled ?? data.shipmentWriteEnabled),
    cancelWriteEnabled: Boolean(data.cancel_write_enabled ?? data.cancelWriteEnabled),
    returnWriteEnabled: Boolean(data.return_write_enabled ?? data.returnWriteEnabled),
    exchangeWriteEnabled: Boolean(data.exchange_write_enabled ?? data.exchangeWriteEnabled),
  };
}

function adaptNaverBatchExecutionApprovalReadonlyResult(data = {}, kind = 'order') {
  const isProduct = kind === 'product';
  return {
    ...data,
    phase: data.phase || (isProduct ? 'Naver-Product-Batch-2L' : 'Naver-Order-Batch-3C'),
    status: data.status || 'blocked',
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    storeIds: Array.isArray(data.store_ids) ? data.store_ids : (Array.isArray(data.storeIds) ? data.storeIds : []),
    candidateCount: Number(data.candidate_count ?? data.candidateCount ?? 0),
    batchSize: Number(data.batch_size ?? data.batchSize ?? 0),
    productBatchExecutionApprovalReady: Boolean(
      data.product_batch_execution_approval_ready ?? data.productBatchExecutionApprovalReady,
    ),
    orderBatchExecutionApprovalReady: Boolean(
      data.order_batch_execution_approval_ready ?? data.orderBatchExecutionApprovalReady,
    ),
    requiredExecutionFlags: Array.isArray(data.required_execution_flags)
      ? data.required_execution_flags
      : (Array.isArray(data.requiredExecutionFlags) ? data.requiredExecutionFlags : []),
    missingExecutionFlags: Array.isArray(data.missing_execution_flags)
      ? data.missing_execution_flags
      : (Array.isArray(data.missingExecutionFlags) ? data.missingExecutionFlags : []),
    requiredApiFlags: Array.isArray(data.required_api_flags)
      ? data.required_api_flags
      : (Array.isArray(data.requiredApiFlags) ? data.requiredApiFlags : []),
    missingApiFlags: Array.isArray(data.missing_api_flags)
      ? data.missing_api_flags
      : (Array.isArray(data.missingApiFlags) ? data.missingApiFlags : []),
    permissionVerified: Boolean(data.permission_verified ?? data.permissionVerified),
    approvalRoleVerified: Boolean(data.approval_role_verified ?? data.approvalRoleVerified),
    backupEvidenceVerified: Boolean(data.backup_evidence_verified ?? data.backupEvidenceVerified),
    readonlyEvidenceVerified: Boolean(data.readonly_evidence_verified ?? data.readonlyEvidenceVerified),
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    routePath: data.route_path || data.routePath || data.route_path_planned || data.routePathPlanned || (
      isProduct
        ? '/api/v1/batch/naver/products/execution-approval/readonly-check'
        : '/api/v1/batch/naver/orders/execution-approval/readonly-check'
    ),
    executionApproved: Boolean(data.execution_approved ?? data.executionApproved),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    timelineEventsWritten: Boolean(data.timeline_events_written ?? data.timelineEventsWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    formalOrderSyncOpen: Boolean(data.formal_order_sync_open ?? data.formalOrderSyncOpen),
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    platformOrderWritesEnabled: Boolean(data.platform_order_writes_enabled ?? data.platformOrderWritesEnabled),
    platformProductWritesEnabled: Boolean(data.platform_product_writes_enabled ?? data.platformProductWritesEnabled),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    shipmentWriteEnabled: Boolean(data.shipment_write_enabled ?? data.shipmentWriteEnabled),
    cancelWriteEnabled: Boolean(data.cancel_write_enabled ?? data.cancelWriteEnabled),
    returnWriteEnabled: Boolean(data.return_write_enabled ?? data.returnWriteEnabled),
    exchangeWriteEnabled: Boolean(data.exchange_write_enabled ?? data.exchangeWriteEnabled),
  };
}

function adaptProductRollbackReadonlyReportResult(data = {}) {
  return {
    ...data,
    phase: data.phase || 'Naver-Product-Batch-1R',
    status: data.status || 'blocked',
    skipReason: data.skip_reason || data.skipReason || null,
    businessMessage: data.business_message || data.businessMessage || '',
    nextAction: data.next_action || data.nextAction || '',
    reportReady: Boolean(data.report_ready ?? data.reportReady),
    reportSections: Array.isArray(data.report_sections) ? data.report_sections : (Array.isArray(data.reportSections) ? data.reportSections : []),
    rollbackDrillReady: Boolean(data.rollback_drill_ready ?? data.rollbackDrillReady),
    backupEvidenceVerified: Boolean(data.backup_evidence_verified ?? data.backupEvidenceVerified),
    updatedCount: Number(data.updated_count ?? data.updatedCount ?? 0),
    createdCount: Number(data.created_count ?? data.createdCount ?? 0),
    stockOnlyWriteVerified: Boolean(data.stock_only_write_verified ?? data.stockOnlyWriteVerified),
    temporaryRestoreRequired: data.temporary_restore_required !== false && data.temporaryRestoreRequired !== false,
    backendRouteImplemented: Boolean(data.backend_route_implemented ?? data.backendRouteImplemented),
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled ?? data.publicEndpointEnabled),
    realRestoreExecuted: Boolean(data.real_restore_executed ?? data.realRestoreExecuted),
    rollbackExecuted: Boolean(data.rollback_executed ?? data.rollbackExecuted),
    productionDbTouched: Boolean(data.production_db_touched ?? data.productionDbTouched),
    realApiCalled: Boolean(data.real_api_called ?? data.realApiCalled),
    realDatabaseWritten: Boolean(data.real_database_written ?? data.realDatabaseWritten),
    productsWritten: Boolean(data.products_written ?? data.productsWritten),
    ordersWritten: Boolean(data.orders_written ?? data.ordersWritten),
    syncLogWritten: Boolean(data.sync_log_written ?? data.syncLogWritten),
    capabilityTestedSuccessWritten: Boolean(data.capability_tested_success_written ?? data.capabilityTestedSuccessWritten),
    operationAuditRowsWritten: Boolean(data.operation_audit_rows_written ?? data.operationAuditRowsWritten),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    secretsSaved: Boolean(data.secrets_saved ?? data.secretsSaved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false && data.privacyFieldsRedacted !== false,
    formalProductSyncOpen: Boolean(data.formal_product_sync_open ?? data.formalProductSyncOpen),
    formalSyncOpen: Boolean(data.formal_sync_open ?? data.formalSyncOpen),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    routePath: data.route_path || data.routePath || data.route_path_planned || data.routePathPlanned || '',
  };
}

function mockBatchReadonlyEvidence(payload = {}) {
  const rawItems = Array.isArray(payload.evidence_items || payload.evidenceItems)
    ? (payload.evidence_items || payload.evidenceItems)
    : [];
  const items = rawItems.map((item, index) => ({
    evidence_id: item.evidence_id || `mock-evidence-${index + 1}`,
    store_id: Number(item.store_id ?? item.storeId ?? 0),
    platform: item.platform || 'naver',
    sync_kind: item.sync_kind || item.syncKind || '',
    target: String(item.sync_kind || item.syncKind || '').includes('order') ? 'orders' : 'products',
    window_label: item.window_label || item.windowLabel || 'mock 只读窗口',
    candidate_count: Number(item.candidate_count ?? item.candidateCount ?? 0),
    would_create: Number(item.would_create ?? item.wouldCreate ?? 0),
    would_update: Number(item.would_update ?? item.wouldUpdate ?? 0),
    would_refresh_only: Number(item.would_refresh_only ?? item.wouldRefreshOnly ?? 0),
    would_skip: Number(item.would_skip ?? item.wouldSkip ?? 0),
    changed_field_names: Array.isArray(item.changed_field_names)
      ? item.changed_field_names
      : (Array.isArray(item.changedFieldNames) ? item.changedFieldNames : []),
    duplicate_check_passed: item.duplicate_check_passed !== false && item.duplicateCheckPassed !== false,
    field_whitelist_verified: item.field_whitelist_verified !== false && item.fieldWhitelistVerified !== false,
    backup_required: true,
    permission_required: true,
    audit_required: true,
    operation_audit_rows_planned: true,
    business_message: item.business_message || item.businessMessage || 'mock 只读证据已整理。',
    next_action: item.next_action || item.nextAction || 'manual_review_required',
  }));
  return adaptBatchReadonlyEvidenceResult({
    phase: 'ERP-Batch-1J',
    status: 'readonly_evidence_api_ready',
    business_message: 'mock 批量同步只读证据已整理，本次不会写入商品或订单。',
    evidence_count: items.length,
    max_items: Number(payload.max_items ?? payload.maxItems ?? 10),
    items,
    public_endpoint_enabled: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    operation_audit_rows_written: false,
    operation_audit_rows_planned: true,
    timeline_events_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_writes_enabled: false,
  });
}

function mockBatchApprovalAuditEvidence(payload = {}) {
  const evidence = payload.readonly_evidence || payload.readonlyEvidence || {};
  const items = Array.isArray(evidence.items) ? evidence.items : [];
  const hasSensitiveMarker = JSON.stringify(payload).toLowerCase().includes('productorderid')
    || JSON.stringify(payload).toLowerCase().includes('rawresponse');
  if (hasSensitiveMarker) {
    return adaptBatchApprovalAuditEvidenceResult({
      phase: 'ERP-Batch-1S',
      status: 'blocked',
      skip_reason: 'batch_approval_audit_sensitive_field_blocked',
      operation_audit_rows_written: false,
      real_database_written: false,
      orders_written: false,
      products_written: false,
      sync_log_written: false,
      capability_tested_success_written: false,
      formal_sync_open: false,
      public_endpoint_enabled: false,
      privacy_fields_redacted: true,
    });
  }
  return adaptBatchApprovalAuditEvidenceResult({
    phase: 'ERP-Batch-1S',
    status: 'batch_approval_audit_evidence_ready',
    business_message: 'mock 批量审批审计证据已整理，仅用于页面只读展示。',
    next_action: '继续人工审核备份、权限、回读、敏感扫描和回滚证据。',
    evidence_count: items.length,
    store_ids: [...new Set(items.map((item) => Number(item.storeId ?? item.store_id)).filter(Boolean))],
    sync_kinds: [...new Set(items.map((item) => item.syncKind || item.sync_kind).filter(Boolean))],
    required_actions: ['orders.batch_sync_write', 'products.batch_sync_write'],
    manual_approval_planned: true,
    permission_evidence_planned: true,
    backup_evidence_required: true,
    rollback_evidence_required: true,
    post_write_readback_required: true,
    sensitive_scan_required: true,
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    operation_audit_rows_planned: true,
    operation_audit_rows_written: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_writes_enabled: false,
    route_path: '/api/v1/batch/approval-audit-evidence',
  });
}

function mockBatchApprovalDecisionReadonly(payload = {}) {
  const readonlyEvidence = payload.readonly_evidence || payload.readonlyEvidence || {};
  const approvalAuditEvidence = payload.approval_audit_evidence || payload.approvalAuditEvidence || {};
  const decisionContext = payload.decision_context || payload.decisionContext || {};
  const hasSensitiveMarker = JSON.stringify(payload).toLowerCase().includes('productorderid')
    || JSON.stringify(payload).toLowerCase().includes('rawresponse');
  if (hasSensitiveMarker) {
    return adaptBatchApprovalDecisionReadonlyResult({
      phase: 'ERP-Batch-2N',
      status: 'blocked',
      decision_status: 'blocked',
      skip_reason: 'formal_batch_decision_sensitive_field_blocked',
      execution_approved: false,
      operation_audit_rows_written: false,
      real_database_written: false,
      orders_written: false,
      products_written: false,
      sync_log_written: false,
      capability_tested_success_written: false,
      formal_sync_open: false,
      public_endpoint_enabled: false,
      privacy_fields_redacted: true,
    });
  }
  const items = Array.isArray(readonlyEvidence.items) ? readonlyEvidence.items : [];
  const storeIds = [...new Set(items.map((item) => Number(item.store_id ?? item.storeId)).filter(Boolean))];
  const syncKinds = [...new Set(items.map((item) => item.sync_kind || item.syncKind).filter(Boolean))];
  const requiredActions = Array.isArray(approvalAuditEvidence.required_actions)
    ? approvalAuditEvidence.required_actions
    : (Array.isArray(approvalAuditEvidence.requiredActions) ? approvalAuditEvidence.requiredActions : []);
  return adaptBatchApprovalDecisionReadonlyResult({
    phase: 'ERP-Batch-2N',
    status: 'formal_batch_approval_decision_readonly_api_ready',
    decision_status: 'ready_for_local_readonly_review',
    business_message: '批量同步审批决策只读检查已完成。当前只展示人工复核材料，不批准执行，也不写入商品或订单。',
    next_action: '继续由管理员复核备份、权限、回读、审计和敏感扫描证据；执行写入必须另开阶段。',
    evidence_count: Number(readonlyEvidence.evidence_count ?? readonlyEvidence.evidenceCount ?? items.length),
    store_ids: storeIds.length ? storeIds : (Array.isArray(decisionContext.store_ids) ? decisionContext.store_ids : []),
    sync_kinds: syncKinds,
    required_actions: requiredActions,
    required_decision_flags: [
      'decision_record_planned',
      'human_approval_required',
      'backup_manifest_verified',
      'rollback_report_ready',
      'permission_gate_verified',
      'readonly_evidence_fresh',
      'field_whitelist_verified',
      'duplicate_check_passed',
      'sensitive_scan_passed',
      'post_write_readback_required',
      'audit_correlation_planned',
      'formal_sync_remains_closed',
    ],
    missing_decision_flags: [],
    required_api_flags: [
      'readonly_api_contract_planned',
      'business_wording_required',
      'technical_details_folded',
      'execution_button_excluded',
      'write_endpoint_excluded',
      'sensitive_fields_hidden_from_main_page',
      'route_requires_separate_implementation',
      'formal_sync_remains_closed',
    ],
    missing_api_flags: [],
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    execution_approved: false,
    decision_record_planned: true,
    backup_manifest_verified: true,
    rollback_report_ready: true,
    permission_gate_verified: true,
    readonly_evidence_fresh: true,
    field_whitelist_verified: true,
    duplicate_check_passed: true,
    sensitive_scan_passed: true,
    audit_correlation_planned: true,
    operation_audit_rows_planned: true,
    operation_audit_rows_written: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_writes_enabled: false,
    route_path: '/api/v1/batch/approval-decision/readonly-check',
  });
}

function mockBatchApprovalDecisionAuditLinkageReadonly(payload = {}) {
  const approvalDecision = payload.approval_decision || payload.approvalDecision || {};
  const auditLinkageContext = payload.audit_linkage_context || payload.auditLinkageContext || {};
  const hasSensitiveMarker = JSON.stringify(payload).toLowerCase().includes('productorderid')
    || JSON.stringify(payload).toLowerCase().includes('rawresponse')
    || JSON.stringify(payload).toLowerCase().includes('authorization');
  if (hasSensitiveMarker) {
    return adaptBatchApprovalDecisionAuditLinkageReadonlyResult({
      phase: 'ERP-Batch-2U',
      status: 'blocked',
      skip_reason: 'approval_decision_audit_linkage_sensitive_field_blocked',
      audit_linkage_ready: false,
      execution_approved: false,
      operation_audit_rows_written: false,
      real_database_written: false,
      orders_written: false,
      products_written: false,
      sync_log_written: false,
      capability_tested_success_written: false,
      formal_sync_open: false,
      public_endpoint_enabled: false,
      privacy_fields_redacted: true,
    });
  }
  const storeIds = Array.isArray(approvalDecision.store_ids)
    ? approvalDecision.store_ids
    : (Array.isArray(approvalDecision.storeIds) ? approvalDecision.storeIds : []);
  const syncKinds = Array.isArray(approvalDecision.sync_kinds)
    ? approvalDecision.sync_kinds
    : (Array.isArray(approvalDecision.syncKinds) ? approvalDecision.syncKinds : []);
  const requiredActions = Array.isArray(approvalDecision.required_actions)
    ? approvalDecision.required_actions
    : (Array.isArray(approvalDecision.requiredActions) ? approvalDecision.requiredActions : []);
  return adaptBatchApprovalDecisionAuditLinkageReadonlyResult({
    phase: 'ERP-Batch-2U',
    status: 'approval_decision_audit_linkage_readonly_api_ready',
    audit_linkage_ready: true,
    business_message: '批量审批决策与审计证据链路已可只读复核；当前不会批准执行，也不会写入审计记录或业务数据。',
    next_action: '继续由管理员复核备份、权限、敏感扫描、回读和回滚证据；任何批量写入仍需单独阶段批准。',
    store_ids: storeIds.length ? storeIds : (Array.isArray(auditLinkageContext.store_ids) ? auditLinkageContext.store_ids : []),
    sync_kinds: syncKinds,
    required_actions: requiredActions,
    required_linkage_flags: [
      'approval_decision_id_planned',
      'readonly_evidence_hash_planned',
      'backup_manifest_reference_planned',
      'permission_evidence_reference_planned',
      'sensitive_scan_reference_planned',
      'readback_result_reference_planned',
      'rollback_report_reference_planned',
      'operator_identity_hash_planned',
      'store_scope_planned',
      'audit_correlation_id_planned',
      'append_only_audit_rows_planned',
      'formal_sync_remains_closed',
    ],
    missing_linkage_flags: [],
    required_api_flags: [
      'readonly_api_contract_planned',
      'business_wording_required',
      'technical_details_folded',
      'execution_button_excluded',
      'write_endpoint_excluded',
      'sensitive_fields_hidden_from_main_page',
      'audit_row_write_excluded',
      'route_requires_separate_implementation',
      'formal_sync_remains_closed',
    ],
    missing_api_flags: [],
    approval_decision_id_planned: true,
    readonly_evidence_hash_planned: true,
    backup_manifest_reference_planned: true,
    permission_evidence_reference_planned: true,
    sensitive_scan_reference_planned: true,
    readback_result_reference_planned: true,
    rollback_report_reference_planned: true,
    operator_identity_hash_planned: true,
    store_scope_planned: true,
    audit_correlation_id_planned: true,
    append_only_audit_rows_planned: true,
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    execution_approved: false,
    operation_audit_rows_planned: true,
    operation_audit_rows_written: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_writes_enabled: false,
    route_path: '/api/v1/batch/approval-decision/audit-linkage/readonly-check',
  });
}

function mockFormalBatchExecutionPreflightReadonly(payload = {}) {
  const hasSensitiveMarker = JSON.stringify(payload).toLowerCase().includes('productorderid')
    || JSON.stringify(payload).toLowerCase().includes('rawresponse')
    || JSON.stringify(payload).toLowerCase().includes('authorization')
    || JSON.stringify(payload).toLowerCase().includes('client_secret');
  if (hasSensitiveMarker) {
    return adaptFormalBatchExecutionPreflightReadonlyResult({
      phase: 'ERP-Batch-3A',
      status: 'blocked',
      preflight_status: 'blocked',
      preflight_ready: false,
      skip_reason: 'formal_batch_execution_preflight_sensitive_field_blocked',
      execution_approved: false,
      batch_execution_enabled: false,
      write_endpoint_enabled: false,
      real_api_called: false,
      real_database_written: false,
      orders_written: false,
      products_written: false,
      operation_audit_rows_written: false,
      raw_response_saved: false,
      privacy_fields_redacted: true,
      formal_sync_open: false,
      platform_writes_enabled: false,
    });
  }
  const approvals = Array.isArray(payload.execution_approvals || payload.executionApprovals)
    ? (payload.execution_approvals || payload.executionApprovals)
    : [];
  const preflightContext = payload.preflight_context || payload.preflightContext || {};
  const requiredFlags = [
    'operator_checklist_reviewed',
    'approval_decision_referenced',
    'audit_linkage_referenced',
    'readonly_evidence_referenced',
    'backup_manifest_referenced',
    'permission_evidence_referenced',
    'rollback_report_referenced',
    'readback_plan_referenced',
    'sensitive_scan_referenced',
    'execution_window_limited',
    'formal_sync_remains_closed',
  ];
  const missingFlags = requiredFlags.filter((flag) => preflightContext[flag] !== true);
  const storeIds = [...new Set(approvals.flatMap((approval) => (
    Array.isArray(approval.store_ids) ? approval.store_ids : (Array.isArray(approval.storeIds) ? approval.storeIds : [])
  )).map(Number).filter(Boolean))];
  const syncKinds = [...new Set(approvals.map((approval) => {
    const status = approval.status || '';
    if (status.includes('product')) return 'naver_product_batch';
    if (status.includes('order')) return 'naver_order_batch';
    return '';
  }).filter(Boolean))];
  const targets = [...new Set(syncKinds.map((kind) => (kind.includes('product') ? 'products' : 'orders')))];
  const requiredActions = [
    ...(syncKinds.includes('naver_order_batch') ? ['orders.batch_sync_write'] : []),
    ...(syncKinds.includes('naver_product_batch') ? ['products.batch_sync_write'] : []),
  ];
  const ready = approvals.length > 0 && missingFlags.length === 0;
  return adaptFormalBatchExecutionPreflightReadonlyResult({
    phase: 'ERP-Batch-3A',
    status: ready ? 'formal_batch_execution_preflight_readonly_ready' : 'blocked',
    preflight_status: ready ? 'ready_for_execution_phase_planning' : 'blocked',
    preflight_ready: ready,
    skip_reason: ready ? null : 'execution_preflight_context_incomplete',
    required_preflight_flags: requiredFlags,
    missing_preflight_flags: missingFlags,
    execution_approval_count: approvals.length,
    store_ids: storeIds,
    sync_kinds: syncKinds,
    targets,
    required_actions: requiredActions,
    route_path: '/api/v1/batch/execution-preflight/readonly-check',
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    execution_approved: false,
    batch_execution_enabled: false,
    write_endpoint_enabled: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_order_writes_enabled: false,
    platform_product_writes_enabled: false,
    platform_writes_enabled: false,
    business_message: ready
      ? '\u6b63\u5f0f\u6279\u91cf\u6267\u884c\u524d\u7f6e\u68c0\u67e5\u5df2\u53ef\u7528\u4e8e\u4eba\u5de5\u590d\u6838\uff0c\u4f46\u5f53\u524d\u4e0d\u6279\u51c6\u6267\u884c\u3001\u4e0d\u5199\u5546\u54c1\u6216\u8ba2\u5355\u3002'
      : '\u6b63\u5f0f\u6279\u91cf\u6267\u884c\u524d\u7f6e\u68c0\u67e5\u5c1a\u672a\u9f50\u5907\uff0c\u8bf7\u5148\u8865\u9f50\u6298\u53e0\u8be6\u60c5\u4e2d\u7684\u95e8\u7981\u9879\u3002',
    next_action: '\u5982\u8981\u771f\u6b63\u6267\u884c\u5546\u54c1\u6216\u8ba2\u5355\u6279\u91cf\u5199\u5165\uff0c\u5fc5\u987b\u53e6\u5f00\u660e\u786e\u7684\u6267\u884c\u9636\u6bb5\u3002',
  });
}

function mockFormalBatchExecutionDryRunReadonly(payload = {}) {
  const requiredFlags = [
    'preflight_referenced',
    'readonly_candidates_referenced',
    'backup_manifest_referenced',
    'permission_evidence_referenced',
    'audit_linkage_referenced',
    'readback_plan_referenced',
    'rollback_plan_referenced',
    'sensitive_scan_passed',
    'execution_window_limited',
    'dry_run_only',
    'formal_sync_remains_closed',
  ];
  const serialized = JSON.stringify(payload);
  const hasSensitiveMarker = [
    /["']productOrderId["']\s*:/i,
    /["']product_order_id["']\s*:/i,
    /["']orderId["']\s*:/i,
    /["']order_id["']\s*:/i,
    /["']rawResponse["']\s*:/i,
    /["']raw_response["']\s*:/i,
    /["']authorization["']\s*:/i,
    /["']headers?["']\s*:/i,
    /["']clientSecret["']\s*:/i,
    /["']client_secret["']\s*:/i,
    /["']buyerPhone["']\s*:/i,
    /["']buyer_phone["']\s*:/i,
    /["']receiverPhone["']\s*:/i,
    /["']receiver_phone["']\s*:/i,
    /["']address["']\s*:/i,
    /["']detailedAddress["']\s*:/i,
    /["']detailed_address["']\s*:/i,
  ].some((pattern) => pattern.test(serialized));
  const blockedBase = {
    phase: 'ERP-Batch-3D',
    status: 'blocked',
    dry_run_status: 'blocked',
    dry_run_ready: false,
    required_dry_run_flags: requiredFlags,
    missing_dry_run_flags: [],
    route_path: '/api/v1/batch/execution-dry-run/readonly-check',
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    dry_run_only: true,
    execution_approved: false,
    batch_execution_enabled: false,
    write_endpoint_enabled: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_order_writes_enabled: false,
    platform_product_writes_enabled: false,
    platform_writes_enabled: false,
    shipment_write_enabled: false,
    cancel_write_enabled: false,
    return_write_enabled: false,
    exchange_write_enabled: false,
  };
  if (hasSensitiveMarker) {
    return adaptFormalBatchExecutionDryRunReadonlyResult({
      ...blockedBase,
      skip_reason: 'formal_batch_execution_dry_run_sensitive_field_blocked',
    });
  }

  const preflight = payload.execution_preflight || payload.executionPreflight || {};
  const dryRunContext = payload.dry_run_context || payload.dryRunContext || {};
  const executionPlan = payload.execution_plan || payload.executionPlan || {};
  const candidateSummaries = Array.isArray(payload.candidate_summaries)
    ? payload.candidate_summaries
    : (Array.isArray(payload.candidateSummaries) ? payload.candidateSummaries : []);

  if (preflight.status !== 'formal_batch_execution_preflight_readonly_ready' || preflight.preflight_ready !== true) {
    return adaptFormalBatchExecutionDryRunReadonlyResult({
      ...blockedBase,
      skip_reason: 'execution_preflight_not_ready',
    });
  }
  if (!candidateSummaries.length) {
    return adaptFormalBatchExecutionDryRunReadonlyResult({
      ...blockedBase,
      skip_reason: 'candidate_summaries_required',
    });
  }
  const missingFlags = requiredFlags.filter((flag) => dryRunContext[flag] !== true);
  if (missingFlags.length) {
    return adaptFormalBatchExecutionDryRunReadonlyResult({
      ...blockedBase,
      skip_reason: 'dry_run_context_incomplete',
      missing_dry_run_flags: missingFlags,
    });
  }
  if (
    dryRunContext.execution_approved === true
    || executionPlan.execution_approved === true
    || dryRunContext.real_api_called === true
    || dryRunContext.real_database_written === true
    || dryRunContext.orders_written === true
    || dryRunContext.products_written === true
    || executionPlan.real_api_called === true
    || executionPlan.real_database_written === true
  ) {
    return adaptFormalBatchExecutionDryRunReadonlyResult({
      ...blockedBase,
      skip_reason: 'write_not_allowed_in_dry_run',
    });
  }

  const normalizedSummaries = candidateSummaries.map((summary = {}) => {
    const syncKind = summary.sync_kind || summary.syncKind || '';
    const target = summary.target || (String(syncKind).includes('product') ? 'products' : 'orders');
    const candidateCount = Math.min(Number(summary.candidate_count ?? summary.candidateCount ?? 0), 5);
    const wouldCreate = Math.min(Number(summary.would_create ?? summary.wouldCreate ?? 0), candidateCount);
    const wouldUpdate = Math.min(Number(summary.would_update ?? summary.wouldUpdate ?? 0), candidateCount - wouldCreate);
    const wouldSkip = Math.min(Number(summary.would_skip ?? summary.wouldSkip ?? 0), candidateCount - wouldCreate - wouldUpdate);
    const wouldRefreshOnly = Math.max(candidateCount - wouldCreate - wouldUpdate - wouldSkip, 0);
    return {
      sync_kind: syncKind,
      target,
      store_ids: Array.isArray(summary.store_ids)
        ? summary.store_ids
        : (Array.isArray(summary.storeIds) ? summary.storeIds : []),
      candidate_count: candidateCount,
      would_create: wouldCreate,
      would_update: wouldUpdate,
      would_refresh_only: wouldRefreshOnly,
      would_skip: wouldSkip,
      changed_fields: Array.isArray(summary.changed_fields)
        ? summary.changed_fields
        : (Array.isArray(summary.changedFields) ? summary.changedFields : []),
    };
  });
  const totals = normalizedSummaries.reduce((acc, summary) => ({
    candidateCount: acc.candidateCount + summary.candidate_count,
    wouldCreate: acc.wouldCreate + summary.would_create,
    wouldUpdate: acc.wouldUpdate + summary.would_update,
    wouldRefreshOnly: acc.wouldRefreshOnly + summary.would_refresh_only,
    wouldSkip: acc.wouldSkip + summary.would_skip,
  }), {
    candidateCount: 0,
    wouldCreate: 0,
    wouldUpdate: 0,
    wouldRefreshOnly: 0,
    wouldSkip: 0,
  });

  return adaptFormalBatchExecutionDryRunReadonlyResult({
    ...blockedBase,
    status: 'formal_batch_execution_dry_run_readonly_ready',
    dry_run_status: 'ready_for_operator_review',
    dry_run_ready: true,
    skip_reason: null,
    missing_dry_run_flags: [],
    store_ids: Array.isArray(preflight.store_ids)
      ? preflight.store_ids
      : (Array.isArray(preflight.storeIds) ? preflight.storeIds : []),
    sync_kinds: Array.isArray(preflight.sync_kinds)
      ? preflight.sync_kinds
      : (Array.isArray(preflight.syncKinds) ? preflight.syncKinds : []),
    targets: Array.isArray(preflight.targets) ? preflight.targets : [],
    candidate_summary_count: normalizedSummaries.length,
    total_candidate_count: totals.candidateCount,
    total_would_create: totals.wouldCreate,
    total_would_update: totals.wouldUpdate,
    total_would_refresh_only: totals.wouldRefreshOnly,
    total_would_skip: totals.wouldSkip,
    changed_fields: [...new Set(normalizedSummaries.flatMap((summary) => summary.changed_fields))],
    candidate_summaries: normalizedSummaries,
    business_message: 'mock dry-run 证据已可供管理员复核；当前不写商品或订单，不调用 Naver，也不开放正式批量同步。',
    next_action: '如要进入真实批量写入，必须另开执行阶段并重新确认备份、审计、权限、回读和回滚证据。',
  });
}

function mockFormalBatchExecutionApprovalReadonly(payload = {}) {
  const requiredFlags = [
    'latest_dry_run_referenced',
    'manual_execution_phase_required',
    'backup_manifest_verified',
    'permission_evidence_verified',
    'audit_linkage_verified',
    'readback_plan_verified',
    'rollback_plan_verified',
    'sensitive_scan_passed',
    'operator_identity_verified',
    'store_scope_verified',
    'execution_window_limited',
    'manual_approval_record_planned',
    'formal_sync_remains_closed',
  ];
  const serialized = JSON.stringify(payload);
  const hasSensitiveMarker = [
    /["']productOrderId["']\s*:/i,
    /["']product_order_id["']\s*:/i,
    /["']orderId["']\s*:/i,
    /["']order_id["']\s*:/i,
    /["']rawResponse["']\s*:/i,
    /["']raw_response["']\s*:/i,
    /["']authorization["']\s*:/i,
    /["']headers?["']\s*:/i,
    /["']clientSecret["']\s*:/i,
    /["']client_secret["']\s*:/i,
    /["']buyerPhone["']\s*:/i,
    /["']buyer_phone["']\s*:/i,
    /["']receiverPhone["']\s*:/i,
    /["']receiver_phone["']\s*:/i,
    /["']address["']\s*:/i,
    /["']detailedAddress["']\s*:/i,
    /["']detailed_address["']\s*:/i,
  ].some((pattern) => pattern.test(serialized));
  const blockedBase = {
    phase: 'ERP-Batch-3J',
    status: 'blocked',
    approval_status: 'blocked',
    final_approval_ready: false,
    required_final_approval_flags: requiredFlags,
    missing_final_approval_flags: [],
    route_path: '/api/v1/batch/execution-approval/readonly-check',
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    execution_approved: false,
    batch_execution_enabled: false,
    write_endpoint_enabled: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_order_writes_enabled: false,
    platform_product_writes_enabled: false,
    platform_writes_enabled: false,
    shipment_write_enabled: false,
    cancel_write_enabled: false,
    return_write_enabled: false,
    exchange_write_enabled: false,
  };
  if (hasSensitiveMarker) {
    return adaptFormalBatchExecutionApprovalReadonlyResult({
      ...blockedBase,
      skip_reason: 'formal_batch_execution_approval_sensitive_field_blocked',
    });
  }

  const preflight = payload.execution_preflight || payload.executionPreflight || {};
  const dryRun = payload.execution_dry_run || payload.executionDryRun || {};
  const approvalContext = payload.final_approval_context || payload.finalApprovalContext || {};
  if (preflight.status !== 'formal_batch_execution_preflight_readonly_ready' || preflight.preflight_ready !== true) {
    return adaptFormalBatchExecutionApprovalReadonlyResult({
      ...blockedBase,
      skip_reason: 'execution_preflight_not_ready',
    });
  }
  if (dryRun.status !== 'formal_batch_execution_dry_run_readonly_ready' || dryRun.dry_run_ready !== true) {
    return adaptFormalBatchExecutionApprovalReadonlyResult({
      ...blockedBase,
      skip_reason: 'execution_dry_run_not_ready',
    });
  }
  const missingFlags = requiredFlags.filter((flag) => approvalContext[flag] !== true);
  if (missingFlags.length) {
    return adaptFormalBatchExecutionApprovalReadonlyResult({
      ...blockedBase,
      skip_reason: 'final_approval_context_incomplete',
      missing_final_approval_flags: missingFlags,
    });
  }
  const sideEffectBlocked = [
    preflight,
    dryRun,
    approvalContext,
  ].some((item) => item.execution_approved === true
    || item.batch_execution_enabled === true
    || item.write_endpoint_enabled === true
    || item.real_api_called === true
    || item.real_database_written === true
    || item.orders_written === true
    || item.products_written === true
    || item.operation_audit_rows_written === true
    || item.formal_sync_open === true
    || item.platform_writes_enabled === true);
  if (sideEffectBlocked) {
    return adaptFormalBatchExecutionApprovalReadonlyResult({
      ...blockedBase,
      skip_reason: 'side_effect_not_allowed_in_approval_mock_gate',
    });
  }

  const candidateSummaries = Array.isArray(dryRun.candidate_summaries)
    ? dryRun.candidate_summaries
    : (Array.isArray(dryRun.candidateSummaries) ? dryRun.candidateSummaries : []);
  return adaptFormalBatchExecutionApprovalReadonlyResult({
    ...blockedBase,
    status: 'formal_batch_execution_approval_readonly_api_ready',
    approval_status: 'ready_for_local_readonly_review',
    final_approval_ready: true,
    skip_reason: null,
    store_ids: Array.isArray(dryRun.store_ids) ? dryRun.store_ids : (Array.isArray(dryRun.storeIds) ? dryRun.storeIds : []),
    sync_kinds: Array.isArray(dryRun.sync_kinds) ? dryRun.sync_kinds : (Array.isArray(dryRun.syncKinds) ? dryRun.syncKinds : []),
    targets: Array.isArray(dryRun.targets) ? dryRun.targets : [],
    required_actions: Array.isArray(approvalContext.required_actions)
      ? approvalContext.required_actions
      : (Array.isArray(approvalContext.requiredActions) ? approvalContext.requiredActions : []),
    candidate_summary_count: Number(dryRun.candidate_summary_count ?? dryRun.candidateSummaryCount ?? candidateSummaries.length),
    total_candidate_count: Number(dryRun.total_candidate_count ?? dryRun.totalCandidateCount ?? 0),
    total_would_create: Number(dryRun.total_would_create ?? dryRun.totalWouldCreate ?? 0),
    total_would_update: Number(dryRun.total_would_update ?? dryRun.totalWouldUpdate ?? 0),
    total_would_refresh_only: Number(dryRun.total_would_refresh_only ?? dryRun.totalWouldRefreshOnly ?? 0),
    total_would_skip: Number(dryRun.total_would_skip ?? dryRun.totalWouldSkip ?? 0),
    changed_fields: Array.isArray(dryRun.changed_fields) ? dryRun.changed_fields : (Array.isArray(dryRun.changedFields) ? dryRun.changedFields : []),
    candidate_summaries: candidateSummaries,
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    business_message: 'mock 最终审批只读复核已通过；当前不批准执行、不写商品或订单、不调用 Naver，也不开放正式批量同步。',
    next_action: '如要进入真实批量写入，必须另开执行阶段并重新确认备份、审计、权限、回读和回滚证据。',
  });
}

function mockFormalBatchExecutionWriteBoundaryReadonly(payload = {}) {
  const requiredBoundaryFlags = [
    'separate_execution_phase_required',
    'fresh_approval_required',
    'fresh_backup_required',
    'dry_run_recheck_required',
    'write_scope_freeze_required',
    'max_batch_size_enforced',
    'store_scope_locked',
    'permission_recheck_required',
    'audit_write_plan_required',
    'readback_required',
    'rollback_required',
    'sensitive_scan_required',
    'partial_failure_policy_required',
    'idempotency_required',
    'operator_confirmation_required',
    'execution_window_limited',
    'formal_sync_remains_closed',
  ];
  const requiredApiFlags = [
    'readonly_api_contract_planned',
    'business_wording_required',
    'technical_details_folded',
    'execution_button_excluded',
    'write_endpoint_excluded',
    'product_write_endpoint_excluded',
    'order_write_endpoint_excluded',
    'audit_row_write_excluded',
    'sensitive_fields_hidden_from_main_page',
    'route_requires_separate_implementation',
    'formal_sync_remains_closed',
  ];
  const serialized = JSON.stringify(payload);
  const hasSensitiveMarker = [
    /["']productOrderId["']\s*:/i,
    /["']product_order_id["']\s*:/i,
    /["']orderId["']\s*:/i,
    /["']rawResponse["']\s*:/i,
    /["']raw_response["']\s*:/i,
    /["']authorization["']\s*:/i,
    /["']headers?["']\s*:/i,
    /["']clientSecret["']\s*:/i,
    /["']buyerPhone["']\s*:/i,
    /["']receiverPhone["']\s*:/i,
    /["']address["']\s*:/i,
  ].some((pattern) => pattern.test(serialized));
  const blockedBase = {
    phase: 'ERP-Batch-4C',
    status: 'blocked',
    approval_status: 'blocked',
    write_boundary_plan_ready: false,
    required_write_boundary_flags: requiredBoundaryFlags,
    missing_write_boundary_flags: [],
    required_api_flags: requiredApiFlags,
    missing_api_flags: [],
    route_path: '/api/v1/batch/execution-write-boundary/readonly-check',
    route_path_planned: '/api/v1/batch/execution-write-boundary/readonly-check',
    backend_route_implemented: true,
    public_endpoint_enabled: true,
    execution_approved: false,
    batch_execution_enabled: false,
    write_endpoint_enabled: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_order_writes_enabled: false,
    platform_product_writes_enabled: false,
    platform_writes_enabled: false,
    shipment_write_enabled: false,
    cancel_write_enabled: false,
    return_write_enabled: false,
    exchange_write_enabled: false,
  };
  if (hasSensitiveMarker) {
    return adaptFormalBatchExecutionWriteBoundaryReadonlyResult({
      ...blockedBase,
      skip_reason: 'write_boundary_readonly_api_sensitive_field_blocked',
    });
  }
  const approval = payload.execution_approval || payload.executionApproval || {};
  const boundaryContext = payload.write_boundary_context || payload.writeBoundaryContext || {};
  const apiContext = payload.readonly_api_context || payload.readonlyApiContext || {};
  if (approval.status !== 'formal_batch_execution_approval_readonly_api_ready'
    || approval.final_approval_ready !== true) {
    return adaptFormalBatchExecutionWriteBoundaryReadonlyResult({
      ...blockedBase,
      skip_reason: 'execution_approval_not_ready',
    });
  }
  const missingBoundaryFlags = requiredBoundaryFlags.filter((flag) => boundaryContext[flag] !== true);
  if (missingBoundaryFlags.length) {
    return adaptFormalBatchExecutionWriteBoundaryReadonlyResult({
      ...blockedBase,
      skip_reason: 'write_boundary_context_incomplete',
      missing_write_boundary_flags: missingBoundaryFlags,
    });
  }
  const missingApiFlags = requiredApiFlags.filter((flag) => apiContext[flag] !== true);
  if (missingApiFlags.length) {
    return adaptFormalBatchExecutionWriteBoundaryReadonlyResult({
      ...blockedBase,
      skip_reason: 'readonly_api_context_incomplete',
      missing_api_flags: missingApiFlags,
    });
  }
  const sideEffectBlocked = [
    boundaryContext,
    apiContext,
  ].some((item) => item.execution_approved === true
    || item.batch_execution_enabled === true
    || item.write_endpoint_enabled === true
    || item.real_api_called === true
    || item.real_database_written === true
    || item.orders_written === true
    || item.products_written === true
    || item.operation_audit_rows_written === true
    || item.formal_sync_open === true
    || item.platform_writes_enabled === true);
  if (sideEffectBlocked) {
    return adaptFormalBatchExecutionWriteBoundaryReadonlyResult({
      ...blockedBase,
      skip_reason: 'write_not_allowed_in_readonly_api_mock_gate',
    });
  }
  const candidateSummaries = Array.isArray(approval.candidate_summaries)
    ? approval.candidate_summaries
    : (Array.isArray(approval.candidateSummaries) ? approval.candidateSummaries : []);
  return adaptFormalBatchExecutionWriteBoundaryReadonlyResult({
    ...blockedBase,
    status: 'formal_batch_execution_write_boundary_readonly_api_ready',
    approval_status: 'ready_for_local_readonly_review',
    write_boundary_plan_ready: true,
    skip_reason: null,
    store_ids: Array.isArray(approval.store_ids) ? approval.store_ids : (Array.isArray(approval.storeIds) ? approval.storeIds : []),
    sync_kinds: Array.isArray(approval.sync_kinds) ? approval.sync_kinds : (Array.isArray(approval.syncKinds) ? approval.syncKinds : []),
    targets: Array.isArray(approval.targets) ? approval.targets : [],
    required_actions: Array.isArray(approval.required_actions)
      ? approval.required_actions
      : (Array.isArray(approval.requiredActions) ? approval.requiredActions : []),
    candidate_summary_count: Number(approval.candidate_summary_count ?? approval.candidateSummaryCount ?? candidateSummaries.length),
    total_candidate_count: Number(approval.total_candidate_count ?? approval.totalCandidateCount ?? 0),
    total_would_create: Number(approval.total_would_create ?? approval.totalWouldCreate ?? 0),
    total_would_update: Number(approval.total_would_update ?? approval.totalWouldUpdate ?? 0),
    total_would_refresh_only: Number(approval.total_would_refresh_only ?? approval.totalWouldRefreshOnly ?? 0),
    total_would_skip: Number(approval.total_would_skip ?? approval.totalWouldSkip ?? 0),
    max_batch_size: Number(boundaryContext.max_batch_size ?? boundaryContext.maxBatchSize ?? 10),
    changed_fields: Array.isArray(approval.changed_fields) ? approval.changed_fields : (Array.isArray(approval.changedFields) ? approval.changedFields : []),
    candidate_summaries: candidateSummaries,
    business_message: '\u6b63\u5f0f\u6279\u91cf\u5199\u5165\u8fb9\u754c\u53ea\u8bfb\u590d\u6838\u5df2\u5c31\u7eea\uff1b\u5f53\u524d\u4ecd\u4e0d\u6279\u51c6\u6267\u884c\u3001\u4e0d\u5199\u5546\u54c1\u6216\u8ba2\u5355\u3001\u4e0d\u8c03\u7528\u5e73\u53f0\u63a5\u53e3\u3002',
    next_action: '\u5982\u8981\u771f\u6b63\u6267\u884c\u6279\u91cf\u5199\u5165\uff0c\u5fc5\u987b\u53e6\u5f00\u6267\u884c\u9636\u6bb5\u5e76\u91cd\u65b0\u786e\u8ba4\u5907\u4efd\u3001\u5ba1\u8ba1\u3001\u56de\u8bfb\u3001\u56de\u6eda\u548c\u654f\u611f\u626b\u63cf\u3002',
  });
}

function mockFormalBatchPreExecutionRefreshReadonly(payload = {}) {
  const serialized = JSON.stringify(payload).toLowerCase();
  const hasSensitiveMarker = serialized.includes('productorderid')
    || serialized.includes('rawresponse')
    || serialized.includes('authorization')
    || serialized.includes('headers')
    || serialized.includes('clientsecret')
    || serialized.includes('client_secret')
    || serialized.includes('buyerphone')
    || serialized.includes('receiverphone')
    || serialized.includes('address');
  const requiredBackupFlags = [
    'fresh_backup_created',
    'backup_manifest_verified',
    'backup_sha256_verified',
    'restore_dry_run_referenced',
    'backup_created_after_boundary_review',
    'safe_backup_reference_only',
  ];
  const requiredAuditFlags = [
    'audit_correlation_planned',
    'append_only_audit_chain_planned',
    'actor_store_scope_verified',
    'safe_metadata_only',
    'backup_evidence_link_planned',
    'write_attempt_record_planned',
    'readback_audit_planned',
    'rollback_audit_planned',
    'no_audit_rows_written_yet',
  ];
  const requiredApiFlags = [
    'readonly_api_contract_planned',
    'business_wording_required',
    'technical_details_folded',
    'execution_button_excluded',
    'write_endpoint_excluded',
    'backup_creation_button_excluded',
    'audit_row_write_excluded',
    'product_write_endpoint_excluded',
    'order_write_endpoint_excluded',
    'sensitive_fields_hidden_from_main_page',
    'route_requires_separate_implementation',
    'formal_sync_remains_closed',
  ];
  const review = payload.write_boundary_review || payload.writeBoundaryReview || {};
  const backupEvidence = payload.backup_refresh_evidence || payload.backupRefreshEvidence || {};
  const auditEvidence = payload.audit_refresh_evidence || payload.auditRefreshEvidence || {};
  const apiContext = payload.readonly_api_context || payload.readonlyApiContext || {};
  const blockedBase = {
    phase: 'ERP-Batch-4G',
    status: 'blocked',
    approval_status: 'blocked',
    pre_execution_backup_audit_refresh_gate_ready: false,
    backup_refresh_verified: false,
    audit_refresh_verified: false,
    readonly_api_mock_gate: true,
    required_backup_flags: requiredBackupFlags,
    missing_backup_flags: [],
    required_audit_flags: requiredAuditFlags,
    missing_audit_flags: [],
    required_api_flags: requiredApiFlags,
    missing_api_flags: [],
    store_ids: Array.isArray(review.store_ids) ? review.store_ids : (Array.isArray(review.storeIds) ? review.storeIds : []),
    sync_kinds: Array.isArray(review.sync_kinds) ? review.sync_kinds : (Array.isArray(review.syncKinds) ? review.syncKinds : []),
    targets: Array.isArray(review.targets) ? review.targets : [],
    required_actions: Array.isArray(review.required_actions)
      ? review.required_actions
      : (Array.isArray(review.requiredActions) ? review.requiredActions : []),
    candidate_summary_count: Number(review.candidate_summary_count ?? review.candidateSummaryCount ?? 0),
    total_candidate_count: Number(review.total_candidate_count ?? review.totalCandidateCount ?? 0),
    backup_sha256_abbrev: null,
    audit_correlation_reference: null,
    route_path: '/api/v1/batch/pre-execution-refresh/readonly-check',
    route_path_planned: '/api/v1/batch/pre-execution-refresh/readonly-check',
    backend_route_implemented: true,
    public_endpoint_enabled: true,
    execution_approved: false,
    batch_execution_enabled: false,
    write_endpoint_enabled: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_order_writes_enabled: false,
    platform_product_writes_enabled: false,
    platform_writes_enabled: false,
    shipment_write_enabled: false,
    cancel_write_enabled: false,
    return_write_enabled: false,
    exchange_write_enabled: false,
  };
  if (hasSensitiveMarker) {
    return adaptFormalBatchPreExecutionRefreshReadonlyResult({
      ...blockedBase,
      skip_reason: 'pre_execution_refresh_readonly_api_sensitive_field_blocked',
    });
  }
  if (review.status !== 'formal_batch_execution_write_boundary_readonly_api_ready'
    || review.write_boundary_plan_ready !== true) {
    return adaptFormalBatchPreExecutionRefreshReadonlyResult({
      ...blockedBase,
      skip_reason: 'write_boundary_review_not_ready',
    });
  }
  const missingBackupFlags = requiredBackupFlags.filter((flag) => backupEvidence[flag] !== true);
  if (missingBackupFlags.length) {
    return adaptFormalBatchPreExecutionRefreshReadonlyResult({
      ...blockedBase,
      skip_reason: 'backup_refresh_evidence_incomplete',
      missing_backup_flags: missingBackupFlags,
    });
  }
  const missingAuditFlags = requiredAuditFlags.filter((flag) => auditEvidence[flag] !== true);
  if (missingAuditFlags.length) {
    return adaptFormalBatchPreExecutionRefreshReadonlyResult({
      ...blockedBase,
      skip_reason: 'audit_refresh_evidence_incomplete',
      missing_audit_flags: missingAuditFlags,
    });
  }
  const missingApiFlags = requiredApiFlags.filter((flag) => apiContext[flag] !== true);
  if (missingApiFlags.length) {
    return adaptFormalBatchPreExecutionRefreshReadonlyResult({
      ...blockedBase,
      skip_reason: 'readonly_api_context_incomplete',
      missing_api_flags: missingApiFlags,
    });
  }
  const sideEffectBlocked = [
    review,
    backupEvidence,
    auditEvidence,
    apiContext,
  ].some((item) => item.execution_approved === true
    || item.batch_execution_enabled === true
    || item.write_endpoint_enabled === true
    || item.real_api_called === true
    || item.real_database_written === true
    || item.orders_written === true
    || item.products_written === true
    || item.operation_audit_rows_written === true
    || item.formal_sync_open === true
    || item.platform_writes_enabled === true
    || item.backup_created === true
    || item.restore_executed === true);
  if (sideEffectBlocked) {
    return adaptFormalBatchPreExecutionRefreshReadonlyResult({
      ...blockedBase,
      skip_reason: 'write_not_allowed_in_pre_execution_refresh_readonly_api_mock_gate',
    });
  }
  const backupSha256 = String(backupEvidence.backup_sha256 || '');
  return adaptFormalBatchPreExecutionRefreshReadonlyResult({
    ...blockedBase,
    status: 'formal_batch_pre_execution_refresh_readonly_api_ready',
    approval_status: 'ready_for_local_readonly_review',
    pre_execution_backup_audit_refresh_gate_ready: true,
    backup_refresh_verified: true,
    audit_refresh_verified: true,
    backup_sha256_abbrev: backupSha256 ? `${backupSha256.slice(0, 12)}...` : null,
    audit_correlation_reference: String(auditEvidence.audit_correlation_id_hash || '').slice(0, 24) || null,
    business_message: '\u6267\u884c\u524d\u5907\u4efd\u4e0e\u5ba1\u8ba1\u5237\u65b0\u590d\u6838\u5df2\u5c31\u7eea\uff1b\u5f53\u524d\u4ec5\u5c55\u793a\u8bc1\u636e\uff0c\u4e0d\u521b\u5efa\u5907\u4efd\u3001\u4e0d\u5199\u5ba1\u8ba1\u884c\u3001\u4e0d\u6267\u884c\u6279\u91cf\u540c\u6b65\u3002',
    next_action: '\u5982\u8981\u771f\u6b63\u6267\u884c\u6279\u91cf\u5199\u5165\uff0c\u5fc5\u987b\u53e6\u5f00\u6267\u884c\u9636\u6bb5\u5e76\u91cd\u65b0\u786e\u8ba4\u5907\u4efd\u3001\u5ba1\u8ba1\u3001\u56de\u8bfb\u3001\u56de\u6eda\u548c\u654f\u611f\u626b\u63cf\u3002',
  });
}

function mockNaverBatchExecutionApprovalReadonly(payload = {}, kind = 'order') {
  const serialized = JSON.stringify(payload).toLowerCase();
  const hasSensitiveMarker = serialized.includes('productorderid')
    || serialized.includes('rawresponse')
    || serialized.includes('authorization')
    || serialized.includes('client_secret');
  const isProduct = kind === 'product';
  const blockedBase = {
    phase: isProduct ? 'Naver-Product-Batch-2L' : 'Naver-Order-Batch-3C',
    status: 'blocked',
    execution_approved: false,
    real_api_called: false,
    real_database_written: false,
    orders_written: false,
    products_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    timeline_events_written: false,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_sync_open: false,
    formal_order_sync_open: false,
    formal_product_sync_open: false,
    platform_order_writes_enabled: false,
    platform_product_writes_enabled: false,
    platform_writes_enabled: false,
    shipment_write_enabled: false,
    cancel_write_enabled: false,
    return_write_enabled: false,
    exchange_write_enabled: false,
  };
  if (hasSensitiveMarker) {
    return adaptNaverBatchExecutionApprovalReadonlyResult({
      ...blockedBase,
      skip_reason: isProduct
        ? 'naver_product_batch_execution_sensitive_field_blocked'
        : 'naver_order_batch_execution_sensitive_field_blocked',
    }, kind);
  }
  const executionContext = payload.execution_context || payload.executionContext || {};
  const readonlyApiContext = payload.readonly_api_context || payload.readonlyApiContext || {};
  const requiredExecutionFlags = isProduct
    ? [
      'product_batch_candidates_fresh',
      'product_field_whitelist_verified',
      'price_stock_status_mapping_reviewed',
      'duplicate_protection_ready',
      'audit_chain_ready',
      'post_write_readback_required',
      'rollback_plan_ready',
      'sensitive_scan_passed',
      'platform_product_write_actions_excluded',
      'formal_sync_remains_closed',
    ]
    : [
      'order_batch_candidates_fresh',
      'order_privacy_gate_verified',
      'order_field_whitelist_verified',
      'delivery_claim_mapping_reviewed',
      'duplicate_protection_ready',
      'audit_chain_ready',
      'post_write_readback_required',
      'rollback_plan_ready',
      'sensitive_scan_passed',
      'platform_order_write_actions_excluded',
      'formal_sync_remains_closed',
    ];
  const requiredApiFlags = [
    'readonly_api_contract_planned',
    'business_wording_required',
    'technical_details_folded',
    'execution_button_excluded',
    'write_endpoint_excluded',
    isProduct ? 'product_write_endpoint_excluded' : 'order_write_endpoint_excluded',
    'sensitive_fields_hidden_from_main_page',
    ...(isProduct ? [] : ['buyer_privacy_hidden_from_main_page']),
    'audit_row_write_excluded',
    'route_requires_separate_implementation',
    'formal_sync_remains_closed',
  ];
  const missingExecutionFlags = requiredExecutionFlags.filter((flag) => executionContext[flag] !== true);
  const missingApiFlags = requiredApiFlags.filter((flag) => readonlyApiContext[flag] !== true);
  const ready = missingExecutionFlags.length === 0
    && missingApiFlags.length === 0
    && payload.manual_approval === true
    && readonlyApiContext.execution_approved !== true
    && readonlyApiContext.formal_sync_open !== true
    && readonlyApiContext.platform_writes_enabled !== true;
  return adaptNaverBatchExecutionApprovalReadonlyResult({
    ...blockedBase,
    phase: isProduct ? 'Naver-Product-Batch-2L' : 'Naver-Order-Batch-3C',
    status: ready
      ? (isProduct
        ? 'naver_product_batch_execution_approval_readonly_api_ready'
        : 'naver_order_batch_execution_approval_readonly_api_ready')
      : 'blocked',
    skip_reason: ready ? null : 'execution_approval_readonly_context_incomplete',
    store_ids: payload.store_ids || [],
    candidate_count: Number(payload.candidate_count || 0),
    batch_size: Number(payload.batch_size || 0),
    product_batch_execution_approval_ready: isProduct && ready,
    order_batch_execution_approval_ready: !isProduct && ready,
    required_execution_flags: requiredExecutionFlags,
    missing_execution_flags: missingExecutionFlags,
    required_api_flags: requiredApiFlags,
    missing_api_flags: missingApiFlags,
    permission_verified: true,
    approval_role_verified: true,
    backup_evidence_verified: true,
    readonly_evidence_verified: true,
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    route_path: isProduct
      ? '/api/v1/batch/naver/products/execution-approval/readonly-check'
      : '/api/v1/batch/naver/orders/execution-approval/readonly-check',
    business_message: ready
      ? (isProduct
        ? 'Naver 商品批量执行审批只读材料已可用于人工复核；当前不开放商品批量写入。'
        : 'Naver 订单手动批量刷新已在订单页开放；该旧审批只读页不执行同步。')
      : '批量执行审批只读材料尚未齐备；请先补齐折叠详情中的门禁项。',
    next_action: '任何正式批量写入都必须另开明确执行阶段并重新确认备份、审计、回读和敏感扫描。',
  }, kind);
}

function mockNaverProductRollbackReadonlyReport(payload = {}) {
  const gate = payload.rollback_drill_gate || payload.rollbackDrillGate || {};
  const hasSensitiveMarker = JSON.stringify(payload).toLowerCase().includes('rawresponse')
    || JSON.stringify(payload).toLowerCase().includes('external_product_id');
  if (hasSensitiveMarker) {
    return adaptProductRollbackReadonlyReportResult({
      phase: 'Naver-Product-Batch-1R',
      status: 'blocked',
      skip_reason: 'rollback_report_sensitive_field_blocked',
      real_restore_executed: false,
      products_written: false,
      real_database_written: false,
      formal_product_sync_open: false,
      public_endpoint_enabled: false,
      privacy_fields_redacted: true,
    });
  }
  return adaptProductRollbackReadonlyReportResult({
    phase: 'Naver-Product-Batch-1R',
    status: gate.status === 'product_batch_rollback_drill_mock_ready'
      ? 'product_rollback_drill_readonly_report_ready'
      : 'product_rollback_drill_readonly_report_ready',
    report_ready: true,
    report_sections: ['backup_evidence', 'stock_change_summary', 'rollback_checklist', 'restore_drill_plan', 'readback_plan', 'sensitive_scan_plan'],
    rollback_drill_ready: true,
    backup_evidence_verified: true,
    updated_count: Number(gate.updated_count ?? gate.updatedCount ?? 3),
    created_count: Number(gate.created_count ?? gate.createdCount ?? 0),
    stock_only_write_verified: true,
    temporary_restore_required: true,
    backend_route_implemented: false,
    public_endpoint_enabled: false,
    real_restore_executed: false,
    rollback_executed: false,
    production_db_touched: false,
    real_api_called: false,
    real_database_written: false,
    products_written: false,
    orders_written: false,
    sync_log_written: false,
    capability_tested_success_written: false,
    operation_audit_rows_written: false,
    raw_response_saved: false,
    secrets_saved: false,
    privacy_fields_redacted: true,
    formal_product_sync_open: false,
    formal_sync_open: false,
    platform_writes_enabled: false,
    route_path: '/api/v1/batch/naver/products/rollback-readonly-report',
    business_message: 'mock 商品回滚只读报告已整理，不会执行恢复或写入商品。',
    next_action: '继续人工审核备份、回读和敏感扫描证据。',
  });
}

function toBatchApprovalReadonlyEvidencePayload(readonlyEvidence = {}) {
  const rawItems = Array.isArray(readonlyEvidence.items) ? readonlyEvidence.items : [];
  return {
    status: readonlyEvidence.status || 'readonly_evidence_api_ready',
    formal_sync_open: Boolean(readonlyEvidence.formalSyncOpen ?? readonlyEvidence.formal_sync_open),
    real_database_written: Boolean(readonlyEvidence.realDatabaseWritten ?? readonlyEvidence.real_database_written),
    orders_written: Boolean(readonlyEvidence.ordersWritten ?? readonlyEvidence.orders_written),
    products_written: Boolean(readonlyEvidence.productsWritten ?? readonlyEvidence.products_written),
    sync_log_written: Boolean(readonlyEvidence.syncLogWritten ?? readonlyEvidence.sync_log_written),
    capability_tested_success_written: Boolean(readonlyEvidence.capabilityTestedSuccessWritten ?? readonlyEvidence.capability_tested_success_written),
    operation_audit_rows_written: Boolean(readonlyEvidence.operationAuditRowsWritten ?? readonlyEvidence.operation_audit_rows_written),
    operation_audit_rows_planned: readonlyEvidence.operationAuditRowsPlanned ?? readonlyEvidence.operation_audit_rows_planned ?? true,
    privacy_fields_redacted: readonlyEvidence.privacyFieldsRedacted ?? readonlyEvidence.privacy_fields_redacted ?? true,
    raw_response_saved: Boolean(readonlyEvidence.rawResponseSaved ?? readonlyEvidence.raw_response_saved),
    items: rawItems.map((item = {}) => ({
      store_id: Number(item.storeId ?? item.store_id ?? 0),
      sync_kind: item.syncKind || item.sync_kind || '',
      duplicate_check_passed: item.duplicateCheckPassed ?? item.duplicate_check_passed ?? true,
      field_whitelist_verified: item.fieldWhitelistVerified ?? item.field_whitelist_verified ?? true,
      audit_required: item.auditRequired ?? item.audit_required ?? true,
      operation_audit_rows_planned: item.operationAuditRowsPlanned ?? item.operation_audit_rows_planned ?? true,
      backup_required: item.backupRequired ?? item.backup_required ?? true,
      permission_required: item.permissionRequired ?? item.permission_required ?? true,
      candidate_count: Number(item.candidateCount ?? item.candidate_count ?? 0),
      would_create: Number(item.wouldCreate ?? item.would_create ?? 0),
      would_update: Number(item.wouldUpdate ?? item.would_update ?? 0),
      would_refresh_only: Number(item.wouldRefreshOnly ?? item.would_refresh_only ?? 0),
      would_skip: Number(item.wouldSkip ?? item.would_skip ?? 0),
      changed_field_names: Array.isArray(item.changedFieldNames)
        ? item.changedFieldNames
        : (Array.isArray(item.changed_field_names) ? item.changed_field_names : []),
    })),
  };
}

function toBatchApprovalAuditEvidencePayload(approvalAuditEvidence = {}) {
  return {
    status: approvalAuditEvidence.status || 'batch_approval_audit_evidence_ready',
    formal_sync_open: Boolean(approvalAuditEvidence.formalSyncOpen ?? approvalAuditEvidence.formal_sync_open),
    real_database_written: Boolean(approvalAuditEvidence.realDatabaseWritten ?? approvalAuditEvidence.real_database_written),
    orders_written: Boolean(approvalAuditEvidence.ordersWritten ?? approvalAuditEvidence.orders_written),
    products_written: Boolean(approvalAuditEvidence.productsWritten ?? approvalAuditEvidence.products_written),
    sync_log_written: Boolean(approvalAuditEvidence.syncLogWritten ?? approvalAuditEvidence.sync_log_written),
    capability_tested_success_written: Boolean(
      approvalAuditEvidence.capabilityTestedSuccessWritten ?? approvalAuditEvidence.capability_tested_success_written,
    ),
    operation_audit_rows_written: Boolean(
      approvalAuditEvidence.operationAuditRowsWritten ?? approvalAuditEvidence.operation_audit_rows_written,
    ),
    operation_audit_rows_planned: approvalAuditEvidence.operationAuditRowsPlanned
      ?? approvalAuditEvidence.operation_audit_rows_planned
      ?? true,
    privacy_fields_redacted: approvalAuditEvidence.privacyFieldsRedacted
      ?? approvalAuditEvidence.privacy_fields_redacted
      ?? true,
    raw_response_saved: Boolean(approvalAuditEvidence.rawResponseSaved ?? approvalAuditEvidence.raw_response_saved),
    store_ids: Array.isArray(approvalAuditEvidence.storeIds)
      ? approvalAuditEvidence.storeIds
      : (Array.isArray(approvalAuditEvidence.store_ids) ? approvalAuditEvidence.store_ids : []),
    sync_kinds: Array.isArray(approvalAuditEvidence.syncKinds)
      ? approvalAuditEvidence.syncKinds
      : (Array.isArray(approvalAuditEvidence.sync_kinds) ? approvalAuditEvidence.sync_kinds : []),
    required_actions: Array.isArray(approvalAuditEvidence.requiredActions)
      ? approvalAuditEvidence.requiredActions
      : (Array.isArray(approvalAuditEvidence.required_actions) ? approvalAuditEvidence.required_actions : []),
  };
}

function toBatchApprovalDecisionPayload(approvalDecision = {}) {
  return {
    status: approvalDecision.status || 'formal_batch_approval_decision_readonly_api_ready',
    store_ids: Array.isArray(approvalDecision.storeIds)
      ? approvalDecision.storeIds
      : (Array.isArray(approvalDecision.store_ids) ? approvalDecision.store_ids : []),
    sync_kinds: Array.isArray(approvalDecision.syncKinds)
      ? approvalDecision.syncKinds
      : (Array.isArray(approvalDecision.sync_kinds) ? approvalDecision.sync_kinds : []),
    required_actions: Array.isArray(approvalDecision.requiredActions)
      ? approvalDecision.requiredActions
      : (Array.isArray(approvalDecision.required_actions) ? approvalDecision.required_actions : []),
    execution_approved: Boolean(approvalDecision.executionApproved ?? approvalDecision.execution_approved),
    formal_sync_open: Boolean(approvalDecision.formalSyncOpen ?? approvalDecision.formal_sync_open),
    platform_writes_enabled: Boolean(approvalDecision.platformWritesEnabled ?? approvalDecision.platform_writes_enabled),
    real_database_written: Boolean(approvalDecision.realDatabaseWritten ?? approvalDecision.real_database_written),
    orders_written: Boolean(approvalDecision.ordersWritten ?? approvalDecision.orders_written),
    products_written: Boolean(approvalDecision.productsWritten ?? approvalDecision.products_written),
    operation_audit_rows_written: Boolean(
      approvalDecision.operationAuditRowsWritten ?? approvalDecision.operation_audit_rows_written,
    ),
    privacy_fields_redacted: approvalDecision.privacyFieldsRedacted
      ?? approvalDecision.privacy_fields_redacted
      ?? true,
  };
}

function toBatchApprovalDecisionAuditLinkagePayload(approvalAuditLinkage = {}) {
  return {
    status: approvalAuditLinkage.status || 'approval_decision_audit_linkage_readonly_api_ready',
    store_ids: Array.isArray(approvalAuditLinkage.storeIds)
      ? approvalAuditLinkage.storeIds
      : (Array.isArray(approvalAuditLinkage.store_ids) ? approvalAuditLinkage.store_ids : []),
    sync_kinds: Array.isArray(approvalAuditLinkage.syncKinds)
      ? approvalAuditLinkage.syncKinds
      : (Array.isArray(approvalAuditLinkage.sync_kinds) ? approvalAuditLinkage.sync_kinds : []),
    required_actions: Array.isArray(approvalAuditLinkage.requiredActions)
      ? approvalAuditLinkage.requiredActions
      : (Array.isArray(approvalAuditLinkage.required_actions) ? approvalAuditLinkage.required_actions : []),
    audit_linkage_ready: Boolean(approvalAuditLinkage.auditLinkageReady ?? approvalAuditLinkage.audit_linkage_ready),
    execution_approved: Boolean(approvalAuditLinkage.executionApproved ?? approvalAuditLinkage.execution_approved),
    real_database_written: Boolean(approvalAuditLinkage.realDatabaseWritten ?? approvalAuditLinkage.real_database_written),
    orders_written: Boolean(approvalAuditLinkage.ordersWritten ?? approvalAuditLinkage.orders_written),
    products_written: Boolean(approvalAuditLinkage.productsWritten ?? approvalAuditLinkage.products_written),
    operation_audit_rows_written: Boolean(
      approvalAuditLinkage.operationAuditRowsWritten ?? approvalAuditLinkage.operation_audit_rows_written,
    ),
    formal_sync_open: Boolean(approvalAuditLinkage.formalSyncOpen ?? approvalAuditLinkage.formal_sync_open),
    platform_writes_enabled: Boolean(approvalAuditLinkage.platformWritesEnabled ?? approvalAuditLinkage.platform_writes_enabled),
    privacy_fields_redacted: approvalAuditLinkage.privacyFieldsRedacted
      ?? approvalAuditLinkage.privacy_fields_redacted
      ?? true,
  };
}

function toBatchExecutionApprovalPayload(approval = {}) {
  return {
    status: approval.status || 'blocked',
    store_ids: Array.isArray(approval.storeIds)
      ? approval.storeIds
      : (Array.isArray(approval.store_ids) ? approval.store_ids : []),
    product_batch_execution_approval_ready: Boolean(
      approval.productBatchExecutionApprovalReady ?? approval.product_batch_execution_approval_ready,
    ),
    order_batch_execution_approval_ready: Boolean(
      approval.orderBatchExecutionApprovalReady ?? approval.order_batch_execution_approval_ready,
    ),
    execution_approved: Boolean(approval.executionApproved ?? approval.execution_approved),
    real_api_called: Boolean(approval.realApiCalled ?? approval.real_api_called),
    real_database_written: Boolean(approval.realDatabaseWritten ?? approval.real_database_written),
    orders_written: Boolean(approval.ordersWritten ?? approval.orders_written),
    products_written: Boolean(approval.productsWritten ?? approval.products_written),
    sync_log_written: Boolean(approval.syncLogWritten ?? approval.sync_log_written),
    capability_tested_success_written: Boolean(
      approval.capabilityTestedSuccessWritten ?? approval.capability_tested_success_written,
    ),
    timeline_events_written: Boolean(approval.timelineEventsWritten ?? approval.timeline_events_written),
    operation_audit_rows_written: Boolean(approval.operationAuditRowsWritten ?? approval.operation_audit_rows_written),
    raw_response_saved: Boolean(approval.rawResponseSaved ?? approval.raw_response_saved),
    privacy_fields_redacted: approval.privacyFieldsRedacted ?? approval.privacy_fields_redacted ?? true,
    formal_sync_open: Boolean(approval.formalSyncOpen ?? approval.formal_sync_open),
    formal_order_sync_open: Boolean(approval.formalOrderSyncOpen ?? approval.formal_order_sync_open),
    formal_product_sync_open: Boolean(approval.formalProductSyncOpen ?? approval.formal_product_sync_open),
    platform_order_writes_enabled: Boolean(
      approval.platformOrderWritesEnabled ?? approval.platform_order_writes_enabled,
    ),
    platform_product_writes_enabled: Boolean(
      approval.platformProductWritesEnabled ?? approval.platform_product_writes_enabled,
    ),
    platform_writes_enabled: Boolean(approval.platformWritesEnabled ?? approval.platform_writes_enabled),
  };
}

function toNaverBatchExecutionApprovalReadonlyPayload(payload = {}) {
  return {
    actor_context: payload.actorContext || payload.actor_context || {},
    store_ids: Array.isArray(payload.storeIds)
      ? payload.storeIds.map(Number).filter(Boolean)
      : (Array.isArray(payload.store_ids) ? payload.store_ids.map(Number).filter(Boolean) : []),
    candidate_count: Number(payload.candidateCount ?? payload.candidate_count ?? 0),
    batch_size: Number(payload.batchSize ?? payload.batch_size ?? 0),
    readonly_evidence: payload.readonlyEvidence || payload.readonly_evidence || {},
    backup_evidence: payload.backupEvidence || payload.backup_evidence || {},
    manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    execution_context: payload.executionContext || payload.execution_context || {},
    readonly_api_context: payload.readonlyApiContext || payload.readonly_api_context || {},
  };
}

function toFormalBatchExecutionDryRunCandidateSummary(summary = {}) {
  return {
    sync_kind: summary.syncKind || summary.sync_kind || '',
    target: summary.target || '',
    store_ids: Array.isArray(summary.storeIds)
      ? summary.storeIds.map(Number).filter(Boolean)
      : (Array.isArray(summary.store_ids) ? summary.store_ids.map(Number).filter(Boolean) : []),
    candidate_count: Number(summary.candidateCount ?? summary.candidate_count ?? 0),
    would_create: Number(summary.wouldCreate ?? summary.would_create ?? 0),
    would_update: Number(summary.wouldUpdate ?? summary.would_update ?? 0),
    would_refresh_only: Number(summary.wouldRefreshOnly ?? summary.would_refresh_only ?? 0),
    would_skip: Number(summary.wouldSkip ?? summary.would_skip ?? 0),
    changed_fields: Array.isArray(summary.changedFields)
      ? summary.changedFields
      : (Array.isArray(summary.changed_fields) ? summary.changed_fields : []),
    execution_approved: Boolean(summary.executionApproved ?? summary.execution_approved),
    real_api_called: Boolean(summary.realApiCalled ?? summary.real_api_called),
    real_database_written: Boolean(summary.realDatabaseWritten ?? summary.real_database_written),
    orders_written: Boolean(summary.ordersWritten ?? summary.orders_written),
    products_written: Boolean(summary.productsWritten ?? summary.products_written),
    raw_response_saved: Boolean(summary.rawResponseSaved ?? summary.raw_response_saved),
    privacy_fields_redacted: summary.privacyFieldsRedacted ?? summary.privacy_fields_redacted ?? true,
  };
}

function toFormalBatchExecutionDryRunReadonlyPayload(payload = {}) {
  return {
    execution_preflight: payload.executionPreflight || payload.execution_preflight || {},
    dry_run_context: payload.dryRunContext || payload.dry_run_context || {},
    execution_plan: payload.executionPlan || payload.execution_plan || {},
    candidate_summaries: (
      payload.candidateSummaries || payload.candidate_summaries || []
    ).map(toFormalBatchExecutionDryRunCandidateSummary),
  };
}

function toFormalBatchExecutionApprovalReadonlyPayload(payload = {}) {
  return {
    execution_preflight: payload.executionPreflight || payload.execution_preflight || {},
    execution_dry_run: payload.executionDryRun || payload.execution_dry_run || {},
    final_approval_context: payload.finalApprovalContext || payload.final_approval_context || {},
  };
}

function toFormalBatchExecutionWriteBoundaryReadonlyPayload(payload = {}) {
  return {
    execution_approval: payload.executionApproval || payload.execution_approval || {},
    write_boundary_context: payload.writeBoundaryContext || payload.write_boundary_context || {},
    readonly_api_context: payload.readonlyApiContext || payload.readonly_api_context || {},
  };
}

function toFormalBatchPreExecutionWriteBoundaryReview(review = {}) {
  return {
    ...review,
    status: review.status || 'blocked',
    write_boundary_plan_ready: Boolean(review.write_boundary_plan_ready ?? review.writeBoundaryPlanReady),
    store_ids: Array.isArray(review.storeIds)
      ? review.storeIds.map(Number).filter(Boolean)
      : (Array.isArray(review.store_ids) ? review.store_ids.map(Number).filter(Boolean) : []),
    sync_kinds: Array.isArray(review.syncKinds)
      ? review.syncKinds
      : (Array.isArray(review.sync_kinds) ? review.sync_kinds : []),
    targets: Array.isArray(review.targets) ? review.targets : [],
    required_actions: Array.isArray(review.requiredActions)
      ? review.requiredActions
      : (Array.isArray(review.required_actions) ? review.required_actions : []),
    candidate_summary_count: Number(review.candidateSummaryCount ?? review.candidate_summary_count ?? 0),
    total_candidate_count: Number(review.totalCandidateCount ?? review.total_candidate_count ?? 0),
    execution_approved: Boolean(review.executionApproved ?? review.execution_approved),
    batch_execution_enabled: Boolean(review.batchExecutionEnabled ?? review.batch_execution_enabled),
    write_endpoint_enabled: Boolean(review.writeEndpointEnabled ?? review.write_endpoint_enabled),
    real_api_called: Boolean(review.realApiCalled ?? review.real_api_called),
    real_database_written: Boolean(review.realDatabaseWritten ?? review.real_database_written),
    orders_written: Boolean(review.ordersWritten ?? review.orders_written),
    products_written: Boolean(review.productsWritten ?? review.products_written),
    sync_log_written: Boolean(review.syncLogWritten ?? review.sync_log_written),
    capability_tested_success_written: Boolean(
      review.capabilityTestedSuccessWritten ?? review.capability_tested_success_written,
    ),
    timeline_events_written: Boolean(review.timelineEventsWritten ?? review.timeline_events_written),
    operation_audit_rows_written: Boolean(review.operationAuditRowsWritten ?? review.operation_audit_rows_written),
    raw_response_saved: Boolean(review.rawResponseSaved ?? review.raw_response_saved),
    secrets_saved: Boolean(review.secretsSaved ?? review.secrets_saved),
    privacy_fields_redacted: review.privacyFieldsRedacted ?? review.privacy_fields_redacted ?? true,
    formal_sync_open: Boolean(review.formalSyncOpen ?? review.formal_sync_open),
    formal_order_sync_open: Boolean(review.formalOrderSyncOpen ?? review.formal_order_sync_open),
    formal_product_sync_open: Boolean(review.formalProductSyncOpen ?? review.formal_product_sync_open),
    platform_order_writes_enabled: Boolean(review.platformOrderWritesEnabled ?? review.platform_order_writes_enabled),
    platform_product_writes_enabled: Boolean(review.platformProductWritesEnabled ?? review.platform_product_writes_enabled),
    platform_writes_enabled: Boolean(review.platformWritesEnabled ?? review.platform_writes_enabled),
  };
}

function toFormalBatchPreExecutionRefreshReadonlyPayload(payload = {}) {
  return {
    write_boundary_review: toFormalBatchPreExecutionWriteBoundaryReview(
      payload.writeBoundaryReview || payload.write_boundary_review || {},
    ),
    backup_refresh_evidence: payload.backupRefreshEvidence || payload.backup_refresh_evidence || {},
    audit_refresh_evidence: payload.auditRefreshEvidence || payload.audit_refresh_evidence || {},
    readonly_api_context: payload.readonlyApiContext || payload.readonly_api_context || {},
  };
}

const sourceMethods = {
  healthCheck: backendApi.healthCheck,
  getDashboardData: (params) => (isBackendSource ? getBackendDashboardData(params) : getMockDashboardData()),
  getDashboardSummary: async (params) => {
    if (!isBackendSource) return withMockFinancialSummary(await mockApi.getDashboardSummary(params));
    return adapters.dashboardSummary(await backendApi.getDashboardSummary(params)).summary;
  },
  getStoreOverview: async (params = {}) => {
    if (!isBackendSource) return adapters.storeOverview(mockStoreOverview(params));
    return adapters.storeOverview(await backendApi.getStoreOverview({
      include_inactive: params.includeInactive ?? params.include_inactive ?? false,
    }));
  },
  getDashboardSalesTrend: mockApi.getDashboardSalesTrend,
  getStores: async (params) => {
    if (!isBackendSource) return mockApi.getStores(params);
    return queryBackendRows(await getBackendStores(), params);
  },
  createStore: async (payload) => {
    if (!isBackendSource) return mockApi.createStore(payload);
    const result = adapters.store(await backendApi.createStore(adapters.toBackendStorePayload(payload)));
    resetBackendStoresCache();
    return result;
  },
  updateStore: async (storeId, payload) => {
    if (!isBackendSource) return mockApi.updateStore(storeId, payload);
    const result = adapters.store(await backendApi.updateStore(storeId, adapters.toBackendStorePayload(payload)));
    resetBackendStoresCache();
    return result;
  },
  getProducts: async (params) => {
    if (!isBackendSource) return mockApi.getProducts(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getProducts({ storeId: store.id, platform: params?.platform });
    const rows = withStoreName(adapters.list(result, adapters.product).data, stores);
    return queryBackendRows(rows, params);
  },
  getOrders: async (params) => {
    if (!isBackendSource) return mockApi.getOrders(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getOrders({ storeId: store.id, platform: params?.platform });
    const adapted = adapters.list(result, adapters.order);
    const rows = withStoreName(adapted.data, stores);
    return {
      ...queryBackendRows(rows, params),
      includeTestOrders: adapted.includeTestOrders,
      testOrdersExcluded: adapted.testOrdersExcluded,
    };
  },
  getOrderLogisticsTrace: async (order = {}) => {
    if (!isBackendSource) return adapters.orderLogisticsTrace(mockOrderLogisticsTrace(order));
    const { store } = await resolveBackendStore({ storeId: order.storeId || order.store_id });
    return adapters.orderLogisticsTrace(await backendApi.getOrderLogisticsTrace(order.id, { storeId: store.id }));
  },
  refreshSingleNaverOrderDetail: async (order = {}) => {
    if (!isBackendSource) return mockSingleNaverOrderDetailRefresh(order);
    const { store } = await resolveBackendStore({ storeId: order.storeId || order.store_id });
    const result = await backendApi.refreshSingleNaverOrderDetail({
      store_id: Number(store.id),
      order_id: Number(order.id),
    });
    const refreshedOrder = result.refreshed_order || result.refreshedOrder || null;
    return {
      status: result.status || '',
      message: result.message || '',
      errorCode: result.error_code || result.errorCode || '',
      updatedCount: Number(result.updated_count || result.updatedCount || 0),
      noChangeCount: Number(result.no_change_count || result.noChangeCount || 0),
      skippedCount: Number(result.skipped_count || result.skippedCount || 0),
      platformWrite: Boolean(result.platform_write || result.platformWrite),
      fieldAvailability: result.field_availability || result.fieldAvailability || {},
      order: refreshedOrder ? adapters.order(refreshedOrder) : null,
    };
  },
  getShippingLogisticsMappings: async (params = {}) => {
    if (!isBackendSource) {
      return {
        phase: 'Shipping-2B',
        status: 'mock_local_state_only',
        businessMessage: 'mock 模式使用页面内演示映射；不会读取或写入 Codex1 数据库。',
        data: [],
        items: [],
        total: 0,
        realDatabaseWritten: false,
        realApiCalled: false,
        ordersWritten: false,
        productsWritten: false,
        syncLogWritten: false,
        capabilityTestedSuccessWritten: false,
        rawResponseSaved: false,
        secretsSaved: false,
        privacyFieldsRedacted: true,
        formalOrderSyncOpen: false,
        platformWritesEnabled: false,
      };
    }
    const { store } = await resolveBackendStore(params);
    return adaptShippingMappingResult(await backendApi.getShippingLogisticsMappings({
      storeId: store.id,
      platform: params?.platform || 'naver',
    }));
  },
  checkShippingLogisticsMappingWriteGate: async (payload = {}) => {
    const request = toBackendShippingMappingPayload(payload);
    if (!isBackendSource) {
      return adaptShippingMappingResult({
        phase: 'Shipping-2C',
        status: request.manual_approval ? 'mapping_stock_write_gate_ready' : 'blocked',
        skip_reason: request.manual_approval ? null : 'manual_approval_required',
        business_message: request.manual_approval
          ? 'mock 模式门禁通过，但不会写入数据库。'
          : '请先确认本地保存操作。',
        mapping_rows_ready: request.mappings.length,
        inventory_rows_ready: new Set(request.mappings.map((item) => item.logistics_inventory_code)).size,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingMappingResult(await backendApi.checkShippingLogisticsMappingWriteGate({
      ...request,
      store_id: Number(store.id),
    }));
  },
  writeShippingLogisticsMappings: async (payload = {}) => {
    const request = toBackendShippingMappingPayload(payload);
    if (!isBackendSource) {
      return adaptShippingMappingResult({
        phase: 'Shipping-2D',
        status: request.manual_approval ? 'mock_mapping_stock_updated' : 'blocked',
        skip_reason: request.manual_approval ? null : 'manual_approval_required',
        business_message: request.manual_approval
          ? 'mock 模式已更新页面状态，不写入数据库。'
          : '请先确认本地保存操作。',
        items: request.mappings.map((item, index) => ({
          id: `mock-shipping-map-${index + 1}`,
          store_id: request.store_id,
          platform: request.platform,
          match_product_name: item.match_product_name,
          match_option_name: item.match_option_name,
          logistics_inventory_code: item.logistics_inventory_code,
          logistics_provider_name: item.logistics_provider_name,
          current_stock_quantity: item.current_stock_quantity,
          stock_status: item.current_stock_quantity <= 0 ? 'out_of_stock' : item.current_stock_quantity <= 3 ? 'low_stock' : 'available',
          is_active: item.is_active,
          mapping_version: 'shipping_mapping_mock_v1',
        })),
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        operation_audit_rows_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingMappingResult(await backendApi.writeShippingLogisticsMappings({
      ...request,
      store_id: Number(store.id),
    }));
  },
  generateShippingExcelExport: async (payload = {}) => {
    const request = toBackendShippingExcelExportPayload(payload);
    if (!isBackendSource) {
      return adaptShippingExcelExportResult({
        phase: 'Shipping-3D',
        status: request.manual_approval ? 'mock_excel_export_preview_ready' : 'blocked',
        skip_reason: request.manual_approval ? null : 'manual_approval_required',
        business_message: request.manual_approval
          ? 'mock 模式只生成页面预览，不创建真实 Excel 文件。'
          : '请先确认本地导出操作。',
        file_type: 'shipping_request',
        file_format: 'xlsx',
        row_count: request.export_rows.length,
        matched_row_count: request.export_rows.length,
        unmatched_row_count: 0,
        file_generated: false,
        file_persisted: false,
        export_record_written: false,
        download_record_written: false,
        operation_audit_rows_written: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        tracking_number_import_open: false,
        export_rows_preview: request.export_rows,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingExcelExportResult(await backendApi.generateShippingExcelExport({
      ...request,
      store_id: Number(store.id),
    }));
  },
  getShippingExportHistory: async (params = {}) => {
    if (!isBackendSource) {
      return adaptShippingExportHistoryResult({
        phase: 'Shipping-4D',
        status: 'mock_export_history_ready',
        business_message: 'mock 模式展示导出历史示例；不会读取或写入 Codex1 数据库。',
        export_history_readonly: true,
        readonly_route: true,
        tracking_number_import_open: false,
        shipment_writeback_open: false,
        import_record_written: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        total: 1,
        items: [{
          id: 'mock-shipping-export-1',
          store_id: params.storeId || params.store_id || 8,
          platform: 'naver',
          file_type: 'shipping_request',
          file_format: 'xlsx',
          file_name: 'naver-shipping-request-store-8-mock.xlsx',
          file_path: '',
          file_sha256: 'mock-sha256-shipping-export-history',
          row_count: 1,
          matched_row_count: 1,
          unmatched_row_count: 0,
          audit_correlation_id: 'mock-shipping-export-history',
          export_status: 'generated',
          include_receiver_privacy: false,
          file_generated: false,
          file_persisted: false,
          raw_response_saved: false,
          secrets_saved: false,
          privacy_fields_redacted: true,
          mapping_version: 'shipping_export_mock_v1',
          created_at: '2026-07-05T18:00:00+09:00',
          rows: [],
        }],
      });
    }
    const { store } = await resolveBackendStore(params);
    return adaptShippingExportHistoryResult(await backendApi.getShippingExportHistory({
      storeId: store.id,
      platform: params?.platform || 'naver',
      limit: params?.limit || 20,
      offset: params?.offset || 0,
      includeRows: params?.includeRows || false,
    }));
  },
  checkShippingTrackingImportMockParse: async (payload = {}) => {
    const request = toBackendShippingTrackingImportPayload(payload);
    if (!isBackendSource) {
      return adaptShippingTrackingImportMockParseResult({
        phase: 'Shipping-4B',
        status: request.manual_approval && request.parser_contract_acknowledged
          ? 'tracking_import_mock_parse_ready'
          : 'blocked',
        skip_reason: request.manual_approval
          ? (request.parser_contract_acknowledged ? null : 'tracking_parser_contract_required')
          : 'manual_approval_required',
        business_message: request.manual_approval && request.parser_contract_acknowledged
          ? 'mock 模式已验证物流单号导入字段；不会写订单，也不会回填 Naver。'
          : '请先确认导入解析门禁。',
        file_type: request.file_type,
        file_format: request.file_format,
        row_count: request.tracking_rows.length,
        ready_row_count: request.tracking_rows.length,
        duplicate_row_count: 0,
        file_parsed: request.manual_approval && request.parser_contract_acknowledged,
        parser_contract_acknowledged: request.parser_contract_acknowledged,
        tracking_number_import_open: false,
        tracking_numbers_written: false,
        shipment_writeback_open: false,
        shipment_writeback_called: false,
        import_record_written: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        tracking_rows_preview: request.tracking_rows.map((row, index) => ({
          row_index: index + 1,
          ...row,
          row_status: 'ready_for_future_review',
          future_write_allowed: false,
        })),
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingTrackingImportMockParseResult(await backendApi.checkShippingTrackingImportMockParse({
      ...request,
      store_id: Number(store.id),
    }));
  },
  checkShippingTrackingImportXlsxParserMock: async (payload = {}) => {
    const request = toBackendShippingTrackingImportXlsxParsePayload(payload);
    if (!isBackendSource) {
      const approved = request.manual_approval && request.parser_contract_acknowledged && request.file_content_base64;
      const skipReason = !request.manual_approval
        ? 'manual_approval_required'
        : (!request.parser_contract_acknowledged ? 'tracking_parser_contract_required' : 'tracking_xlsx_file_required');
      return adaptShippingTrackingImportMockParseResult({
        phase: 'Shipping-7B',
        status: approved ? 'tracking_xlsx_parser_mock_ready' : 'blocked',
        skip_reason: approved ? null : skipReason,
        business_message: approved
          ? 'Mock xlsx parser preview is ready. The file is not saved, rows are not written, and Naver is not called.'
          : 'Please confirm parser approval before previewing the uploaded xlsx.',
        file_type: request.file_type,
        file_format: request.file_format,
        source_file_name: request.source_file_name,
        parser_version: 'shipping_tracking_import_xlsx_parser_v1',
        file_received: Boolean(request.file_content_base64),
        file_parsed: Boolean(approved),
        file_size_bytes: Math.round((request.file_content_base64.length * 3) / 4),
        file_content_saved: false,
        parsed_rows_written: false,
        import_record_written: false,
        tracking_number_import_open: false,
        tracking_numbers_written: false,
        shipment_writeback_open: false,
        shipment_writeback_called: false,
        orders_updated: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        integration_plan_ready: Boolean(approved),
        next_action: 'review_parsed_rows_then_use_existing_tracking_import_write_gate',
        mapped_columns: [
          'order_reference',
          'product_order_reference',
          'logistics_inventory_code',
          'carrier',
          'tracking_number',
        ],
        unknown_columns: [],
        row_count: approved ? 1 : 0,
        ready_row_count: approved ? 1 : 0,
        duplicate_row_count: 0,
        tracking_rows_preview: approved ? [{
          row_index: 1,
          order_reference: 'mock-shipping-order-001',
          product_order_reference: 'mock-product-order-001',
          logistics_inventory_code: 'PXG-AUTO-MATCH-001',
          carrier: 'Mock carrier',
          tracking_number: 'MOCKTRACK001',
          shipped_at: '2026-07-05T18:10:00+09:00',
          row_status: 'ready_for_future_review',
          operator_note: 'mock xlsx parser preview only',
          future_write_allowed: false,
        }] : [],
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingTrackingImportMockParseResult(await backendApi.checkShippingTrackingImportXlsxParserMock({
      ...request,
      store_id: Number(store.id),
    }));
  },
  checkShippingTrackingImportWriteGate: async (payload = {}) => {
    const request = toBackendShippingTrackingImportPayload(payload);
    if (!isBackendSource) {
      return adaptShippingTrackingImportMockParseResult({
        phase: 'Shipping-5C',
        status: request.manual_approval && request.parser_contract_acknowledged
          ? 'tracking_import_local_write_gate_ready'
          : 'blocked',
        skip_reason: request.manual_approval
          ? (request.parser_contract_acknowledged ? null : 'tracking_parser_contract_required')
          : 'manual_approval_required',
        business_message: request.manual_approval && request.parser_contract_acknowledged
          ? 'Mock tracking import write gate passed. No database write is performed in mock mode.'
          : 'Tracking import write gate is not ready.',
        file_type: request.file_type,
        file_format: request.file_format,
        row_count: request.tracking_rows.length,
        ready_row_count: request.tracking_rows.length,
        duplicate_row_count: 0,
        tracking_import_records_written: false,
        tracking_import_batch_written: false,
        tracking_import_rows_written: false,
        operation_audit_rows_written: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        platform_writes_enabled: false,
        tracking_rows_preview: request.tracking_rows,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingTrackingImportMockParseResult(await backendApi.checkShippingTrackingImportWriteGate({
      ...request,
      store_id: Number(store.id),
    }));
  },
  writeShippingTrackingImport: async (payload = {}) => {
    const request = toBackendShippingTrackingImportPayload(payload);
    if (!isBackendSource) {
      return adaptShippingTrackingImportMockParseResult({
        phase: 'Shipping-5D',
        status: request.manual_approval && request.parser_contract_acknowledged
          ? 'mock_tracking_import_local_record_ready'
          : 'blocked',
        skip_reason: request.manual_approval
          ? (request.parser_contract_acknowledged ? null : 'tracking_parser_contract_required')
          : 'manual_approval_required',
        business_message: request.manual_approval && request.parser_contract_acknowledged
          ? 'Mock tracking import record is ready. Codex1 database is not written in mock mode.'
          : 'Tracking import local write is not ready.',
        file_type: request.file_type,
        file_format: request.file_format,
        row_count: request.tracking_rows.length,
        ready_row_count: request.tracking_rows.length,
        duplicate_row_count: 0,
        tracking_import_records_written: false,
        tracking_import_batch_written: false,
        tracking_import_rows_written: false,
        operation_audit_rows_written: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        platform_writes_enabled: false,
        tracking_rows_preview: request.tracking_rows,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingTrackingImportMockParseResult(await backendApi.writeShippingTrackingImport({
      ...request,
      store_id: Number(store.id),
    }));
  },
  getShippingTrackingImportHistory: async (params = {}) => {
    if (!isBackendSource) {
      return adaptShippingTrackingImportHistoryResult({
        phase: 'Shipping-5E',
        status: 'mock_tracking_import_history_ready',
        business_message: 'Mock tracking import history. Codex1 database is not read or written in mock mode.',
        tracking_import_history_readonly: true,
        readonly_route: true,
        tracking_number_import_open: false,
        shipment_writeback_open: false,
        shipment_writeback_called: false,
        orders_updated: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        total: 1,
        items: [{
          id: 'mock-shipping-tracking-import-1',
          store_id: params.storeId || params.store_id || 8,
          platform: 'naver',
          file_type: 'tracking_upload',
          file_format: 'xlsx',
          source_file_name: 'tracking-upload-mock.xlsx',
          row_count: 1,
          ready_row_count: 1,
          duplicate_row_count: 0,
          blocked_row_count: 0,
          audit_correlation_id: 'mock-shipping-tracking-import-history',
          import_status: 'recorded',
          parser_contract_acknowledged: true,
          tracking_number_import_open: false,
          shipment_writeback_called: false,
          orders_updated: false,
          raw_response_saved: false,
          secrets_saved: false,
          privacy_fields_redacted: true,
          mapping_version: 'shipping_tracking_import_mock_v1',
          created_at: '2026-07-05T18:10:00+09:00',
          rows: [],
        }],
      });
    }
    const { store } = await resolveBackendStore(params);
    return adaptShippingTrackingImportHistoryResult(await backendApi.getShippingTrackingImportHistory({
      storeId: store.id,
      platform: params?.platform || 'naver',
      limit: params?.limit || 20,
      offset: params?.offset || 0,
      includeRows: params?.includeRows || false,
    }));
  },
  checkShippingTrackingOrderMatchReadonly: async (payload = {}) => {
    const request = toBackendShippingTrackingOrderMatchPayload(payload);
    if (!isBackendSource) {
      return adaptShippingTrackingOrderMatchResult({
        phase: 'Shipping-6B',
        status: 'tracking_order_match_readonly_ready',
        business_message: 'Mock tracking rows have been compared with local orders. No order is updated.',
        readonly_route: true,
        tracking_order_match_readonly: true,
        matching_contract_acknowledged: true,
        import_batch_id: request.import_batch_id,
        total_tracking_rows: 1,
        matched_order_count: 1,
        unmatched_order_count: 0,
        duplicate_tracking_row_count: 0,
        tracking_number_import_open: false,
        shipment_writeback_open: false,
        shipment_writeback_called: false,
        orders_updated: false,
        tracking_rows_written: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        match_rows: [{
          row_index: 1,
          order_reference: 'mock-shipping-order-001',
          product_order_reference: 'mock-product-order-001',
          logistics_inventory_code: 'PXG-AUTO-MATCH-001',
          carrier: 'Mock carrier',
          tracking_number: 'MOCKTRACK001',
          shipped_at: '2026-07-05T18:10:00+09:00',
          row_status: 'ready_for_future_review',
          match_status: 'matched_existing_order',
          match_method: 'order_reference',
          future_write_allowed: false,
          order_summary: {
            local_order_id: 'mock-order-1',
            order_reference: 'mock-shipping-order-001',
            order_status: 'PAYED',
            product_name: 'PXG Wheel Bag',
            quantity: 1,
            source_type: 'mock_shipping_order',
          },
        }],
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingTrackingOrderMatchResult(await backendApi.checkShippingTrackingOrderMatchReadonly({
      ...request,
      store_id: Number(store.id),
    }));
  },
  checkShippingTrackingOrderStatusLocalUpdateGate: async (payload = {}) => {
    const request = toBackendShippingTrackingOrderStatusLocalUpdatePayload(payload);
    if (!isBackendSource) {
      const missingReason = !request.manual_approval
        ? 'manual_approval_required'
        : (!request.backup_evidence_acknowledged
          ? 'backup_evidence_required'
          : (!request.audit_evidence_acknowledged
            ? 'audit_evidence_required'
            : (!request.operator_checklist_acknowledged ? 'operator_checklist_required' : null)));
      return adaptShippingTrackingOrderStatusLocalUpdateResult({
        phase: 'Shipping-8B',
        status: missingReason ? 'blocked' : 'tracking_order_status_update_gate_ready',
        skip_reason: missingReason,
        business_message: missingReason
          ? 'Mock local status update is waiting for approval evidence.'
          : 'Mock local status update gate is ready. Backend mode writes local order status only.',
        tracking_order_status_local_update_gate: true,
        manual_approval: request.manual_approval,
        matching_contract_acknowledged: request.matching_contract_acknowledged,
        backup_evidence_acknowledged: request.backup_evidence_acknowledged,
        audit_evidence_acknowledged: request.audit_evidence_acknowledged,
        operator_checklist_acknowledged: request.operator_checklist_acknowledged,
        target_order_status: 'DISPATCHED',
        target_order_status_label_zh: '已发货 / 配送中',
        import_batch_id: request.import_batch_id,
        matched_order_count: 1,
        update_candidate_count: missingReason ? 0 : 1,
        already_updated_count: 0,
        blocked_order_count: 0,
        duplicate_tracking_row_count: 0,
        unmatched_order_count: 0,
        update_candidates: missingReason ? [] : [{
          local_order_id: 'mock-order-1',
          current_order_status: 'PAYED',
          next_order_status: 'DISPATCHED',
          tracking_number_hash: 'id-hash-mocktracking001',
          carrier: 'Mock carrier',
          shipped_at: '2026-07-05T18:10:00+09:00',
        }],
        orders_updated: false,
        orders_written: false,
        order_status_events_written: false,
        tracking_import_batch_updated: false,
        operation_audit_rows_written: false,
        real_database_written: false,
        real_api_called: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        shipment_writeback_called: false,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingTrackingOrderStatusLocalUpdateResult(
      await backendApi.checkShippingTrackingOrderStatusLocalUpdateGate({
        ...request,
        store_id: Number(store.id),
      }),
    );
  },
  writeShippingTrackingOrderStatusLocalUpdate: async (payload = {}) => {
    const request = toBackendShippingTrackingOrderStatusLocalUpdatePayload(payload);
    if (!isBackendSource) {
      const approved = request.manual_approval
        && request.backup_evidence_acknowledged
        && request.audit_evidence_acknowledged
        && request.operator_checklist_acknowledged
        && request.matching_contract_acknowledged;
      return adaptShippingTrackingOrderStatusLocalUpdateResult({
        phase: 'Shipping-8C',
        status: approved ? 'mock_tracking_order_status_update_ready' : 'tracking_order_status_update_blocked',
        skip_reason: approved ? null : 'approval_evidence_required',
        business_message: approved
          ? 'Mock mode shows the local status update path. No database row is written.'
          : 'Mock local status update requires approval evidence.',
        tracking_order_status_local_update: true,
        manual_approval: request.manual_approval,
        matching_contract_acknowledged: request.matching_contract_acknowledged,
        backup_evidence_acknowledged: request.backup_evidence_acknowledged,
        audit_evidence_acknowledged: request.audit_evidence_acknowledged,
        operator_checklist_acknowledged: request.operator_checklist_acknowledged,
        target_order_status: 'DISPATCHED',
        target_order_status_label_zh: '已发货 / 配送中',
        import_batch_id: request.import_batch_id,
        matched_order_count: 1,
        update_candidate_count: approved ? 1 : 0,
        updated_order_count: 0,
        updated_order_ids: [],
        event_rows_written: 0,
        orders_updated: false,
        orders_written: false,
        order_status_events_written: false,
        tracking_import_batch_updated: false,
        operation_audit_rows_written: false,
        real_database_written: false,
        real_api_called: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        shipment_writeback_called: false,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingTrackingOrderStatusLocalUpdateResult(
      await backendApi.writeShippingTrackingOrderStatusLocalUpdate({
        ...request,
        store_id: Number(store.id),
      }),
    );
  },
  checkShippingShipmentWritebackBoundary: async (payload = {}) => {
    const request = toBackendShippingShipmentWritebackBoundaryPayload(payload);
    if (!isBackendSource) {
      const missingActions = request.manual_approval
        ? []
        : ['manual_approval'];
      return adaptShippingShipmentWritebackBoundaryResult({
        phase: 'Shipping-6C',
        status: missingActions.length ? 'blocked' : 'shipment_writeback_boundary_ready',
        skip_reason: missingActions[0] || null,
        business_message: missingActions.length
          ? 'Mock shipment writeback remains closed until approval is complete.'
          : 'Mock shipment writeback boundary is ready for review only. No Naver API is called.',
        readonly_route: true,
        shipment_writeback_boundary_review: true,
        manual_approval: request.manual_approval,
        matched_order_count: request.matched_order_count,
        total_tracking_rows: request.total_tracking_rows,
        matching_evidence_acknowledged: request.matching_evidence_acknowledged,
        backup_evidence_acknowledged: request.backup_evidence_acknowledged,
        audit_evidence_acknowledged: request.audit_evidence_acknowledged,
        naver_writeback_boundary_acknowledged: request.naver_writeback_boundary_acknowledged,
        operator_checklist_acknowledged: request.operator_checklist_acknowledged,
        required_actions: [
          'manual_approval',
          'matched_order_evidence',
          'matching_evidence_acknowledged',
          'backup_evidence_acknowledged',
          'audit_evidence_acknowledged',
          'naver_writeback_boundary_acknowledged',
          'operator_checklist_acknowledged',
        ],
        missing_actions: missingActions,
        tracking_number_import_open: false,
        shipment_writeback_open: false,
        shipment_writeback_called: false,
        orders_updated: false,
        real_database_written: false,
        real_api_called: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingShipmentWritebackBoundaryResult(await backendApi.checkShippingShipmentWritebackBoundary({
      ...request,
      store_id: Number(store.id),
    }));
  },
  checkShippingShipmentWritebackDryRunGate: async (payload = {}) => {
    const request = toBackendShippingShipmentWritebackDryRunGatePayload(payload);
    if (!isBackendSource) {
      const missingReason = !request.manual_approval
        ? 'manual_approval_required'
        : (!request.backup_evidence_acknowledged
          ? 'backup_evidence_required'
          : (!request.audit_evidence_acknowledged
            ? 'audit_evidence_required'
            : (!request.local_status_evidence_acknowledged
              ? 'local_status_evidence_required'
              : (!request.naver_writeback_boundary_acknowledged
                ? 'naver_writeback_boundary_required'
                : (!request.operator_checklist_acknowledged ? 'operator_checklist_required' : null)))));
      return adaptShippingShipmentWritebackDryRunGateResult({
        phase: 'Shipping-8F',
        status: missingReason ? 'blocked' : 'shipment_writeback_dry_run_gate_ready',
        skip_reason: missingReason,
        business_message: missingReason
          ? 'Mock shipment writeback dry-run is waiting for approval evidence.'
          : 'Mock shipment writeback dry-run evidence is ready. No Naver API is called.',
        readonly_route: true,
        shipment_writeback_dry_run_gate: true,
        shipment_writeback_dry_run_ready: !missingReason,
        future_platform_write_requires_separate_approval: true,
        manual_approval: request.manual_approval,
        matching_contract_acknowledged: request.matching_contract_acknowledged,
        backup_evidence_acknowledged: request.backup_evidence_acknowledged,
        audit_evidence_acknowledged: request.audit_evidence_acknowledged,
        local_status_evidence_acknowledged: request.local_status_evidence_acknowledged,
        naver_writeback_boundary_acknowledged: request.naver_writeback_boundary_acknowledged,
        operator_checklist_acknowledged: request.operator_checklist_acknowledged,
        target_delivery_status: request.target_delivery_status,
        target_delivery_status_label_zh: '已发货 / 配送中',
        import_batch_id: request.import_batch_id,
        total_tracking_rows: 1,
        matched_order_count: 1,
        unmatched_order_count: 0,
        duplicate_tracking_row_count: 0,
        dry_run_candidate_count: missingReason ? 0 : 1,
        blocked_order_count: 0,
        tracking_number_import_open: false,
        shipment_writeback_open: false,
        shipment_writeback_called: false,
        orders_updated: false,
        order_status_events_written: false,
        tracking_import_batch_updated: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        platform_writes_enabled: false,
        real_database_written: false,
        real_api_called: false,
        dry_run_candidates: missingReason ? [] : [{
          local_order_id: 'mock-order-1',
          order_reference_hash: 'id-hash-mockshippingorder',
          product_order_reference_hash: 'id-hash-mockproductorder',
          tracking_number_hash: 'id-hash-mocktracking001',
          carrier: 'Mock carrier',
          shipped_at: '2026-07-05T18:10:00+09:00',
          current_order_status: 'DISPATCHED',
          target_delivery_status: 'DISPATCHED',
          payload_preview_saved: false,
          raw_response_saved: false,
          future_write_allowed: false,
        }],
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingShipmentWritebackDryRunGateResult(
      await backendApi.checkShippingShipmentWritebackDryRunGate({
        ...request,
        store_id: Number(store.id),
      }),
    );
  },
  checkShippingShipmentWritebackExecutionMockGate: async (payload = {}) => {
    const request = toBackendShippingShipmentWritebackExecutionMockGatePayload(payload);
    if (!isBackendSource) {
      const missingReason = !request.execution_approval
        ? 'execution_approval_required'
        : (!request.dry_run_evidence_acknowledged
          ? 'dry_run_evidence_required'
          : (!request.permission_evidence_acknowledged
            ? 'permission_evidence_required'
            : (!request.final_operator_confirmation
              ? 'final_operator_confirmation_required'
              : (!request.manual_approval
                ? 'manual_approval_required'
                : (!request.backup_evidence_acknowledged
                  ? 'backup_evidence_required'
                  : (!request.audit_evidence_acknowledged
                    ? 'audit_evidence_required'
                    : (!request.local_status_evidence_acknowledged
                      ? 'local_status_evidence_required'
                      : (!request.naver_writeback_boundary_acknowledged
                        ? 'naver_writeback_boundary_required'
                        : (!request.operator_checklist_acknowledged ? 'operator_checklist_required' : null)))))))));
      return adaptShippingShipmentWritebackExecutionMockGateResult({
        phase: 'Shipping-9B',
        status: missingReason ? 'blocked' : 'shipment_writeback_execution_mock_gate_ready',
        skip_reason: missingReason,
        business_message: missingReason
          ? 'Mock execution gate is waiting for final approval evidence.'
          : 'Mock execution evidence is ready for review. Naver is still not called.',
        readonly_route: true,
        shipment_writeback_execution_mock_gate: true,
        shipment_writeback_execution_ready: !missingReason,
        execution_approval: request.execution_approval,
        dry_run_evidence_acknowledged: request.dry_run_evidence_acknowledged,
        permission_evidence_acknowledged: request.permission_evidence_acknowledged,
        final_operator_confirmation: request.final_operator_confirmation,
        real_api_call_requested: request.real_api_call_requested,
        future_real_write_requires_separate_approval: true,
        import_batch_id: request.import_batch_id,
        dry_run_status: missingReason ? 'blocked' : 'shipment_writeback_dry_run_gate_ready',
        dry_run_candidate_count: missingReason ? 0 : 1,
        execution_candidate_count: missingReason ? 0 : 1,
        matched_order_count: missingReason ? 0 : 1,
        unmatched_order_count: 0,
        execution_candidates: missingReason ? [] : [{
          local_order_id: 'mock-order-1',
          order_reference_hash: 'id-hash-mockshippingorder',
          product_order_reference_hash: 'id-hash-mockproductorder',
          tracking_number_hash: 'id-hash-mocktracking001',
          carrier: 'Mock carrier',
          shipped_at: '2026-07-05T18:10:00+09:00',
          current_order_status: 'DISPATCHED',
          target_delivery_status: 'DISPATCHED',
          execution_allowed: false,
          future_write_allowed: false,
          payload_preview_saved: false,
          raw_response_saved: false,
        }],
        shipment_writeback_open: false,
        shipment_writeback_called: false,
        platform_writes_enabled: false,
        orders_updated: false,
        order_status_events_written: false,
        tracking_import_batch_updated: false,
        orders_written: false,
        products_written: false,
        sync_log_written: false,
        capability_tested_success_written: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_order_sync_open: false,
        real_database_written: false,
        real_api_called: false,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingShipmentWritebackExecutionMockGateResult(
      await backendApi.checkShippingShipmentWritebackExecutionMockGate({
        ...request,
        store_id: Number(store.id),
      }),
    );
  },
  executeShippingShipmentWriteback: async (payload = {}) => {
    const request = {
      ...toBackendShippingShipmentWritebackExecutionMockGatePayload(payload),
      real_api_call_requested: Boolean(payload.realApiCallRequested ?? payload.real_api_call_requested),
    };
    if (!isBackendSource) {
      return adaptShippingShipmentWritebackExecuteResult({
        phase: 'Shipping-10A',
        status: 'blocked',
        skip_reason: 'demo_source_no_platform_write',
        business_message: '演示数据源不会调用 Naver 发货回填。',
        shipment_writeback_execute: true,
        platform_write: false,
        platform_write_attempted: false,
        real_api_called: false,
        shipment_writeback_called: false,
        raw_response_saved: false,
        secrets_saved: false,
      });
    }
    const { store } = await resolveBackendStore({ storeId: request.store_id });
    return adaptShippingShipmentWritebackExecuteResult(
      await backendApi.executeShippingShipmentWriteback({
        ...request,
        store_id: Number(store.id),
      }),
    );
  },
  getRolePermissionInventory: async () => {
    if (!isBackendSource) {
      return {
        phase: 'ERP-Auth-1F',
        status: 'role_inventory_ready',
        businessMessage: '当前仅开放本地角色权限模型预览，用于页面展示和后续审批设计；正式登录权限系统尚未开放。',
        roles: mockRolePermissions,
        ...permissionSafetyFlags(),
      };
    }
    const result = await backendApi.getRolePermissionInventory();
    return {
      ...result,
      businessMessage: result.business_message || result.businessMessage,
      mockPermissionApi: Boolean(result.mock_permission_api),
      publicEndpointEnabled: Boolean(result.public_endpoint_enabled),
      realAuthSessionCreated: Boolean(result.real_auth_session_created),
      realDatabaseWritten: Boolean(result.real_database_written),
      formalSyncOpen: Boolean(result.formal_sync_open),
      platformWritesEnabled: Boolean(result.platform_writes_enabled),
    };
  },
  checkPermissionMock: async (payload = {}) => {
    const request = {
      actor_context: payload.actorContext || payload.actor_context || {},
      store_id: Number(payload.storeId || payload.store_id),
      operation_key: payload.operationKey || payload.operation_key,
    };
    if (!isBackendSource) {
      return adaptPermissionGateResult(mockPermissionGate({
        actorContext: request.actor_context,
        storeId: request.store_id,
        operationKey: request.operation_key,
      }));
    }
    return adaptPermissionGateResult(await backendApi.checkPermissionMock(request));
  },
  checkSensitiveActionPermissionMock: async (payload = {}) => {
    const request = {
      actor_context: payload.actorContext || payload.actor_context || {},
      store_id: Number(payload.storeId || payload.store_id),
      action_key: payload.actionKey || payload.action_key,
      manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
    };
    if (!isBackendSource) {
      return adaptPermissionGateResult(mockSensitiveActionGate({
        actorContext: request.actor_context,
        storeId: request.store_id,
        actionKey: request.action_key,
        manualApproval: request.manual_approval,
      }));
    }
    return adaptPermissionGateResult(await backendApi.checkSensitiveActionPermissionMock(request));
  },
  checkStoreMembershipReadonly: async (payload = {}) => {
    const request = {
      actor_context: payload.actorContext || payload.actor_context || {},
      target_user_key_hash: payload.targetUserKeyHash || payload.target_user_key_hash,
      target_store_id: Number(payload.targetStoreId || payload.target_store_id),
      target_role: payload.targetRole || payload.target_role,
      manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
      assignment_reason: payload.assignmentReason || payload.assignment_reason || 'readonly membership check',
    };
    if (!isBackendSource) return adaptStoreMembershipReadonlyResult(mockStoreMembershipReadonlyGate(request));
    return adaptStoreMembershipReadonlyResult(await backendApi.checkStoreMembershipReadonly(request));
  },
  checkUserInvitationReadonly: async (payload = {}) => {
    const request = {
      actor_context: payload.actorContext || payload.actor_context || {},
      target_user_key_hash: payload.targetUserKeyHash || payload.target_user_key_hash,
      login_identifier_hash: payload.loginIdentifierHash || payload.login_identifier_hash,
      login_identifier_masked: payload.loginIdentifierMasked || payload.login_identifier_masked,
      target_store_ids: payload.targetStoreIds || payload.target_store_ids || [],
      target_role: payload.targetRole || payload.target_role,
      manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
      invitation_reason: payload.invitationReason || payload.invitation_reason || 'readonly user invitation check',
      backup_evidence_planned: Boolean(payload.backupEvidencePlanned ?? payload.backup_evidence_planned),
      audit_evidence_planned: Boolean(payload.auditEvidencePlanned ?? payload.audit_evidence_planned),
      membership_assignment_plan_ready: Boolean(payload.membershipAssignmentPlanReady ?? payload.membership_assignment_plan_ready),
      existing_user_hashes: payload.existingUserHashes || payload.existing_user_hashes || [],
    };
    if (!isBackendSource) return adaptUserInvitationReadonlyResult(mockUserInvitationReadonlyGate(request));
    return adaptUserInvitationReadonlyResult(await backendApi.checkUserInvitationReadonly(request));
  },
  checkUserInvitationApprovalChecklistReadonly: async (payload = {}) => {
    const request = {
      actor_context: payload.actorContext || payload.actor_context || {},
      target_user_key_hash: payload.targetUserKeyHash || payload.target_user_key_hash,
      login_identifier_hash: payload.loginIdentifierHash || payload.login_identifier_hash,
      login_identifier_masked: payload.loginIdentifierMasked || payload.login_identifier_masked,
      target_store_ids: payload.targetStoreIds || payload.target_store_ids || [],
      target_role: payload.targetRole || payload.target_role,
      manual_approval: Boolean(payload.manualApproval ?? payload.manual_approval),
      invitation_reason: payload.invitationReason || payload.invitation_reason || 'readonly user invitation approval checklist check',
      approval_checklist: payload.approvalChecklist || payload.approval_checklist || {},
      readonly_api_context: payload.readonlyApiContext || payload.readonly_api_context || {},
      existing_user_hashes: payload.existingUserHashes || payload.existing_user_hashes || [],
    };
    if (!isBackendSource) {
      return adaptUserInvitationApprovalChecklistReadonlyResult(
        mockUserInvitationApprovalChecklistReadonlyGate(request),
      );
    }
    return adaptUserInvitationApprovalChecklistReadonlyResult(
      await backendApi.checkUserInvitationApprovalChecklistReadonly(request),
    );
  },
  checkUserInvitationApprovalAuditLinkageReadonly: async (payload = {}) => {
    const request = {
      invitation_approval: payload.invitationApproval || payload.invitation_approval || {},
      audit_linkage_context: payload.auditLinkageContext || payload.audit_linkage_context || {},
      readonly_api_context: payload.readonlyApiContext || payload.readonly_api_context || {},
    };
    if (!isBackendSource) {
      return adaptUserInvitationApprovalAuditLinkageReadonlyResult(
        mockUserInvitationApprovalAuditLinkageReadonlyGate(request),
      );
    }
    return adaptUserInvitationApprovalAuditLinkageReadonlyResult(
      await backendApi.checkUserInvitationApprovalAuditLinkageReadonly(request),
    );
  },
  normalizeBatchReadonlyEvidence: async (payload = {}) => {
    const request = {
      max_items: Number(payload.maxItems ?? payload.max_items ?? 10),
      evidence_items: payload.evidenceItems || payload.evidence_items || [],
    };
    if (!isBackendSource) return mockBatchReadonlyEvidence(request);
    return adaptBatchReadonlyEvidenceResult(await backendApi.normalizeBatchReadonlyEvidence(request));
  },
  checkBatchApprovalAuditEvidence: async (payload = {}) => {
    const request = {
      readonly_evidence: toBatchApprovalReadonlyEvidencePayload(payload.readonlyEvidence || payload.readonly_evidence || {}),
      approval_context: payload.approvalContext || payload.approval_context || {},
      audit_evidence_plan: payload.auditEvidencePlan || payload.audit_evidence_plan || {},
    };
    if (!isBackendSource) return mockBatchApprovalAuditEvidence(request);
    return adaptBatchApprovalAuditEvidenceResult(await backendApi.checkBatchApprovalAuditEvidence(request));
  },
  checkBatchApprovalDecisionReadonly: async (payload = {}) => {
    const request = {
      readonly_evidence: toBatchApprovalReadonlyEvidencePayload(payload.readonlyEvidence || payload.readonly_evidence || {}),
      approval_audit_evidence: toBatchApprovalAuditEvidencePayload(
        payload.approvalAuditEvidence || payload.approval_audit_evidence || {},
      ),
      decision_context: payload.decisionContext || payload.decision_context || {},
      readonly_api_context: payload.readonlyApiContext || payload.readonly_api_context || {},
    };
    if (!isBackendSource) return mockBatchApprovalDecisionReadonly(request);
    return adaptBatchApprovalDecisionReadonlyResult(await backendApi.checkBatchApprovalDecisionReadonly(request));
  },
  checkBatchApprovalDecisionAuditLinkageReadonly: async (payload = {}) => {
    const request = {
      approval_decision: toBatchApprovalDecisionPayload(payload.approvalDecision || payload.approval_decision || {}),
      audit_linkage_context: payload.auditLinkageContext || payload.audit_linkage_context || {},
      readonly_api_context: payload.readonlyApiContext || payload.readonly_api_context || {},
    };
    if (!isBackendSource) return mockBatchApprovalDecisionAuditLinkageReadonly(request);
    return adaptBatchApprovalDecisionAuditLinkageReadonlyResult(
      await backendApi.checkBatchApprovalDecisionAuditLinkageReadonly(request),
    );
  },
  checkNaverProductBatchExecutionApprovalReadonly: async (payload = {}) => {
    const request = toNaverBatchExecutionApprovalReadonlyPayload(payload);
    if (!isBackendSource) return mockNaverBatchExecutionApprovalReadonly(request, 'product');
    return adaptNaverBatchExecutionApprovalReadonlyResult(
      await backendApi.checkNaverProductBatchExecutionApprovalReadonly(request),
      'product',
    );
  },
  checkNaverOrderBatchExecutionApprovalReadonly: async (payload = {}) => {
    const request = toNaverBatchExecutionApprovalReadonlyPayload(payload);
    if (!isBackendSource) return mockNaverBatchExecutionApprovalReadonly(request, 'order');
    return adaptNaverBatchExecutionApprovalReadonlyResult(
      await backendApi.checkNaverOrderBatchExecutionApprovalReadonly(request),
      'order',
    );
  },
  checkFormalBatchExecutionPreflightReadonly: async (payload = {}) => {
    const request = {
      approval_decision: toBatchApprovalDecisionPayload(payload.approvalDecision || payload.approval_decision || {}),
      approval_audit_linkage: toBatchApprovalDecisionAuditLinkagePayload(
        payload.approvalAuditLinkage || payload.approval_audit_linkage || {},
      ),
      execution_approvals: (
        payload.executionApprovals || payload.execution_approvals || []
      ).map(toBatchExecutionApprovalPayload),
      preflight_context: payload.preflightContext || payload.preflight_context || {},
    };
    if (!isBackendSource) return mockFormalBatchExecutionPreflightReadonly(request);
    return adaptFormalBatchExecutionPreflightReadonlyResult(
      await backendApi.checkFormalBatchExecutionPreflightReadonly(request),
    );
  },
  checkFormalBatchExecutionDryRunReadonly: async (payload = {}) => {
    const request = toFormalBatchExecutionDryRunReadonlyPayload(payload);
    if (!isBackendSource) return mockFormalBatchExecutionDryRunReadonly(request);
    return adaptFormalBatchExecutionDryRunReadonlyResult(
      await backendApi.checkFormalBatchExecutionDryRunReadonly(request),
    );
  },
  checkFormalBatchExecutionApprovalReadonly: async (payload = {}) => {
    const request = toFormalBatchExecutionApprovalReadonlyPayload(payload);
    if (!isBackendSource) return mockFormalBatchExecutionApprovalReadonly(request);
    return adaptFormalBatchExecutionApprovalReadonlyResult(
      await backendApi.checkFormalBatchExecutionApprovalReadonly(request),
    );
  },
  checkFormalBatchExecutionWriteBoundaryReadonly: async (payload = {}) => {
    const request = toFormalBatchExecutionWriteBoundaryReadonlyPayload(payload);
    if (!isBackendSource) return mockFormalBatchExecutionWriteBoundaryReadonly(request);
    return adaptFormalBatchExecutionWriteBoundaryReadonlyResult(
      await backendApi.checkFormalBatchExecutionWriteBoundaryReadonly(request),
    );
  },
  checkFormalBatchPreExecutionRefreshReadonly: async (payload = {}) => {
    const request = toFormalBatchPreExecutionRefreshReadonlyPayload(payload);
    if (!isBackendSource) return mockFormalBatchPreExecutionRefreshReadonly(request);
    return adaptFormalBatchPreExecutionRefreshReadonlyResult(
      await backendApi.checkFormalBatchPreExecutionRefreshReadonly(request),
    );
  },
  getNaverProductRollbackReadonlyReport: async (payload = {}) => {
    const request = {
      rollback_drill_gate: payload.rollbackDrillGate || payload.rollback_drill_gate || {},
    };
    if (!isBackendSource) return mockNaverProductRollbackReadonlyReport(request);
    return adaptProductRollbackReadonlyReportResult(await backendApi.getNaverProductRollbackReadonlyReport(request));
  },
  previewNaverOrderCompleteFields: async (payload = {}) => {
    if (!isBackendSource) return mockNaverOrderCompletePreview(payload);
    const { store } = await resolveBackendStore(payload);
    const windowConfig = getNaverOrderPreviewWindow(payload.previewWindow || payload.windowKey);
    const startDateTime = payload.startDateTime || naverOrderPreviewDateTime(-windowConfig.hours);
    const endDateTime = payload.endDateTime || naverOrderPreviewDateTime(0);
    return withNaverOrderPreviewWindowMetadata(adapters.naverOrderCompletePreview(await backendApi.previewNaverOrders({
      store_id: Number(store.id),
      credential_id: Number(payload.credentialId || payload.credential_id || 7),
      start_datetime: startDateTime,
      end_datetime: endDateTime,
      order_status: 'ALL',
      page: 1,
      size: 1,
      real_preview: true,
      include_detail: true,
      complete_field_preview: true,
      real_sync: false,
    })), windowConfig, startDateTime, endDateTime);
  },
  getCustomerInquiries: async (params) => {
    if (!isBackendSource) return mockApi.getCustomerTickets(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getCustomerInquiries({ storeId: store.id, platform: params?.platform });
    const rows = withStoreName(adapters.list(result, adapters.customerInquiry).data, stores);
    return queryBackendRows(rows, params);
  },
  syncNaverCustomerInquiries: async (payload = {}) => {
    const request = {
      store_id: Number(payload.storeId || payload.store_id),
      start_date: payload.startDate || payload.start_date || undefined,
      end_date: payload.endDate || payload.end_date || undefined,
      answered: payload.answered ?? undefined,
      page: Number(payload.page || 1),
      size: Number(payload.size || 50),
    };
    if (!isBackendSource) {
      return {
        status: 'skipped',
        message: '演示数据源不会调用 Naver 客服消息 API。',
        platformWrite: false,
        createdCount: 0,
        updatedCount: 0,
      };
    }
    const { store } = await resolveBackendStore(payload);
    const result = await backendApi.syncNaverCustomerInquiries({ ...request, store_id: Number(store.id) });
    return {
      status: result.status || 'skipped',
      message: result.message || '',
      errorCode: result.error_code || null,
      createdCount: Number(result.created_count || 0),
      updatedCount: Number(result.updated_count || 0),
      platformWrite: Boolean(result.platform_write),
      rawResponseSaved: Boolean(result.raw_response_saved),
    };
  },
  replyNaverCustomerInquiry: async (payload = {}) => {
    const request = {
      store_id: Number(payload.storeId || payload.store_id),
      inquiry_id: payload.inquiryId || payload.inquiry_id || undefined,
      external_inquiry_id: payload.externalInquiryId || payload.external_inquiry_id || undefined,
      answer_comment: payload.answerComment || payload.answer_comment || '',
      answer_template_id: payload.answerTemplateId || payload.answer_template_id || undefined,
      manual_approval: Boolean(payload.manualApproval || payload.manual_approval),
      final_operator_confirmation: Boolean(payload.finalOperatorConfirmation || payload.final_operator_confirmation),
      actor_context: payload.actorContext || payload.actor_context || { role: 'operator' },
    };
    if (!isBackendSource) {
      return {
        status: 'blocked',
        message: '演示数据源不会提交 Naver 客服回复。',
        platformWrite: false,
      };
    }
    const { store } = await resolveBackendStore(payload);
    const result = await backendApi.replyNaverCustomerInquiry({ ...request, store_id: Number(store.id) });
    return {
      status: result.status || 'blocked',
      message: result.message || '',
      errorCode: result.error_code || null,
      platformWrite: Boolean(result.platform_write),
      platformWriteAttempted: Boolean(result.platform_write_attempted),
      rawResponseSaved: Boolean(result.raw_response_saved),
    };
  },
  syncProductsMock: async (payload) => {
    if (!isBackendSource) return mockSyncResult('products', payload);
    const { store } = await resolveBackendStore(payload);
    return backendApi.syncProductsMock({ storeId: store.id, platform: normalizeSyncPlatform(payload.platform) });
  },
  syncOrdersMock: async (payload) => {
    if (!isBackendSource) return mockSyncResult('orders', payload);
    const { store } = await resolveBackendStore(payload);
    return backendApi.syncOrdersMock({ storeId: store.id, platform: normalizeSyncPlatform(payload.platform) });
  },
  syncCustomerInquiriesMock: async (payload) => {
    if (!isBackendSource) return mockSyncResult('customerInquiries', payload);
    const { store } = await resolveBackendStore(payload);
    return backendApi.syncCustomerInquiriesMock({ storeId: store.id, platform: normalizeSyncPlatform(payload.platform) });
  },
  runManualStoreSync: async (payload = {}) => {
    const platforms = (payload.platforms || (payload.platform ? [payload.platform] : []))
      .map(normalizeSyncPlatform)
      .filter(Boolean);
    const request = {
      store_id: Number(payload.storeId || payload.store_id),
      platforms: platforms.length ? platforms : ['naver', 'coupang'],
      include_products: payload.includeProducts ?? payload.include_products ?? true,
      include_orders: payload.includeOrders ?? payload.include_orders ?? true,
      include_customer_inquiries: payload.includeCustomerInquiries ?? payload.include_customer_inquiries ?? true,
      replace_policy: payload.replacePolicy || payload.replace_policy || 'delete_absent_when_full_snapshot',
    };
    if (!isBackendSource) return adapters.manualBatchSyncResult(mockManualBatchSyncResult(request));
    const { store } = await resolveBackendStore(payload);
    return adapters.manualBatchSyncResult(await backendApi.runManualStoreSync({
      ...request,
      store_id: Number(store.id),
    }));
  },
  manualRefreshNaverOrders: async (payload = {}) => {
    const request = {
      store_id: Number(payload.storeId || payload.store_id),
      max_count: Number(payload.maxCount || payload.max_count || 20),
      hours: Number(payload.hours || 24),
    };
    if (!isBackendSource) return adapters.manualNaverOrderRefreshResult(mockManualNaverOrderRefreshResult(request));
    const { store } = await resolveBackendStore(payload);
    return adapters.manualNaverOrderRefreshResult(await backendApi.manualRefreshNaverOrders({
      ...request,
      store_id: Number(store.id),
    }));
  },
  runManualAllStoresSync: async (payload = {}) => {
    const platforms = (payload.platforms || (payload.platform ? [payload.platform] : []))
      .map(normalizeSyncPlatform)
      .filter(Boolean);
    const request = {
      platforms: platforms.length ? platforms : ['naver', 'coupang'],
      include_products: payload.includeProducts ?? payload.include_products ?? true,
      include_orders: payload.includeOrders ?? payload.include_orders ?? true,
      include_customer_inquiries: payload.includeCustomerInquiries ?? payload.include_customer_inquiries ?? true,
      include_inactive: payload.includeInactive ?? payload.include_inactive ?? false,
      replace_policy: payload.replacePolicy || payload.replace_policy || 'delete_absent_when_full_snapshot',
    };
    if (!isBackendSource) {
      const overview = mockStoreOverview();
      return {
        status: 'skipped',
        requestedPlatforms: request.platforms,
        platformWrite: false,
        storeResults: overview.stores.map((store) => ({
          storeId: store.store_id,
          storeName: store.store_name,
          status: 'skipped',
          message: '演示模式不调用真实平台',
          platformWrite: false,
        })),
        summary: {
          storeCount: overview.stores.length,
          successCount: 0,
          failedCount: 0,
          skippedCount: overview.stores.length,
          createdCount: 0,
          updatedCount: 0,
          deletedCount: 0,
        },
      };
    }
    const result = await backendApi.runManualAllStoresSync(request);
    const summary = result.summary || {};
    return {
      status: result.status || 'skipped',
      requestedPlatforms: result.requested_platforms || [],
      platformWrite: Boolean(result.platform_write),
      storeResults: (result.store_results || []).map((item) => ({
        storeId: item.store_id,
        storeName: item.store_name,
        status: item.status,
        message: item.message || item.summary?.message || '',
        platformWrite: Boolean(item.platform_write),
        summary: item.summary || {},
      })),
      summary: {
        storeCount: Number(summary.store_count || 0),
        successCount: Number(summary.success_count || 0),
        partialSuccessCount: Number(summary.partial_success_count || 0),
        failedCount: Number(summary.failed_count || 0),
        skippedCount: Number(summary.skipped_count || 0),
        createdCount: Number(summary.created_count || 0),
        updatedCount: Number(summary.updated_count || 0),
        deletedCount: Number(summary.deleted_count || 0),
      },
    };
  },
  previewCoupangOrders: async (payload) => {
    if (!isBackendSource) {
      return adapters.coupangOrderSyncResult({
        store_id: payload?.storeId,
        platform: 'coupang',
        source_type: 'mock',
        start_date: payload?.startDate,
        end_date: payload?.endDate,
        max_pages: payload?.maxPages,
        page_count: 0,
        next_cursor_exists: false,
        would_create: 0,
        would_update: 0,
        sample_ids: [],
      });
    }
    const { store } = await resolveBackendStore(payload);
    return adapters.coupangOrderSyncResult(await backendApi.previewCoupangOrders({
      store_id: Number(store.id),
      start_date: payload.startDate,
      end_date: payload.endDate,
      max_pages: Number(payload.maxPages || 1),
    }));
  },
  syncCoupangOrders: async (payload) => {
    if (!isBackendSource) {
      return adapters.coupangOrderSyncResult({
        store_id: payload?.storeId,
        platform: 'coupang',
        source_type: 'mock',
        start_date: payload?.startDate,
        end_date: payload?.endDate,
        max_pages: payload?.maxPages,
        page_count: 0,
        next_cursor_exists: false,
        created_count: 0,
        updated_count: 0,
        skipped_count: 0,
        sample_ids: [],
      });
    }
    const { store } = await resolveBackendStore(payload);
    return adapters.coupangOrderSyncResult(await backendApi.syncCoupangOrders({
      store_id: Number(store.id),
      start_date: payload.startDate,
      end_date: payload.endDate,
      max_pages: Number(payload.maxPages || 1),
    }));
  },
  previewCoupangProducts: async (payload) => {
    if (!isBackendSource) {
      return adapters.coupangProductSyncResult({
        store_id: payload?.storeId,
        platform: 'coupang',
        source_type: 'mock',
        status_filter: payload?.status || 'APPROVED',
        status_semantic_notice: 'APPROVED is a Coupang API product review/listing status and may not exactly match the seller center sales status.',
        max_pages: payload?.maxPages,
        page_count: 0,
        next_cursor_exists: false,
        would_create: 0,
        would_update: 0,
        sample_ids: [],
        per_status: [],
      });
    }
    const { store } = await resolveBackendStore(payload);
    return adapters.coupangProductSyncResult(await backendApi.previewCoupangProducts({
      store_id: Number(store.id),
      status: payload.status || 'APPROVED',
      max_pages: Number(payload.maxPages || 1),
    }));
  },
  syncCoupangProducts: async (payload) => {
    if (!isBackendSource) {
      return adapters.coupangProductSyncResult({
        store_id: payload?.storeId,
        platform: 'coupang',
        source_type: 'mock',
        write_scope: 'local_products_only',
        platform_write: false,
        real_api_write_enabled: false,
        status_filter: payload?.status || 'APPROVED',
        status_semantic_notice: 'APPROVED is a Coupang API product review/listing status and may not exactly match the seller center sales status.',
        max_pages: payload?.maxPages,
        page_count: 0,
        next_cursor_exists: false,
        created_count: 0,
        updated_count: 0,
        skipped_count: 0,
        sample_ids: [],
        per_status: [],
      });
    }
    const { store } = await resolveBackendStore(payload);
    return adapters.coupangProductSyncResult(await backendApi.syncCoupangProducts({
      store_id: Number(store.id),
      status: payload.status || 'APPROVED',
      max_pages: Number(payload.maxPages || 1),
    }));
  },
  previewCoupangSales: async (payload) => {
    if (!isBackendSource) {
      return adapters.coupangFinancialPreviewResult({
        store_id: payload?.storeId,
        platform: 'coupang',
        sync_type: 'sales_coupang_mock_preview',
        source_type: 'mock',
        business_timezone: 'Asia/Seoul',
        start_date: payload?.startDate,
        end_date: payload?.endDate,
        max_pages: payload?.maxPages,
        page_count: 0,
        next_cursor_exists: false,
        total_rows: 0,
        sample_ids: [],
        sample_rows: [],
        summary_totals: {},
        semantic_notice: 'mock mode shows an empty preview state and does not represent real Coupang financial data.',
      });
    }
    const { store } = await resolveBackendStore(payload);
    return adapters.coupangFinancialPreviewResult(await backendApi.previewCoupangSales({
      store_id: Number(store.id),
      start_date: payload.startDate,
      end_date: payload.endDate,
      max_pages: Number(payload.maxPages || 1),
    }));
  },
  previewCoupangSettlements: async (payload) => {
    if (!isBackendSource) {
      return adapters.coupangFinancialPreviewResult({
        store_id: payload?.storeId,
        platform: 'coupang',
        sync_type: 'settlements_coupang_mock_preview',
        source_type: 'mock',
        business_timezone: 'Asia/Seoul',
        start_date: payload?.startDate,
        end_date: payload?.endDate,
        months: [],
        page_count: 0,
        next_cursor_exists: false,
        total_rows: 0,
        sample_ids: [],
        sample_rows: [],
        summary_totals: {},
        per_month: [],
        month_semantic_notice: 'Settlement preview uses revenueRecognitionYearMonth=YYYY-MM; mock mode does not query Coupang.',
        field_mapping_suggestion: {},
      });
    }
    const { store } = await resolveBackendStore(payload);
    return adapters.coupangFinancialPreviewResult(await backendApi.previewCoupangSettlements({
      store_id: Number(store.id),
      start_date: payload.startDate,
      end_date: payload.endDate,
    }));
  },
  getSyncLogs: async (params) => {
    if (!isBackendSource) return mockApi.getOperationLogs(params);
    const result = await backendApi.getSyncLogs(params);
    return queryBackendRows(adapters.list(result, adapters.syncLog).data, params);
  },
  getOperationAuditLogs: async (params = {}) => {
    if (!isBackendSource) return mockApi.getOperationLogs(params);
    const { store } = await resolveBackendStore(params);
    const result = await backendApi.getOperationAuditLogs({
      storeId: store.id,
      limit: 50,
      offset: 0,
      includeAdvanced: true,
      date_from: params.startDate || undefined,
      date_to: params.endDate || undefined,
    });
    const adapted = adapters.operationAuditLogList(result);
    return {
      ...queryBackendRows(adapted.data, params),
      businessMessage: adapted.businessMessage,
      auditStatus: adapted.status,
      auditRuntimeStatus: adapted.runtimeStatus,
      publicEndpointEnabled: adapted.publicEndpointEnabled,
      readonlyLocalRoute: adapted.readonlyLocalRoute,
    };
  },
  getOperationAuditLogSummary: async (params = {}) => {
    if (!isBackendSource) {
      const rows = await mockApi.getOperationLogs({ ...params, page: 1, pageSize: 1000 });
      const attentionCount = (rows.data || []).filter((item) => ['高', '紧急', '高风险', '需复核'].some((flag) => String(item.riskLevel || item.status || '').includes(flag))).length;
      return {
        status: 'mock_operation_summary',
        runtimeStatus: rows.total ? 'available' : 'empty',
        total: rows.total || 0,
        needsAttentionCount: attentionCount,
        backupEvidenceCount: 0,
        restoreEvidenceCount: 0,
        businessMessage: rows.total ? '当前显示演示操作记录。' : '当前没有演示操作记录。',
      };
    }
    const { store } = await resolveBackendStore(params);
    return adapters.operationAuditSummary(await backendApi.getOperationAuditLogSummary({ storeId: store.id }));
  },
  getBackupLocalReport: async (params = {}) => {
    if (!isBackendSource) {
      return adapters.backupLocalReport({
        status: 'mock_backup_report_unavailable',
        business_message: 'mock 模式不读取本地真实备份报告。',
        backup_report_readonly: true,
        public_endpoint_enabled: false,
        backup_count: 0,
        manifest_count: 0,
        items: [],
        summary: {},
        backup_deleted: false,
        real_restore_executed: false,
        production_db_touched: false,
        rows_written: 0,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_sync_open: false,
        platform_writes_enabled: false,
      });
    }
    return adapters.backupLocalReport(await backendApi.getBackupLocalReport({ limit: params.limit || 20 }));
  },
  getBackupLocalReportSummary: async (params = {}) => {
    if (!isBackendSource) {
      return adapters.backupLocalReportSummary({
        status: 'mock_backup_summary_unavailable',
        business_message: 'mock 模式不读取本地真实备份摘要。',
        backup_report_readonly: true,
        public_endpoint_enabled: false,
        backup_count: 0,
        manifest_count: 0,
        reported_item_count: 0,
        valid_manifest_count: 0,
        sensitive_scan_passed_count: 0,
        existing_backup_count: 0,
        needs_attention_count: 0,
        backup_deleted: false,
        real_restore_executed: false,
        production_db_touched: false,
        rows_written: 0,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_sync_open: false,
        platform_writes_enabled: false,
      });
    }
    return adapters.backupLocalReportSummary(await backendApi.getBackupLocalReportSummary({ limit: params.limit || 20 }));
  },
  getOperatorReadiness: async () => {
    const health = isBackendSource
      ? await backendApi.healthCheck()
      : {
        status: 'mock',
        environment: 'mock',
        api_version: 'local',
        real_api_write_enabled: false,
        controlled_platform_writes_enabled: true,
        generic_platform_write_closed: true,
        platform_write_mode: 'controlled_naver_official_writes',
        platform_write_closed: true,
      };
    const overview = isBackendSource
      ? adapters.storeOverview(await backendApi.getStoreOverview({ include_inactive: false }))
      : adapters.storeOverview(mockStoreOverview());
    const backup = isBackendSource
      ? adapters.backupLocalReportSummary(await backendApi.getBackupLocalReportSummary({ limit: 5 }))
      : adapters.backupLocalReportSummary({
        status: 'mock_backup_summary_unavailable',
        business_message: 'mock 模式不读取本地真实备份摘要。',
        backup_report_readonly: true,
        backup_count: 0,
        manifest_count: 0,
        existing_backup_count: 0,
        needs_attention_count: 0,
        backup_deleted: false,
        real_restore_executed: false,
        production_db_touched: false,
        raw_response_saved: false,
        secrets_saved: false,
        privacy_fields_redacted: true,
        formal_sync_open: false,
        platform_writes_enabled: false,
      });
    const overviewSummary = overview.summary || {};
    const unknownStoreCount = Math.max(
      Number(overviewSummary.ordersUnknownStoreCount || 0),
      Number(overviewSummary.inventoryUnknownStoreCount || 0),
    );
    const genericPlatformWriteClosed = Boolean(
      health.platform_write_closed ?? health.platformWriteClosed ?? health.real_api_write_enabled === false,
    );
    const controlledPlatformWritesEnabled = Boolean(
      health.controlled_platform_writes_enabled ?? health.controlledPlatformWritesEnabled ?? true,
    );
    const controlledPlatformWriteReady = controlledPlatformWritesEnabled && genericPlatformWriteClosed;
    const checks = [
      {
        key: 'backend',
        label: '后端服务',
        status: health.status === 'ok' || health.status === 'mock' ? '通过' : '需要检查',
        detail: isBackendSource ? `API ${health.api_version || 'v1'} / ${health.environment || 'local'}` : '当前为 mock 数据源。',
        tone: health.status === 'ok' || health.status === 'mock' ? 'success' : 'danger',
      },
      {
        key: 'controlled_platform_write',
        label: '受控平台写入',
        status: controlledPlatformWriteReady ? 'Naver 受控开放' : '需要检查',
        detail: controlledPlatformWriteReady
          ? '仅 Naver 发货回填和人工客服回复开放；通用平台写入、改价、改库存、自动回复和 Coupang 写入仍关闭。'
          : '通用平台写入开关或受控写入边界异常，请确认只保留 Naver 官方写入入口。',
        tone: controlledPlatformWriteReady ? 'success' : 'danger',
      },
      {
        key: 'store_overview',
        label: '全店铺总览',
        status: overview.stores.length ? '可查看' : '需要检查',
        detail: `${overview.stores.length} 个店铺；${unknownStoreCount} 个店铺存在无法确认指标。`,
        tone: overview.stores.length ? (unknownStoreCount ? 'warning' : 'success') : 'danger',
      },
      {
        key: 'ip_whitelist',
        label: 'IP 白名单',
        status: overviewSummary.ipBlockedStoreCount ? '需要处理' : '未发现阻断',
        detail: overviewSummary.ipBlockedStoreCount ? `${overviewSummary.ipBlockedStoreCount} 个店铺显示 IP 白名单未通过。` : '当前总览未发现 IP 白名单阻断。',
        tone: overviewSummary.ipBlockedStoreCount ? 'warning' : 'success',
      },
      {
        key: 'backup',
        label: '备份状态',
        status: backup.existingBackupCount ? '已有备份' : '建议先备份',
        detail: backup.existingBackupCount ? `可用备份 ${backup.existingBackupCount} 个，需复核 ${backup.needsAttentionCount} 个。` : '交给运营前建议运行 scripts/operator-db-backup.ps1。',
        tone: backup.existingBackupCount ? (backup.needsAttentionCount ? 'warning' : 'success') : 'warning',
      },
    ];
    return {
      status: 'operator_readiness',
      dataSource: DATA_SOURCE,
      backendOnline: health.status === 'ok' || health.status === 'mock',
      platformWriteClosed: genericPlatformWriteClosed,
      genericPlatformWriteClosed,
      controlledPlatformWritesEnabled,
      controlledPlatformWriteReady,
      platformWriteMode: health.platform_write_mode || health.platformWriteMode || 'controlled_naver_official_writes',
      unknownStoreCount,
      ipBlockedStoreCount: Number(overviewSummary.ipBlockedStoreCount || 0),
      storeCount: overview.stores.length,
      backup,
      overview,
      checks,
    };
  },
  getDeviceEnvironments: async (params) => {
    if (!isBackendSource) return mockApi.getEnvironments(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getDeviceEnvironments({ ...params, storeId: store.id });
    const rows = withStoreName(adapters.list(result, adapters.deviceEnvironment).data, stores);
    return queryBackendRows(rows, params);
  },
  createDeviceEnvironment: async (payload) => {
    if (!isBackendSource) return mockApi.createEnvironment(payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.createDeviceEnvironment(adapters.toBackendDeviceEnvironmentPayload(payload, store.id));
    return withStoreName([adapters.deviceEnvironment(result)], stores)[0];
  },
  updateDeviceEnvironment: async (environmentId, payload) => {
    if (!isBackendSource) return mockApi.updateEnvironment(environmentId, payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.updateDeviceEnvironment(environmentId, adapters.toBackendDeviceEnvironmentPayload(payload, store.id));
    return withStoreName([adapters.deviceEnvironment(result)], stores)[0];
  },
  getEmailAccounts: async (params) => {
    if (!isBackendSource) return mockApi.getEmails(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getEmailAccounts({ ...params, storeId: store.id });
    const rows = withStoreName(adapters.list(result, adapters.emailAccount).data, stores);
    return queryBackendRows(rows, params);
  },
  createEmailAccount: async (payload) => {
    if (!isBackendSource) return mockApi.createEmail(payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.createEmailAccount(adapters.toBackendEmailAccountPayload(payload, store.id));
    return withStoreName([adapters.emailAccount(result)], stores)[0];
  },
  updateEmailAccount: async (emailAccountId, payload) => {
    if (!isBackendSource) return mockApi.updateEmail(emailAccountId, payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.updateEmailAccount(emailAccountId, adapters.toBackendEmailAccountPayload(payload, store.id));
    return withStoreName([adapters.emailAccount(result)], stores)[0];
  },
  getImportantEmails: async (params) => {
    if (!isBackendSource) return mockApi.getRecentEmails(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getImportantEmails({ ...params, storeId: store.id });
    const rows = withStoreName(adapters.list(result, adapters.importantEmail).data, stores);
    return queryBackendRows(rows, params);
  },
  getAppealCases: async (params) => {
    if (!isBackendSource) return mockApi.getAppeals(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getAppealCases({ ...params, storeId: store.id });
    const rows = withStoreName(adapters.list(result, adapters.appealCase).data, stores);
    return queryBackendRows(rows, params);
  },
  getCredentials: async (params) => {
    if (!isBackendSource) return mockApi.getAccounts(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getCredentials({ ...params, storeId: store.id });
    const rows = withStoreName(adapters.list(result, adapters.credential).data, stores);
    return queryBackendRows(rows, params);
  },
  createCredential: async (payload) => {
    if (!isBackendSource) return mockApi.createAccount(payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.createCredential(adapters.toBackendCredentialPayload(payload, store.id));
    return withStoreName([adapters.credential(result)], stores)[0];
  },
  updateCredential: async (credentialId, payload) => {
    if (!isBackendSource) return mockApi.updateAccount(credentialId, payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.updateCredential(credentialId, adapters.toBackendCredentialPayload(payload, store.id));
    return withStoreName([adapters.credential(result)], stores)[0];
  },
  disableCredential: async (credentialId, payload = {}) => {
    if (!isBackendSource) return mockApi.updateAccountStatus(credentialId, 'inactive');
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.updateCredential(credentialId, adapters.toBackendCredentialPayload({ ...payload, status: 'inactive' }, store.id));
    return withStoreName([adapters.credential(result)], stores)[0];
  },
  getPlatformLogins: async (params) => {
    if (!isBackendSource) return mockApi.getAccounts(params);
    const { store, stores } = await resolveBackendStore(params);
    const result = await backendApi.getPlatformLogins({ ...params, storeId: store.id });
    const rows = withStoreName(adapters.list(result, adapters.platformLogin).data, stores);
    return queryBackendRows(rows, params);
  },
  createPlatformLogin: async (payload) => {
    if (!isBackendSource) return mockApi.createAccount(payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.createPlatformLogin(adapters.toBackendPlatformLoginPayload(payload, store.id));
    return withStoreName([adapters.platformLogin(result)], stores)[0];
  },
  updatePlatformLogin: async (loginId, payload) => {
    if (!isBackendSource) return mockApi.updateAccount(loginId, payload);
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.updatePlatformLogin(loginId, adapters.toBackendPlatformLoginPayload(payload, store.id));
    return withStoreName([adapters.platformLogin(result)], stores)[0];
  },
  deactivatePlatformLogin: async (loginId, payload = {}) => {
    if (!isBackendSource) return mockApi.updateAccountStatus(loginId, 'inactive');
    const { store, stores } = await resolveBackendStore(payload);
    const result = await backendApi.updatePlatformLogin(loginId, adapters.toBackendPlatformLoginPayload({ ...payload, loginStatus: 'inactive' }, store.id));
    return withStoreName([adapters.platformLogin(result)], stores)[0];
  },
  getApiCredentialReadiness: async (params) => {
    if (!isBackendSource) return adapters.apiCredentialReadiness(mockApiCredentialReadiness(params));
    return adapters.apiCredentialReadiness(await backendApi.getApiCredentialReadiness(params));
  },
  runApiCredentialSmokeTest: async () => {
    if (!isBackendSource) return adapters.apiCredentialSmokeTest();
    return adapters.apiCredentialSmokeTest(await backendApi.runApiCredentialSmokeTest({ platform: 'all', mode: 'readonly' }));
  },
  getApiCapabilities: async (params) => {
    if (!isBackendSource) return queryBackendRows(mockApiCapabilities, params);
    const result = await backendApi.getApiCapabilities(params);
    return queryBackendRows(adapters.list(result, adapters.apiCapability).data, params);
  },
  createApiCapability: async (payload) => {
    if (!isBackendSource) throw new Error('mock 模式不维护后端 API 能力矩阵，请切换 backend 模式查看/写入 Codex1 记录。');
    return adapters.apiCapability(await backendApi.createApiCapability(adapters.toBackendApiCapabilityPayload(payload)));
  },
  updateApiCapability: async (capabilityId, payload) => {
    if (!isBackendSource) throw new Error('mock 模式不维护后端 API 能力矩阵，请切换 backend 模式查看/写入 Codex1 记录。');
    return adapters.apiCapability(await backendApi.updateApiCapability(capabilityId, adapters.toBackendApiCapabilityPayload(payload)));
  },
  getApiCapabilityResults: async (params) => {
    if (!isBackendSource) return queryBackendRows(mockApiCapabilityResults(params?.storeId || params?.store_id), params);
    const result = await backendApi.getApiCapabilityResults(params);
    return queryBackendRows(adapters.list(result, adapters.apiCapabilityResult).data, params);
  },
  createApiCapabilityResult: async (payload) => {
    if (!isBackendSource) throw new Error('mock 模式不维护后端 API 能力矩阵，请切换 backend 模式查看/写入 Codex1 记录。');
    const { store } = await resolveBackendStore(payload);
    return adapters.apiCapabilityResult(await backendApi.createApiCapabilityResult(adapters.toBackendApiCapabilityResultPayload(payload, store.id)));
  },
  getApiCapabilityResult: async (resultId) => {
    if (!isBackendSource) throw new Error('mock 模式不维护后端 API 能力矩阵，请切换 backend 模式查看/写入 Codex1 记录。');
    return adapters.apiCapabilityResult(await backendApi.getApiCapabilityResult(resultId));
  },
  getAiDailyContext: async (params) => {
    if (!isBackendSource) return null;
    return adapters.aiDailyContext(await backendApi.getAiDailyContext(params));
  },
};

export const dataProvider = new Proxy(sourceMethods, {
  get(target, property) {
    if (property in target) return target[property];
    return mockApi[property];
  },
});

export { DATA_SOURCE, isBackendSource };
export default dataProvider;
