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
    name: item.credential_name,
    credentialName: item.credential_name,
    status: item.status,
    hasAccessKey: Boolean(item.has_access_key),
    hasSecretKey: Boolean(item.has_secret_key),
    accessKeyStatus: item.has_access_key ? '已配置' : '未配置',
    secretKeyStatus: item.has_secret_key ? '已配置' : '未配置',
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

export function toBackendCredentialPayload(item = {}, storeId) {
  const credentialName = item.name || item.credentialName;
  return compactPayload({
    store_id: Number(item.storeId || storeId),
    platform: normalizeCredentialPlatformForBackend(item.platform),
    credential_name: credentialName ? String(credentialName).trim() : undefined,
    access_key: item.accessKeyInput ? String(item.accessKeyInput) : undefined,
    secret_key: item.secretKeyInput ? String(item.secretKeyInput) : undefined,
    status: normalizeAccountStatusForBackend(item.status),
  });
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
    pendingCustomers,
    pendingAppeals: numberValue(data.open_appeal_cases),
    riskEnvironments: risks.filter((item) => /ENV|DEVICE|IP|LOGIN/i.test(item.id)).length,
    unreadImportantEmails: numberValue(data.unread_important_emails),
    currency: data.currency || 'KRW',
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
    scope: {
      storeId: data.scope?.store_id ?? null,
      platform: data.scope?.platform ? adaptPlatform(data.scope.platform) : null,
    },
    salesSummary: data.sales_summary || {},
    orderSummary: data.order_summary || {},
    customerInquirySummary: data.customer_inquiry_summary || {},
    syncSummary: data.sync_summary || {},
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
  toBackendStorePayload,
  toBackendDeviceEnvironmentPayload,
  toBackendEmailAccountPayload,
  toBackendCredentialPayload,
  toBackendPlatformLoginPayload,
  dashboardSummary: adaptDashboardSummary,
  aiDailyContext: adaptAiDailyContext,
  list: adaptList,
};

export default adapters;
