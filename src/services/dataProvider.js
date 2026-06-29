import adapters from './adapters';
import backendApi from './backendApi';
import mockApi from './mockApi';

const requestedSource = String(import.meta.env?.VITE_DATA_SOURCE || 'mock').toLowerCase();
const DATA_SOURCE = requestedSource === 'backend' ? 'backend' : 'mock';
const isBackendSource = DATA_SOURCE === 'backend';

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
    return adapters.list(await backendApi.getStores(params), adapters.store);
  },
  getProducts: async (params) => {
    if (!isBackendSource) return mockApi.getProducts(params);
    return adapters.list(await backendApi.getProducts(params), adapters.product);
  },
  getOrders: async (params) => {
    if (!isBackendSource) return mockApi.getOrders(params);
    return adapters.list(await backendApi.getOrders(params), adapters.order);
  },
  getCustomerInquiries: async (params) => {
    if (!isBackendSource) return mockApi.getCustomerTickets(params);
    return adapters.list(await backendApi.getCustomerInquiries(params), adapters.customerInquiry);
  },
  getSyncLogs: async (params) => {
    if (!isBackendSource) return mockApi.getOperationLogs(params);
    return adapters.list(await backendApi.getSyncLogs(params), adapters.syncLog);
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
  getAiDailyContext: async (params) => adapters.aiDailyContext(await backendApi.getAiDailyContext(params)),
};

export const dataProvider = new Proxy(sourceMethods, {
  get(target, property) {
    if (property in target) return target[property];
    return mockApi[property];
  },
});

export { DATA_SOURCE, isBackendSource };
export default dataProvider;
