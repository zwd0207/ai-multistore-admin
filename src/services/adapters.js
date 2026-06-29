const numberValue = (value) => Number(value || 0);

export function adaptStore(item = {}) {
  return {
    id: item.id,
    name: item.name,
    platform: item.platform,
    region: item.country,
    country: item.country,
    language: item.language,
    manager: item.owner_name,
    status: item.status,
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptProduct(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: item.platform,
    externalId: item.external_product_id,
    sku: item.sku || item.external_product_id,
    name: item.name,
    brand: item.brand,
    category: item.category,
    price: numberValue(item.price),
    currency: item.currency,
    stock: item.stock_quantity,
    status: item.status,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptOrder(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: item.platform,
    orderNo: item.external_order_id,
    product: item.product_name,
    productName: item.product_name,
    customer: item.buyer_name,
    customerName: item.buyer_name,
    maskedPhone: item.buyer_masked_phone,
    quantity: item.quantity,
    amount: numberValue(item.order_amount),
    currency: item.currency,
    status: item.order_status,
    paidAt: item.paid_at,
    createdAt: item.ordered_at,
    updatedAt: item.updated_at,
  };
}

export function adaptCustomerInquiry(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: item.platform,
    ticketNo: item.external_inquiry_id,
    type: item.inquiry_type,
    customer: item.customer_name,
    customerName: item.customer_name,
    title: item.title,
    content: item.content,
    summary: item.title || item.content,
    status: item.status,
    receivedAt: item.received_at,
    createdAt: item.received_at,
    answeredAt: item.answered_at,
    updatedAt: item.updated_at,
  };
}

export function adaptSyncLog(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: item.platform,
    type: item.sync_type,
    status: item.status,
    message: item.message,
    startedAt: item.started_at,
    finishedAt: item.finished_at,
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
    scope: data.scope || {},
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
    items,
    total: source.total ?? items.length,
    page: source.page ?? 1,
    pageSize: source.page_size ?? source.pageSize ?? items.length,
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
  dashboardSummary: adaptDashboardSummary,
  aiDailyContext: adaptAiDailyContext,
  list: adaptList,
};

export default adapters;
