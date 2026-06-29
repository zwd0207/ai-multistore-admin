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

async function resolveBackendStore(params = {}) {
  const stores = await getBackendStores();
  const requestedId = params.storeId ?? params.store_id;
  const store = requestedId
    ? stores.find((item) => String(item.id) === String(requestedId))
    : stores[0];
  if (!store) throw new Error('Codex1 后端暂无可用店铺，请先创建或导入店铺数据');
  return { store, stores };
}

function withStoreName(items, stores) {
  const names = new Map(stores.map((store) => [String(store.id), store.name]));
  return items.map((item) => ({ ...item, store: names.get(String(item.storeId)) || item.store }));
}

async function getMockDashboardData() {
  const [summary, risks, todos, activities] = await Promise.all([
    mockApi.getDashboardSummary(),
    mockApi.getDashboardRisks(),
    mockApi.getDashboardTodos(),
    mockApi.getDashboardActivities(),
  ]);
  return { summary, risks, todos, activities };
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
    if (!isBackendSource) return mockApi.getDashboardSummary(params);
    return adapters.dashboardSummary(await backendApi.getDashboardSummary(params)).summary;
  },
  getDashboardSalesTrend: mockApi.getDashboardSalesTrend,
  getStores: async (params) => {
    if (!isBackendSource) return mockApi.getStores(params);
    return queryBackendRows(await getBackendStores(), params);
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
  getSyncLogs: async (params) => {
    if (!isBackendSource) return mockApi.getOperationLogs(params);
    const result = await backendApi.getSyncLogs(params);
    return queryBackendRows(adapters.list(result, adapters.syncLog).data, params);
  },
  getDeviceEnvironments: async (params) => {
    if (!isBackendSource) return mockApi.getEnvironments(params);
    return adapters.list(await backendApi.getDeviceEnvironments(params), adapters.deviceEnvironment);
  },
  getEmailAccounts: async (params) => {
    if (!isBackendSource) return mockApi.getEmails(params);
    return adapters.list(await backendApi.getEmailAccounts(params), adapters.emailAccount);
  },
  getImportantEmails: async (params) => {
    if (!isBackendSource) return mockApi.getRecentEmails(params);
    return adapters.list(await backendApi.getImportantEmails(params), adapters.importantEmail);
  },
  getAppealCases: async (params) => {
    if (!isBackendSource) return mockApi.getAppeals(params);
    return adapters.list(await backendApi.getAppealCases(params), adapters.appealCase);
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
