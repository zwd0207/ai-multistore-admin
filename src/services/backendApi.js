import http, { sanitizeForError } from './http';

const PARAMETER_ALIASES = {
  pageSize: 'page_size',
  storeId: 'store_id',
  startDate: 'start_date',
  endDate: 'end_date',
  includeAdvanced: 'include_advanced',
  includeRows: 'include_rows',
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
  getStoreOverview: (params) => getData('/dashboard/store-overview', params),
  getAiDailyContext: (params) => getData('/ai/daily-context', params),
  getProducts: (params) => getData('/products', params),
  getOrders: (params) => getData('/orders', params),
  getOrderLogisticsTrace: (orderId, params) => getData(`/orders/${orderId}/logistics-trace`, params),
  getShippingLogisticsMappings: (params) => getData('/shipping/logistics-mappings', params),
  getWarehouseShippingBatches: (params) => getData('/shipping/warehouse-batches', params),
  createWarehouseShippingBatch: (payload) => sendData('post', '/shipping/warehouse-batches', payload),
  requestWarehouseShippingApproval: (batchId, scope, payload) => sendData('post', `/shipping/warehouse-batches/${batchId}/approval/${scope}`, payload),
  downloadWarehouseShippingManifest: (batchId, payload) => sendData('post', `/shipping/warehouse-batches/${batchId}/manifest`, payload),
  importWarehouseShippingTracking: (batchId, payload) => sendData('post', `/shipping/warehouse-batches/${batchId}/tracking-import`, payload),
  confirmWarehouseShippingBatch: (batchId, payload) => sendData('post', `/shipping/warehouse-batches/${batchId}/confirm`, payload),
  removeWarehouseShippingRow: (batchId, rowId, payload) => sendData('post', `/shipping/warehouse-batches/${batchId}/rows/${rowId}/remove`, payload),
  confirmWarehouseShippingWriteback: (batchId, payload) => sendData('post', `/shipping/warehouse-batches/${batchId}/writeback`, payload),
  checkShippingLogisticsMappingWriteGate: (payload) => sendData('post', '/shipping/logistics-mappings/write-gate', payload),
  writeShippingLogisticsMappings: (payload) => sendData('post', '/shipping/logistics-mappings', payload),
  generateShippingExcelExport: (payload) => sendData('post', '/shipping/export-excel', payload),
  getShippingExportHistory: (params) => getData('/shipping/export-history', params),
  checkShippingTrackingImportMockParse: (payload) => sendData('post', '/shipping/tracking-import/mock-parse', payload),
  checkShippingTrackingImportXlsxParserMock: (payload) => sendData('post', '/shipping/tracking-import/parse-xlsx-mock', payload),
  checkShippingTrackingImportWriteGate: (payload) => sendData('post', '/shipping/tracking-import/write-gate', payload),
  writeShippingTrackingImport: (payload) => sendData('post', '/shipping/tracking-import', payload),
  getShippingTrackingImportHistory: (params) => getData('/shipping/tracking-import-history', params),
  checkShippingTrackingOrderMatchReadonly: (payload) => sendData('post', '/shipping/tracking-order-match/readonly-check', payload),
  checkShippingTrackingOrderStatusLocalUpdateGate: (payload) => (
    sendData('post', '/shipping/tracking-order-status/local-update-gate', payload)
  ),
  writeShippingTrackingOrderStatusLocalUpdate: (payload) => (
    sendData('post', '/shipping/tracking-order-status/local-update', payload)
  ),
  checkShippingShipmentWritebackBoundary: (payload) => sendData('post', '/shipping/shipment-writeback/approval-boundary', payload),
  checkShippingShipmentWritebackDryRunGate: (payload) => sendData('post', '/shipping/shipment-writeback/dry-run-gate', payload),
  checkShippingShipmentWritebackExecutionMockGate: (payload) => (
    sendData('post', '/shipping/shipment-writeback/execution-mock-gate', payload)
  ),
  executeShippingShipmentWriteback: (payload) => sendData('post', '/shipping/shipment-writeback/execute', payload),
  getCustomerInquiries: (params) => getData('/customer-inquiries', params),
  getSyncLogs: (params) => getData('/sync-logs', params),
  getOperationAuditLogs: (params) => getData('/operation-audit-logs', params),
  getOperationAuditLogSummary: (params) => getData('/operation-audit-logs/summary', params),
  getBackupLocalReport: (params) => getData('/backups/local-report', params),
  getBackupLocalReportSummary: (params) => getData('/backups/local-report/summary', params),
  normalizeBatchReadonlyEvidence: (payload) => sendData('post', '/batch/readonly-evidence', payload),
  checkBatchApprovalAuditEvidence: (payload) => sendData('post', '/batch/approval-audit-evidence', payload),
  checkBatchApprovalDecisionReadonly: (payload) => sendData('post', '/batch/approval-decision/readonly-check', payload),
  checkBatchApprovalDecisionAuditLinkageReadonly: (payload) => (
    sendData('post', '/batch/approval-decision/audit-linkage/readonly-check', payload)
  ),
  checkFormalBatchExecutionPreflightReadonly: (payload) => (
    sendData('post', '/batch/execution-preflight/readonly-check', payload)
  ),
  checkFormalBatchExecutionDryRunReadonly: (payload) => (
    sendData('post', '/batch/execution-dry-run/readonly-check', payload)
  ),
  checkFormalBatchExecutionApprovalReadonly: (payload) => (
    sendData('post', '/batch/execution-approval/readonly-check', payload)
  ),
  checkFormalBatchExecutionWriteBoundaryReadonly: (payload) => (
    sendData('post', '/batch/execution-write-boundary/readonly-check', payload)
  ),
  checkFormalBatchPreExecutionRefreshReadonly: (payload) => (
    sendData('post', '/batch/pre-execution-refresh/readonly-check', payload)
  ),
  checkNaverProductBatchExecutionApprovalReadonly: (payload) => (
    sendData('post', '/batch/naver/products/execution-approval/readonly-check', payload)
  ),
  checkNaverOrderBatchExecutionApprovalReadonly: (payload) => (
    sendData('post', '/batch/naver/orders/execution-approval/readonly-check', payload)
  ),
  getNaverProductRollbackReadonlyReport: (payload) => sendData('post', '/batch/naver/products/rollback-readonly-report', payload),
  getRolePermissionInventory: () => getData('/permissions/role-inventory'),
  checkPermissionMock: (payload) => sendData('post', '/permissions/mock-check', payload),
  checkSensitiveActionPermissionMock: (payload) => sendData('post', '/permissions/sensitive-action/mock-check', payload),
  checkStoreMembershipReadonly: (payload) => sendData('post', '/permissions/store-membership/readonly-check', payload),
  checkUserInvitationReadonly: (payload) => sendData('post', '/permissions/user-invitation/readonly-check', payload),
  checkUserInvitationApprovalChecklistReadonly: (payload) => sendData('post', '/permissions/user-invitation/approval-checklist/readonly-check', payload),
  checkUserInvitationApprovalAuditLinkageReadonly: (payload) => (
    sendData('post', '/permissions/user-invitation/approval-audit-linkage/readonly-check', payload)
  ),
  syncProductsMock: (params) => sendData('post', '/sync/products/mock', undefined, params),
  syncOrdersMock: (params) => sendData('post', '/sync/orders/mock', undefined, params),
  syncCustomerInquiriesMock: (params) => sendData('post', '/sync/customer-inquiries/mock', undefined, params),
  syncNaverCustomerInquiries: (payload) => sendData('post', '/sync/customer-inquiries/naver', payload),
  replyNaverCustomerInquiry: (payload) => sendData('post', '/sync/customer-inquiries/naver/reply', payload),
  runManualStoreSync: (payload) => sendData('post', '/sync/manual-batch', payload),
  runManualAllStoresSync: (payload) => sendData('post', '/sync/manual-batch/all', payload),
  previewCoupangOrders: (payload) => sendData('post', '/sync/orders/coupang/preview', payload),
  syncCoupangOrders: (payload) => sendData('post', '/sync/orders/coupang', payload),
  previewNaverOrders: (payload) => sendData('post', '/sync/orders/naver/preview', payload),
  manualRefreshNaverOrders: (payload) => sendData('post', '/sync/orders/naver/manual-refresh', payload),
  refreshSingleNaverOrderDetail: (payload) => sendData('post', '/sync/orders/naver/refresh-one', payload),
  previewCoupangProducts: (payload) => sendData('post', '/sync/products/coupang/preview', payload),
  syncCoupangProducts: (payload) => sendData('post', '/sync/products/coupang', payload),
  previewCoupangSales: (payload) => sendData('post', '/sync/sales/coupang/preview', payload),
  previewCoupangSettlements: (payload) => sendData('post', '/sync/settlements/coupang/preview', payload),
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
  getPlatformLogins: (params) => getData('/platform-logins', params),
  createPlatformLogin: (payload) => sendData('post', '/platform-logins', payload),
  updatePlatformLogin: (loginId, payload) => sendData('put', `/platform-logins/${loginId}`, payload),
  getApiCredentialReadiness: (params) => getData('/api-credentials/readiness', params),
  runApiCredentialSmokeTest: (payload) => sendData('post', '/api-credentials/smoke-test', payload),
  getApiCapabilities: (params) => getData('/api-capabilities', params),
  createApiCapability: (payload) => sendData('post', '/api-capabilities', payload),
  updateApiCapability: (capabilityId, payload) => sendData('put', `/api-capabilities/${capabilityId}`, payload),
  getApiCapabilityResults: (params) => getData('/api-capability-results', params),
  createApiCapabilityResult: (payload) => sendData('post', '/api-capability-results', payload),
  getApiCapabilityResult: (resultId) => getData(`/api-capability-results/${resultId}`),
};

export { getData, normalizeParams, sendData };
export default backendApi;
