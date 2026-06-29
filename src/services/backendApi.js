import http, { sanitizeForError } from './http';

const PARAMETER_ALIASES = {
  pageSize: 'page_size',
  storeId: 'store_id',
  startDate: 'start_date',
  endDate: 'end_date',
};

function normalizeParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).map(([key, value]) => [PARAMETER_ALIASES[key] || key, value]),
  );
}

async function getData(path, params) {
  const response = await http.get(path, { params: normalizeParams(params) });

  if (!response || response.success !== true) {
    const error = new Error(response?.message || 'Codex1 后端返回了无效响应');
    error.name = 'BackendApiError';
    error.status = 200;
    error.errorCode = response?.error_code || 'INVALID_BACKEND_RESPONSE';
    error.detail = sanitizeForError(response?.detail || null);
    throw error;
  }

  return response.data;
}

export const backendApi = {
  healthCheck: () => getData('/health'),
  getStores: (params) => getData('/stores', params),
  getDashboardSummary: (params) => getData('/dashboard/summary', params),
  getAiDailyContext: (params) => getData('/ai/daily-context', params),
  getProducts: (params) => getData('/products', params),
  getOrders: (params) => getData('/orders', params),
  getCustomerInquiries: (params) => getData('/customer-inquiries', params),
  getSyncLogs: (params) => getData('/sync-logs', params),
  getDeviceEnvironments: (params) => getData('/device-environments', params),
  getEmailAccounts: (params) => getData('/email-accounts', params),
  getImportantEmails: (params) => getData('/important-emails', params),
  getAppealCases: (params) => getData('/appeal-cases', params),
  getCredentials: (params) => getData('/credentials', params),
};

export { getData, normalizeParams };
export default backendApi;
