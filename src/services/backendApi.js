import http, { sanitizeForError } from './http';

const SAFE_ERROR_MESSAGES = Object.freeze({
  invalid_credentials: '账号或密码不正确，请重新输入。',
  invalid_mfa_code: '验证码或恢复码不正确，请重新输入。',
  mfa_invalid: '验证码或恢复码不正确，请重新输入。',
  session_expired: '登录已过期，请重新登录。',
  reauthentication_required: '请重新验证身份后再继续。',
  mfa_required: '请先完成身份验证。',
  session_required: '登录状态已失效，请重新登录。',
  permission_forbidden: '当前账号没有执行此操作的权限。',
  store_scope_forbidden: '当前账号没有访问该店铺的权限。',
  tenant_scope_forbidden: '当前管理租户不可用，请重新选择。',
  csrf_validation_failed: '页面验证已失效，请刷新后重试。',
  account_already_exists: '该邮箱已经注册。',
  invitation_expired: '邀请已过期，请联系管理员重新发送。',
  invitation_invalid: '邀请链接无效或已被使用，请联系管理员重新发送。',
  platform_admin_already_exists: '平台管理员账号已经存在。',
  platform_admin_invitation_exists: '平台管理员邀请正在处理中。',
  password_policy_failed: '密码至少 12 个字符，并需包含大小写字母和数字。',
  mfa_enrollment_invalid: '身份验证器绑定已失效，请联系管理员重新发送邀请。',
  mfa_enrollment_expired: '身份验证器绑定已超时，请联系管理员重新发送邀请。',
  password_reset_invalid: '重置链接无效或已过期，请重新申请。',
  request_timeout: '系统响应较慢，请稍后重试。',
  network_error: '暂时无法连接系统服务，请稍后重试。',
  rate_limited: '请求过于频繁，请稍后重试。',
  too_many_requests: '请求过于频繁，请稍后重试。',
  validation_error: '提交内容不符合要求，请检查后再试。',
});

const PARAMETER_ALIASES = {
  pageSize: 'page_size',
  storeId: 'store_id',
  startDate: 'start_date',
  endDate: 'end_date',
  includeAdvanced: 'include_advanced',
  includeRows: 'include_rows',
  includeArchived: 'include_archived',
  startAt: 'start_at',
  endAt: 'end_at',
  orderId: 'order_id',
  productOrderId: 'product_order_id',
  productId: 'product_id',
  productName: 'product_name',
  buyerName: 'buyer_name',
  buyerPhone: 'buyer_phone',
};

function normalizeParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).map(([key, value]) => [PARAMETER_ALIASES[key] || key, value]),
  );
}

function normalizeErrorCode(error) {
  return String(error?.errorCode || error?.code || '').trim().toLowerCase();
}

function safeErrorMessage(error, fallback = '请求暂时无法完成，请稍后重试。') {
  const errorCode = normalizeErrorCode(error);
  if (SAFE_ERROR_MESSAGES[errorCode]) return SAFE_ERROR_MESSAGES[errorCode];
  if (error?.status === 401) return '登录状态已失效，请重新登录。';
  if (error?.status === 403) return '当前账号没有执行此操作的权限。';
  if (error?.status === 429) return '请求过于频繁，请稍后重试。';
  if (error?.status >= 500) return '系统服务暂时不可用，请稍后重试。';
  return fallback;
}

function toSafeError(error, fallback) {
  const safe = new Error(safeErrorMessage(error, fallback));
  safe.name = error?.name || 'BackendApiError';
  safe.status = Number.isFinite(Number(error?.status)) ? Number(error.status) : 0;
  safe.errorCode = String(error?.errorCode || 'REQUEST_FAILED');
  safe.detail = null;
  safe.data = null;
  return safe;
}

async function safeGetData(path, params, fallback) {
  try {
    return await getData(path, params);
  } catch (error) {
    throw toSafeError(error, fallback);
  }
}

async function safeSendData(method, path, body, params, fallback) {
  try {
    return await sendData(method, path, body, params);
  } catch (error) {
    throw toSafeError(error, fallback);
  }
}

async function getData(path, params) {
  try {
    const response = await http.get(path, { params: normalizeParams(params) });

    if (!response || response.success !== true) {
      const error = new Error('backend response rejected');
      error.name = 'BackendApiError';
      error.status = 200;
      error.errorCode = response?.error_code || 'INVALID_BACKEND_RESPONSE';
      error.detail = sanitizeForError(response?.detail || null);
      throw error;
    }

    return response.data;
  } catch (error) {
    throw toSafeError(error, '请求暂时无法完成，请稍后重试。');
  }
}

