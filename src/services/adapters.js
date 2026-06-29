const numberValue = (value) => Number(value || 0);
const emptyText = (value, fallback = '—') => value ?? fallback;

function adaptPlatform(value) {
  const platforms = { naver: 'Naver', coupang: 'Coupang', gmarket: 'Gmarket' };
  return platforms[String(value || '').toLowerCase()] || value || '—';
}

function adaptStatus(value, mapping = {}) {
  return mapping[String(value || '').toLowerCase()] || value || '未知';
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
  dashboardSummary: adaptDashboardSummary,
  aiDailyContext: adaptAiDailyContext,
  list: adaptList,
};

export default adapters;
