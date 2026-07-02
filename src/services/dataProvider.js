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
  if (platform) filtered = filtered.filter((item) => comparable(item.platform) === comparable(platform));
  if (params.priority) filtered = filtered.filter((item) => comparable(item.priority) === comparable(params.priority));

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

const sourceMethods = {
  healthCheck: backendApi.healthCheck,
  getDashboardData: (params) => (isBackendSource ? getBackendDashboardData(params) : getMockDashboardData()),
  getDashboardSummary: async (params) => {
    if (!isBackendSource) return withMockFinancialSummary(await mockApi.getDashboardSummary(params));
    return adapters.dashboardSummary(await backendApi.getDashboardSummary(params)).summary;
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
