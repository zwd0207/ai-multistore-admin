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

async function sendData(method, path, body, params) {
  const response = await http[method](path, body, { params: normalizeParams(params) });

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
  createStore: (payload) => sendData('post', '/stores', payload),
  updateStore: (storeId, payload) => sendData('put', `/stores/${storeId}`, payload),
  getDashboardSummary: (params) => getData('/dashboard/summary', params),
  getAiDailyContext: (params) => getData('/ai/daily-context', params),
  getProducts: (params) => getData('/products', params),
  getOrders: (params) => getData('/orders', params),
  getCustomerInquiries: (params) => getData('/customer-inquiries', params),
  getSyncLogs: (params) => getData('/sync-logs', params),
  syncProductsMock: (params) => sendData('post', '/sync/products/mock', undefined, params),
  syncOrdersMock: (params) => sendData('post', '/sync/orders/mock', undefined, params),
  syncCustomerInquiriesMock: (params) => sendData('post', '/sync/customer-inquiries/mock', undefined, params),
  getDeviceEnvironments: (params) => getData('/device-environments', params),
  createDeviceEnvironment: (payload) => sendData('post', '/device-environments', payload),
  updateDeviceEnvironment: (environmentId, payload) => sendData('put', `/device-environments/${environmentId}`, payload),
  getEmailAccounts: (params) => getData('/email-accounts', params),
  createEmailAccount: (payload) => sendData('post', '/email-accounts', payload),
  updateEmailAccount: (emailAccountId, payload) => sendData('put', `/email-accounts/${emailAccountId}`, payload),
  getImportantEmails: (params) => getData('/important-emails', params),
  getAppealCases: (params) => getData('/appeal-cases', params),
  getCredentials: (params) => getData('/credentials', params),
  createCredential: (payload) => sendData('post', '/credentials', payload),
  updateCredential: (credentialId, payload) => sendData('put', `/credentials/${credentialId}`, payload),
};

export { getData, normalizeParams, sendData };
export default backendApi;
