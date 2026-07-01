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
  if (status) filtered = filtered.filter((item) => comparable(item.status) === comparable(status));
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
    const rows = withStoreName(adapters.list(result, adapters.order).data, stores);
    return queryBackendRows(rows, params);
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
  getApiCredentialReadiness: async () => {
    if (!isBackendSource) return adapters.apiCredentialReadiness();
    return adapters.apiCredentialReadiness(await backendApi.getApiCredentialReadiness());
  },
  runApiCredentialSmokeTest: async () => {
    if (!isBackendSource) return adapters.apiCredentialSmokeTest();
    return adapters.apiCredentialSmokeTest(await backendApi.runApiCredentialSmokeTest({ platform: 'all', mode: 'readonly' }));
  },
  getApiCapabilities: async (params) => {
    if (!isBackendSource) return { data: [], items: [], total: 0, page: params?.page ?? 1, pageSize: params?.pageSize ?? 10 };
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
    if (!isBackendSource) return { data: [], items: [], total: 0, page: params?.page ?? 1, pageSize: params?.pageSize ?? 10 };
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
