const numberValue = (value) => Number(value || 0);
const emptyText = (value, fallback = '—') => value ?? fallback;

function adaptPlatform(value) {
  const platforms = { naver: 'Naver', coupang: 'Coupang', gmarket: 'Gmarket' };
  return platforms[String(value || '').toLowerCase()] || value || '—';
}

function adaptStatus(value, mapping = {}) {
  return mapping[String(value || '').toLowerCase()] || value || '未知';
}

function compactPayload(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined && value !== null),
  );
}

function isSensitiveFinancialField(key = '') {
  const normalized = String(key).replace(/[_-]/g, '').toLowerCase();
  return [
    'bankaccountholder',
    'bankname',
    'bankaccount',
    'accesskey',
    'secretkey',
    'authorization',
    'signature',
    'token',
    'clientsecret',
  ].some((item) => normalized.includes(item));
}

function sanitizeFinancialObject(item = {}) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) return {};
  return Object.fromEntries(
    Object.entries(item)
      .filter(([key]) => !isSensitiveFinancialField(key))
      .map(([key, value]) => [key, value && typeof value === 'object' ? String(value) : value]),
  );
}

function sanitizeFieldMappingSuggestion(data = {}) {
  if (!data || typeof data !== 'object') return {};
  return Object.fromEntries(
    Object.entries(data)
      .filter(([key]) => !isSensitiveFinancialField(key))
      .map(([key, value]) => {
        if (Array.isArray(value)) {
          return [key, value.filter((item) => !isSensitiveFinancialField(item))];
        }
        if (value && typeof value === 'object') return [key, sanitizeFinancialObject(value)];
        return [key, value];
      }),
  );
}

function normalizePlatformForBackend(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const platforms = {
    naver: 'naver',
    coupang: 'coupang',
    gmarket: 'gmarket',
    '11街': '11st',
    '11st': '11st',
    '옥션': 'auction',
    auction: 'auction',
  };
  return platforms[normalized] || normalized || value;
}

function normalizeStoreStatusForBackend(value) {
  const statuses = {
    '正常运营': 'active',
    '정상 운영': 'active',
    active: 'active',
    '审核中': 'review',
    '심사중': 'review',
    review: 'review',
    '申诉中': 'appeal',
    appeal: 'appeal',
    '판매중지': 'inactive',
    inactive: 'inactive',
    '使用中止': 'inactive',
  };
  return statuses[String(value || '').trim()] || value || 'active';
}

function normalizeDeviceStatusForBackend(value) {
  const statuses = {
    active: 'active',
    inactive: 'inactive',
    warning: 'warning',
    '正常': 'active',
    '启用': 'active',
    '停用': 'inactive',
    '风险': 'warning',
  };
  return statuses[String(value || '').trim()] || value || 'active';
}

function normalizeCredentialPlatformForBackend(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const platforms = {
    naver: 'naver',
    coupang: 'coupang',
  };
  return platforms[normalized] || normalized || value;
}

function normalizeAccountStatusForBackend(value) {
  const statuses = {
    active: 'active',
    inactive: 'inactive',
    '鍚敤': 'active',
    '鍋滅敤': 'inactive',
  };
  return statuses[String(value || '').trim()] || value || 'active';
}

function normalizeAuthStatusForBackend(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const statuses = {
    not_configured: 'not_configured',
    configured: 'configured',
    needs_test: 'needs_test',
    test_failed: 'test_failed',
    test_passed: 'test_passed',
  };
  return statuses[normalized] || normalized || 'not_configured';
}

export function adaptStore(item = {}) {
  return {
    id: item.id,
    name: item.name,
    platform: adaptPlatform(item.platform),
    region: item.country,
    country: item.country,
    language: item.language,
    manager: emptyText(item.owner_name, '未配置'),
    products: numberValue(item.product_count),
    rawStatus: item.status,
    status: adaptStatus(item.status, { active: '정상 운영', inactive: '使用中止' }),
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: emptyText(item.updated_at),
  };
}