async function sendData(method, path, body, params) {
  try {
    const response = await http[method](path, body, { params: normalizeParams(params) });

    if (!response || response.success !== true) {
      const error = new Error('backend response rejected');
      error.name = 'BackendApiError';
      error.status = 200;
      error.errorCode = response?.error_code || 'INVALID_BACKEND_RESPONSE';
      error.detail = sanitizeForError(response?.detail || null);
      throw error;
    }

    return response.data;
  } catch (error) {
    throw toSafeError(error, '请求暂时无法完成，请稍后重试。');
  }
}

export const backendApi = {
  login: (payload) => safeSendData('post', '/auth/login', payload, undefined, '暂时无法登录，请稍后重试。'),
  verifyMfa: (payload) => safeSendData('post', '/auth/mfa/verify', payload, undefined, '暂时无法确认验证码，请稍后重试。'),
  getLocalMfaCode: () => getData('/auth/local-mfa-code'),
  getSession: () => safeGetData('/auth/session', undefined, '登录状态暂时无法确认，请稍后重试。'),
  logout: () => safeSendData('post', '/auth/logout', undefined, undefined, '退出登录暂时未完成，请稍后重试。'),
  createTenantInvitation: (payload) => safeSendData('post', '/auth/invitations', payload, undefined, '邀请暂时无法创建，请稍后重试。'),
  acceptTenantInvitation: (payload) => safeSendData('post', '/auth/invitations/accept', payload, undefined, '邀请暂时无法使用，请联系管理员确认。'),
  completeMfaEnrollment: (payload) => safeSendData('post', '/auth/mfa/enroll/complete', payload, undefined, '身份验证器绑定暂时无法完成，请稍后重试。'),
  requestPasswordReset: (payload) => safeSendData('post', '/auth/password-reset/request', payload, undefined, '暂时无法提交重置申请，请稍后重试。'),
  completePasswordReset: (payload) => safeSendData('post', '/auth/password-reset/complete', payload, undefined, '重置链接无效或已过期，请重新申请。'),
  getTenants: () => safeGetData('/admin/tenants', undefined, '租户列表暂时无法加载，请稍后重试。'),
  selectTenant: (tenantId) => safeSendData('post', `/admin/tenants/${encodeURIComponent(tenantId)}/select`, {}, undefined, '租户切换暂时无法完成，请稍后重试。'),
  healthCheck: () => getData('/health'),
  getStores: (params) => getData('/stores', params),
  createStoreOnboarding: (payload) => sendData('post', '/store-onboardings', payload),
  getStoreOnboardings: (params) => getData('/store-onboardings', params),
  getStoreOnboarding: (onboardingId) => getData(`/store-onboardings/${onboardingId}`),
  updateStoreOnboarding: (onboardingId, payload) => sendData('patch', `/store-onboardings/${onboardingId}`, payload),
  resumeStoreOnboarding: (onboardingId) => sendData('post', `/store-onboardings/${onboardingId}/resume`),
  historicalOrderBackfill: (onboardingId, payload) => sendData('post', `/store-onboardings/${onboardingId}/historical-backfill`, payload),
  createStore: (payload) => sendData('post', '/stores', payload),
  updateStore: (storeId, payload) => sendData('put', `/stores/${storeId}`, payload),
  openStoreBackend: (storeId) => sendData('post', `/stores/${encodeURIComponent(storeId)}/open-backend`, {}),
  getDashboardSummary: (params) => getData('/dashboard/summary', params),
  getStoreOverview: (params) => getData('/dashboard/store-overview', params),
  recoverAutomaticRead: (storeId) => sendData(
    'post',
    `/stores/${encodeURIComponent(storeId)}/automatic-read/recover`,
    { confirmation: true },
  ),
  getAiDailyContext: (params) => getData('/ai/daily-context', params),
  getProducts: (params) => getData('/products', params),
  getOrders: (params) => getData('/orders', params),
  getOrderLogisticsTrace: (orderId, params) => getData(`/orders/${orderId}/logistics-trace`, params),
  getShippingLogisticsMappings: (params) => getData('/shipping/logistics-mappings', params),
  getWarehouseShippingBatches: (params) => getData('/shipping/warehouse-batches', params),
  getWarehouseShippingTrackingDetails: (batchId, params) => getData(`/shipping/warehouse-batches/${batchId}/tracking-details`, params),
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
  getCustomerInquiries: (params) => getData('/customer-inquiries', params),
  refreshNaverCustomerInquiries: (storeId) => sendData('post', '/customer-inquiries/naver/refresh', undefined, { store_id: storeId }),
  getCustomerInquiryDetail: (readonlyId, storeId) => getData(`/customer-inquiries/${encodeURIComponent(readonlyId)}`, { store_id: storeId }),
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

export { getData, normalizeParams, safeErrorMessage, sendData };
export default backendApi;