export function toBackendStorePayload(item = {}) {
  return compactPayload({
    name: String(item.name || '').trim(),
    platform: normalizePlatformForBackend(item.platform),
    country: String(item.country || item.region || 'KR').trim(),
    language: String(item.language || 'ko-KR').trim(),
    status: normalizeStoreStatusForBackend(item.status || item.rawStatus),
    owner_name: item.manager || item.ownerName || item.owner_name || null,
    remark: item.remark || null,
  });
}

export function adaptProduct(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    externalId: item.external_product_id,
    sku: item.sku || item.external_product_id,
    name: item.name,
    brand: item.brand,
    category: item.category,
    price: numberValue(item.price),
    currency: item.currency,
    stock: item.stock_quantity,
    rawStatus: item.status,
    status: adaptStatus(item.status, { active: '판매중', review: '심사중', suspended: '판매중지' }),
    store: item.store_name || `店铺 #${item.store_id}`,
    createdAt: item.created_at,
    updatedAt: emptyText(item.updated_at),
  };
}

export function adaptOrder(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    orderNo: item.external_order_id,
    product: item.product_name,
    productName: item.product_name,
    customer: item.buyer_name,
    customerName: item.buyer_name,
    maskedPhone: item.buyer_masked_phone,
    phone: emptyText(item.buyer_masked_phone),
    quantity: item.quantity,
    amount: numberValue(item.order_amount),
    currency: item.currency,
    rawStatus: item.order_status,
    status: adaptStatus(item.order_status, { paid: '待发货', shipped: '배송중', completed: '구매확정', cancelled: '取消退款', canceled: '取消退款' }),
    store: item.store_name || `店铺 #${item.store_id}`,
    paidAt: item.paid_at,
    createdAt: item.ordered_at,
    updatedAt: emptyText(item.updated_at),
  };
}

export function adaptCustomerInquiry(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    ticketNo: item.external_inquiry_id,
    type: item.inquiry_type,
    inquiryType: item.inquiry_type,
    customer: item.customer_name,
    customerName: item.customer_name,
    title: item.title,
    content: item.content,
    summary: item.title || item.content,
    rawStatus: item.status,
    status: adaptStatus(item.status, { open: '문의 대기', answered: '답변 완료', processing: '처리중' }),
    priority: item.priority || '일반',
    store: item.store_name || `店铺 #${item.store_id}`,
    orderNo: emptyText(item.order_no),
    productName: emptyText(item.product_name),
    receivedAt: item.received_at,
    createdAt: item.received_at,
    answeredAt: item.answered_at,
    lastReplyAt: emptyText(item.answered_at),
    updatedAt: emptyText(item.updated_at),
    orderInfo: {
      orderNo: emptyText(item.order_no),
      paymentMethod: '—',
      receiver: emptyText(item.customer_name),
      amount: 0,
      address: '—',
    },
    productInfo: {
      productName: emptyText(item.product_name),
      sku: '—',
      quantity: 0,
      store: item.store_name || `店铺 #${item.store_id}`,
    },
    replies: [],
  };
}

export function adaptSyncLog(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    type: item.sync_type,
    rawStatus: item.status,
    status: adaptStatus(item.status, { success: '성공', failed: '실패', running: '처리중', pending: '대기' }),
    message: item.message,
    startedAt: item.started_at,
    finishedAt: item.finished_at,
    logNo: `SYNC-${item.id ?? '—'}`,
    time: item.finished_at || item.started_at,
    module: '数据同步',
    actionType: item.sync_type,
    operator: 'Codex1 后端',
    objectName: adaptPlatform(item.platform),
    summary: item.message || item.sync_type,
    riskLevel: item.status === 'failed' ? '높음' : '낮음',
  };
}

export function adaptDeviceEnvironment(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    name: item.environment_name,
    deviceType: item.device_type,
    osName: item.os_name,
    browserName: item.browser_name,
    ipLabel: item.ip_label,
    proxyLabel: item.proxy_label,
    status: item.status,
    lastUsedAt: item.last_used_at,
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function toBackendDeviceEnvironmentPayload(item = {}, storeId) {
  return compactPayload({
    store_id: Number(item.storeId || storeId),
    environment_name: String(item.name || '').trim(),
    device_type: String(item.deviceType || '').trim(),
    os_name: item.osName || null,
    browser_name: item.browserName || null,
    ip_label: item.ipLabel || null,
    proxy_label: item.proxyLabel || null,
    status: normalizeDeviceStatusForBackend(item.status),
    last_used_at: item.lastUsedAt || null,
    remark: item.remark || null,
  });
}

export function adaptEmailAccount(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    email: item.email_address,
    address: item.email_address,
    provider: item.provider,
    label: item.account_label,
    purpose: item.account_label,
    hasCredential: Boolean(item.has_password_or_token),
    status: item.status,
    lastCheckedAt: item.last_checked_at,
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function toBackendEmailAccountPayload(item = {}, storeId) {
  return compactPayload({
    store_id: Number(item.storeId || storeId),
    email_address: String(item.email || '').trim(),
    provider: String(item.provider || '').trim(),
    account_label: item.label || null,
    password_or_token: item.credentialInput ? String(item.credentialInput) : undefined,
    status: normalizeAccountStatusForBackend(item.status),
    remark: item.remark || null,
  });
}

export function adaptImportantEmail(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    emailAccountId: item.email_account_id,
    platform: item.platform,
    type: item.mail_type,
    emailType: item.mail_type,
    sender: item.sender,
    subject: item.subject,
    title: item.subject,
    snippet: item.snippet,
    summary: item.snippet,
    receivedAt: item.received_at,
    status: item.status,
    priority: item.priority,
    relatedCaseId: item.related_case_id,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptAppealCase(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: item.platform,
    type: item.case_type,
    title: item.case_title,
    name: item.case_title,
    status: item.case_status,
    caseNo: item.external_case_id,
    deadlineAt: item.deadline_at,
    deadline: item.deadline_at,
    summary: item.summary,
    actionRequired: item.action_required,
    relatedOrderId: item.related_order_id,
    relatedProductId: item.related_product_id,
    submittedAt: item.submitted_at,
    resolvedAt: item.resolved_at,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptCredential(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    rawPlatform: item.platform,
    name: item.credential_name,
    credentialName: item.credential_name,
    vendorId: item.vendor_id,
    clientId: item.client_id,
    market: item.market,
    authStatus: item.auth_status || 'not_configured',
    lastTestedAt: item.last_tested_at,
    tokenExpiresAt: item.token_expires_at,
    apiRemark: item.api_remark,
    status: item.status,
    hasAccessKey: Boolean(item.has_access_key),
    hasSecretKey: Boolean(item.has_secret_key),
    hasAccessToken: Boolean(item.has_access_token),
    hasRefreshToken: Boolean(item.has_refresh_token),
    accessKeyStatus: item.has_access_key ? '已配置' : '未配置',
    secretKeyStatus: item.has_secret_key ? '已配置' : '未配置',
    accessTokenStatus: item.has_access_token ? '已配置' : '未配置',
    refreshTokenStatus: item.has_refresh_token ? '已配置' : '未配置',
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptPlatformLogin(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    rawPlatform: item.platform,
    label: item.login_label,
    account: item.login_account,
    emailAccountId: item.email_account_id,
    deviceEnvironmentId: item.device_environment_id,
    loginStatus: item.login_status,
    status: item.login_status,
    hasLoginPassword: Boolean(item.hasLoginPassword),
    passwordStatus: item.hasLoginPassword ? '已保存密码' : '未保存密码',
    lastLoginCheckAt: item.last_login_check_at,
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptApiCapability(item = {}) {
  return {
    id: item.id,
    platform: adaptPlatform(item.platform),
    rawPlatform: item.platform,
    capabilityKey: item.capability_key,
    capabilityName: item.capability_name,
    apiCategory: item.api_category,
    endpointPath: item.endpoint_path,
    method: item.method,
    requiredCredentialType: item.required_credential_type,
    requiredPermission: item.required_permission,
    ordinaryStoreSupported: item.ordinary_store_supported,
    testStatus: item.test_status,
    testMode: item.test_mode,
    requestParamsSummary: item.request_params_summary,
    responseFieldsSummary: item.response_fields_summary,
    errorCodesSummary: item.error_codes_summary,
    dataUsefulness: item.data_usefulness,
    firstPhaseCandidate: Boolean(item.first_phase_candidate),
    salesSourceType: item.sales_source_type,
    officialDocUrl: item.official_doc_url,
    docCheckedAt: item.doc_checked_at,
    notes: item.notes,
    lastCheckedAt: item.last_checked_at,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptApiCapabilityResult(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    capabilityId: item.capability_id,
    credentialId: item.credential_id,
    testMode: item.test_mode,
    testStatus: item.test_status,
    httpStatus: item.http_status,
    errorCode: item.error_code,
    permissionResult: item.permission_result,
    rateLimitSummary: item.rate_limit_summary,
    responseFieldsObserved: item.response_fields_observed,
    testedAt: item.tested_at,
    notes: item.notes,
    createdAt: item.created_at,
  };
}

export function toBackendCredentialPayload(item = {}, storeId) {
  const credentialName = item.name || item.credentialName;
  const payload = { store_id: Number(item.storeId || storeId) };
  if ('platform' in item) payload.platform = normalizeCredentialPlatformForBackend(item.platform);
  if (credentialName) payload.credential_name = String(credentialName).trim();
  if ('vendorId' in item) payload.vendor_id = item.vendorId ? String(item.vendorId).trim() : null;
  if ('clientId' in item) payload.client_id = item.clientId ? String(item.clientId).trim() : null;
  if (item.accessKeyInput) payload.access_key = String(item.accessKeyInput);
  if (item.secretKeyInput) payload.secret_key = String(item.secretKeyInput);
  if (item.accessTokenInput) payload.access_token = String(item.accessTokenInput);
  if (item.refreshTokenInput) payload.refresh_token = String(item.refreshTokenInput);
  if ('tokenExpiresAt' in item) payload.token_expires_at = item.tokenExpiresAt || null;
  if ('market' in item) payload.market = item.market ? String(item.market).trim() : null;
  if ('authStatus' in item) payload.auth_status = normalizeAuthStatusForBackend(item.authStatus);
  if ('lastTestedAt' in item) payload.last_tested_at = item.lastTestedAt || null;
  if ('apiRemark' in item) payload.api_remark = item.apiRemark || null;
  if ('status' in item) payload.status = normalizeAccountStatusForBackend(item.status);
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

export function toBackendPlatformLoginPayload(item = {}, storeId) {
  const payload = { store_id: Number(item.storeId || storeId) };
  if ('platform' in item) payload.platform = normalizeCredentialPlatformForBackend(item.platform);
  if ('label' in item) payload.login_label = item.label ? String(item.label).trim() : undefined;
  if ('account' in item) payload.login_account = item.account ? String(item.account).trim() : null;
  if (item.passwordInput) payload.login_password = String(item.passwordInput);
  if ('emailAccountId' in item) payload.email_account_id = item.emailAccountId ? Number(item.emailAccountId) : null;
  if ('deviceEnvironmentId' in item) payload.device_environment_id = item.deviceEnvironmentId ? Number(item.deviceEnvironmentId) : null;
  if ('loginStatus' in item || 'status' in item) payload.login_status = normalizeAccountStatusForBackend(item.loginStatus || item.status);
  if ('remark' in item) payload.remark = item.remark || null;
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

export function toBackendApiCapabilityPayload(item = {}) {
  const payload = {};
  if ('platform' in item) payload.platform = normalizeCredentialPlatformForBackend(item.platform);
  if ('capabilityKey' in item) payload.capability_key = String(item.capabilityKey || '').trim();
  if ('capabilityName' in item) payload.capability_name = String(item.capabilityName || '').trim();
  if ('apiCategory' in item) payload.api_category = String(item.apiCategory || '').trim();
  if ('endpointPath' in item) payload.endpoint_path = item.endpointPath ? String(item.endpointPath).trim() : null;
  if ('method' in item) payload.method = item.method ? String(item.method).trim().toUpperCase() : null;
  if ('requiredCredentialType' in item) payload.required_credential_type = item.requiredCredentialType ? String(item.requiredCredentialType).trim() : null;
  if ('requiredPermission' in item) payload.required_permission = item.requiredPermission || null;
  if ('ordinaryStoreSupported' in item) payload.ordinary_store_supported = item.ordinaryStoreSupported || 'unknown';
  if ('testStatus' in item) payload.test_status = item.testStatus || 'not_tested';
  if ('testMode' in item) payload.test_mode = item.testMode || 'docs_only';
  if ('requestParamsSummary' in item) payload.request_params_summary = item.requestParamsSummary || null;
  if ('responseFieldsSummary' in item) payload.response_fields_summary = item.responseFieldsSummary || null;
  if ('errorCodesSummary' in item) payload.error_codes_summary = item.errorCodesSummary || null;
  if ('dataUsefulness' in item) payload.data_usefulness = item.dataUsefulness || 'unknown';
  if ('firstPhaseCandidate' in item) payload.first_phase_candidate = Boolean(item.firstPhaseCandidate);
  if ('salesSourceType' in item) payload.sales_source_type = item.salesSourceType || 'not_applicable';
  if ('officialDocUrl' in item) payload.official_doc_url = item.officialDocUrl ? String(item.officialDocUrl).trim() : null;
  if ('docCheckedAt' in item) payload.doc_checked_at = item.docCheckedAt || null;
  if ('notes' in item) payload.notes = item.notes || null;
  if ('lastCheckedAt' in item) payload.last_checked_at = item.lastCheckedAt || null;
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

export function toBackendApiCapabilityResultPayload(item = {}, storeId) {
  const payload = { store_id: Number(item.storeId || storeId) };
  if ('capabilityId' in item) payload.capability_id = Number(item.capabilityId);
  if ('credentialId' in item) payload.credential_id = item.credentialId ? Number(item.credentialId) : null;
  if ('testMode' in item) payload.test_mode = item.testMode || 'manual';
  if ('testStatus' in item) payload.test_status = item.testStatus || 'planned';
  if ('httpStatus' in item) payload.http_status = item.httpStatus ? Number(item.httpStatus) : null;
  if ('errorCode' in item) payload.error_code = item.errorCode ? String(item.errorCode).trim() : null;
  if ('permissionResult' in item) payload.permission_result = item.permissionResult || null;
  if ('rateLimitSummary' in item) payload.rate_limit_summary = item.rateLimitSummary || null;
  if ('responseFieldsObserved' in item) payload.response_fields_observed = item.responseFieldsObserved || null;
  if ('testedAt' in item) payload.tested_at = item.testedAt || null;
  if ('notes' in item) payload.notes = item.notes || null;
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined && !Number.isNaN(value)));
}

export function adaptApiCapabilitySummary(data = {}) {
  return {
    semanticNotice: data.semantic_notice || '',
    platformSummary: (data.platform_summary || []).map((item) => ({
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      totalCapabilities: numberValue(item.total_capabilities),
      docsOnlyCount: numberValue(item.docs_only_count),
      manualCount: numberValue(item.manual_count),
      testedSuccessCount: numberValue(item.tested_success_count),
      notTestedCount: numberValue(item.not_tested_count),
      permissionRequiredCount: numberValue(item.permission_required_count),
      unavailableCount: numberValue(item.unavailable_count),
      firstPhaseCandidateCount: numberValue(item.first_phase_candidate_count),
      realReadonlyCount: numberValue(item.real_readonly_count),
      lastCheckedAt: item.last_checked_at,
    })),
    storeResultSummary: (data.store_result_summary || []).map((item) => ({
      storeId: item.store_id,
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      totalResults: numberValue(item.total_results),
      credentialBoundResults: numberValue(item.credential_bound_results),
      docsOnlyCount: numberValue(item.docs_only_count),
      manualCount: numberValue(item.manual_count),
      mockCount: numberValue(item.mock_count),
      sandboxCount: numberValue(item.sandbox_count),
      testedSuccessCount: numberValue(item.tested_success_count),
      testedFailedCount: numberValue(item.tested_failed_count),
      permissionRequiredCount: numberValue(item.permission_required_count),
      unavailableCount: numberValue(item.unavailable_count),
      notTestedCount: numberValue(item.not_tested_count),
      latestTestedAt: item.latest_tested_at,
      missingFirstPhaseCandidates: (item.missing_first_phase_candidates || []).map((candidate) => ({
        capabilityId: candidate.capability_id,
        platform: adaptPlatform(candidate.platform),
        rawPlatform: candidate.platform,
        capabilityKey: candidate.capability_key,
        capabilityName: candidate.capability_name,
        apiCategory: candidate.api_category,
      })),
    })),
    attentionItems: (data.attention_items || []).map((item, index) => ({
      id: item.code || `api-capability-attention-${index + 1}`,
      code: item.code,
      level: item.level || 'info',
      platform: item.platform ? adaptPlatform(item.platform) : null,
      rawPlatform: item.platform,
      storeId: item.store_id,
      count: numberValue(item.count),
      message: item.message,
    })),
  };
}

export function adaptApiCredentialReadiness(data = {}) {
  return {
    semanticNotice: data.semantic_notice || '',
    realApiTestEnabled: Boolean(data.real_api_test_enabled),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    platforms: (data.platforms || []).map((item) => ({
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      credentialStatus: item.credential_status || 'missing',
      readinessStatus: item.readiness_status || 'disabled',
      fields: item.fields || {},
    })),
  };
}

export function adaptApiCredentialSmokeTest(data = {}) {
  return {
    semanticNotice: data.semantic_notice || '',
    mode: data.mode || 'readonly',
    realApiTestEnabled: Boolean(data.real_api_test_enabled),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    results: (data.results || []).map((item) => ({
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      enabled: Boolean(item.enabled),
      configured: Boolean(item.configured),
      tokenTest: item.token_test || 'skipped',
      sellerOrAccountTest: item.seller_or_account_test || 'skipped',
      productReadTest: item.product_read_test || 'skipped',
      orderReadTest: item.order_read_test || 'skipped',
      settlementReadTest: item.settlement_read_test || 'skipped',
      errorCode: item.error_code || null,
      maskedMessage: item.masked_message || '',
      testedAt: item.tested_at || null,
    })),
  };
}

export function adaptCoupangOrderSyncResult(data = {}) {
  const syncLog = data.sync_log || {};
  const checkpoint = data.checkpoint || {};
  return {
    storeId: data.store_id,
    platform: adaptPlatform(data.platform),
    rawPlatform: data.platform,
    syncType: data.sync_type,
    sourceType: data.source_type,
    writeScope: data.write_scope,
    platformWrite: Boolean(data.platform_write),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    businessTimezone: data.business_timezone,
    startDate: data.start_date,
    endDate: data.end_date,
    windowStartAt: data.window_start_at,
    windowEndAt: data.window_end_at,
    maxPages: numberValue(data.max_pages),
    pageCount: numberValue(data.page_count),
    nextCursorExists: Boolean(data.next_cursor_exists),
    wouldCreate: numberValue(data.would_create),
    wouldUpdate: numberValue(data.would_update),
    createdCount: numberValue(data.created_count),
    updatedCount: numberValue(data.updated_count),
    skippedCount: numberValue(data.skipped_count),
    sampleIds: data.sample_ids || [],
    lastSyncedAt: data.last_synced_at,
    syncLog: {
      id: syncLog.id,
      status: syncLog.status,
      message: syncLog.message,
    },
    checkpoint: {
      id: checkpoint.id,
      lastSyncedAt: checkpoint.last_synced_at,
      windowStartAt: checkpoint.window_start_at,
      windowEndAt: checkpoint.window_end_at,
    },
  };
}

export function adaptCoupangProductSyncResult(data = {}) {
  const syncLog = data.sync_log || {};
  const checkpoint = data.checkpoint || {};
  return {
    storeId: data.store_id,
    platform: adaptPlatform(data.platform),
    rawPlatform: data.platform,
    syncType: data.sync_type,
    sourceType: data.source_type,
    writeScope: data.write_scope,
    platformWrite: Boolean(data.platform_write),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    statusFilter: data.status_filter || 'APPROVED',
    statusSemanticNotice: data.status_semantic_notice || '',
    maxPages: numberValue(data.max_pages),
    pageCount: numberValue(data.page_count),
    nextCursorExists: Boolean(data.next_cursor_exists),
    wouldCreate: numberValue(data.would_create),
    wouldUpdate: numberValue(data.would_update),
    createdCount: numberValue(data.created_count),
    updatedCount: numberValue(data.updated_count),
    skippedCount: numberValue(data.skipped_count),
    sampleIds: data.sample_ids || [],
    perStatus: (data.per_status || []).map((item) => ({
      status: item.status,
      statusSemantic: item.status_semantic || '',
      pageCount: numberValue(item.page_count),
      nextCursorExists: Boolean(item.next_cursor_exists),
      itemCount: numberValue(item.item_count),
      wouldCreate: numberValue(item.would_create),
      wouldUpdate: numberValue(item.would_update),
      skippedCount: numberValue(item.skipped_count),
      sampleIds: item.sample_ids || [],
    })),
    lastSyncedAt: data.last_synced_at,
    syncLog: {
      id: syncLog.id,
      status: syncLog.status,
      message: syncLog.message,
    },
    checkpoint: {
      id: checkpoint.id,
      lastSyncedAt: checkpoint.last_synced_at,
      windowStartAt: checkpoint.window_start_at,
      windowEndAt: checkpoint.window_end_at,
    },
  };
}

export function adaptCoupangFinancialPreviewResult(data = {}) {
  const syncLog = data.sync_log || {};
  return {
    storeId: data.store_id,
    platform: adaptPlatform(data.platform),
    rawPlatform: data.platform,
    syncType: data.sync_type,
    sourceType: data.source_type,
    businessTimezone: data.business_timezone,
    startDate: data.start_date,
    endDate: data.end_date,
    windowStartAt: data.window_start_at,
    windowEndAt: data.window_end_at,
    maxPages: numberValue(data.max_pages),
    pageCount: numberValue(data.page_count),
    nextCursorExists: Boolean(data.next_cursor_exists),
    totalRows: numberValue(data.total_rows),
    sampleIds: data.sample_ids || [],
    sampleRows: (data.sample_rows || []).map(sanitizeFinancialObject),
    summaryTotals: sanitizeFinancialObject(data.summary_totals || {}),
    months: data.months || [],
    perMonth: (data.per_month || []).map((item) => ({
      revenueRecognitionYearMonth: item.revenue_recognition_year_month,
      itemCount: numberValue(item.item_count),
      sampleIds: item.sample_ids || [],
    })),
    semanticNotice: data.semantic_notice || '',
    dateAvailabilityNotice: data.date_availability_notice || '',
    monthSemanticNotice: data.month_semantic_notice || '',
    fieldMappingSuggestion: sanitizeFieldMappingSuggestion(data.field_mapping_suggestion || {}),
    syncLog: {
      id: syncLog.id,
      status: syncLog.status,
      message: syncLog.message,
    },
  };
}

export function adaptDashboardSummary(data = {}) {
  const risks = (data.risk_flags || []).map((item, index) => ({
    id: item.code || `backend-risk-${index + 1}`,
    title: '后端风险提醒',
    description: item.message,
    status: item.level || 'info',
  }));
  const latestLogs = (data.latest_sync_logs || []).map(adaptSyncLog);
  const recentOrders = (data.recent_orders || []).map(adaptOrder);
  const pendingCustomers = numberValue(data.open_customer_inquiries);

  const summary = {
    storeTotal: numberValue(data.store_count),
    productTotal: numberValue(data.product_count),
    todayOrderCount: numberValue(data.order_count),
    todaySalesAmount: numberValue(data.total_sales_amount),
    scopeOrderCount: numberValue(data.order_count),
    scopeSalesAmount: numberValue(data.total_sales_amount),
    pendingCustomers,
    pendingAppeals: numberValue(data.open_appeal_cases),
    riskEnvironments: risks.filter((item) => /ENV|DEVICE|IP|LOGIN/i.test(item.id)).length,
    unreadImportantEmails: numberValue(data.unread_important_emails),
    currency: data.currency || 'KRW',
    businessTimezone: data.business_timezone,
    businessDate: data.business_date,
    businessDayStart: data.business_day_start,
    businessDayEnd: data.business_day_end,
    apiCapabilitySummary: adaptApiCapabilitySummary(data.api_capability_summary),
  };

  const todos = pendingCustomers > 0
    ? [{ id: 'backend-inquiries', title: '待回复客服', description: `${pendingCustomers} 条咨询等待回复`, status: '대기중' }]
    : [];

  return {
    ...summary,
    summary,
    risks,
    todos,
    activities: {
      logs: [
        ...latestLogs.map((item) => ({
          ...item,
          module: '同步任务',
          summary: item.message || item.type,
          time: item.finishedAt || item.startedAt || '',
        })),
        ...recentOrders.map((item) => ({
          ...item,
          module: '最近订单',
          summary: `${item.orderNo || '订单'} · ${item.product || ''}`,
          time: item.createdAt || '',
        })),
      ],
      appeals: [],
      customers: [],
      emails: [],
      orders: recentOrders,
    },
    recentOrders,
    latestSyncLogs: latestLogs,
  };
}

export function adaptAiDailyContext(data = {}) {
  return {
    date: data.date,
    businessTimezone: data.business_timezone,
    businessDayStart: data.business_day_start,
    businessDayEnd: data.business_day_end,
    scope: {
      storeId: data.scope?.store_id ?? null,
      platform: data.scope?.platform ? adaptPlatform(data.scope.platform) : null,
    },
    salesSummary: data.sales_summary || {},
    orderSummary: data.order_summary || {},
    customerInquirySummary: data.customer_inquiry_summary || {},
    syncSummary: data.sync_summary || {},
    apiCapabilityContext: adaptApiCapabilitySummary(data.api_capability_context),
    riskFlags: data.risk_flags || [],
    recommendedFocus: data.recommended_focus || [],
  };
}

export function adaptList(data, adapter) {
  const source = Array.isArray(data) ? { items: data, total: data.length } : (data || {});
  const items = (source.items || []).map(adapter);
  return {
    data: items,
    items,
    total: source.total ?? items.length,
    page: source.page ?? 1,
    pageSize: source.page_size ?? source.pageSize ?? (items.length || 10),
  };
}

export const adapters = {
  store: adaptStore,
  product: adaptProduct,
  order: adaptOrder,
  customerInquiry: adaptCustomerInquiry,
  syncLog: adaptSyncLog,
  deviceEnvironment: adaptDeviceEnvironment,
  emailAccount: adaptEmailAccount,
  importantEmail: adaptImportantEmail,
  appealCase: adaptAppealCase,
  credential: adaptCredential,
  platformLogin: adaptPlatformLogin,
  apiCapability: adaptApiCapability,
  apiCapabilityResult: adaptApiCapabilityResult,
  apiCapabilitySummary: adaptApiCapabilitySummary,
  apiCredentialReadiness: adaptApiCredentialReadiness,
  apiCredentialSmokeTest: adaptApiCredentialSmokeTest,
  coupangOrderSyncResult: adaptCoupangOrderSyncResult,
  coupangProductSyncResult: adaptCoupangProductSyncResult,
  coupangFinancialPreviewResult: adaptCoupangFinancialPreviewResult,
  toBackendStorePayload,
  toBackendDeviceEnvironmentPayload,
  toBackendEmailAccountPayload,
  toBackendCredentialPayload,
  toBackendPlatformLoginPayload,
  toBackendApiCapabilityPayload,
  toBackendApiCapabilityResultPayload,
  dashboardSummary: adaptDashboardSummary,
  aiDailyContext: adaptAiDailyContext,
  list: adaptList,
};

export default adapters;
