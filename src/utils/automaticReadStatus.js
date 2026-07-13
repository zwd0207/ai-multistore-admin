const SAFE_FAILURE_LABELS = {
  not_supported: '暂未接入自动读取',
  temporary_platform_or_network_failure: '平台或网络暂时异常',
  authentication_or_permission_required: '需要管理员检查凭证或权限',
  cursor_requires_manual_review: '需要管理员检查同步进度',
  privacy_cleanup_gate_blocked: '数据清理状态异常，已暂停读取',
  source_conflict_requires_manual_review: '数据存在冲突，需要管理员检查',
  manual_review_required: '需要管理员检查',
};

function adaptAutomaticReadResource(source = {}) {
  const safeFailureReason = source.safe_failure_reason || '';
  return {
    status: source.status || 'unknown',
    lastSuccessAt: source.last_success_at || '',
    nextRunAt: source.next_run_at || '',
    dataFreshUntil: source.data_fresh_until || '',
    automaticReadEnabled: source.automatic_read_enabled,
    retryCount: source.retry_count ?? null,
    safeFailureReason,
    safeFailureLabel: SAFE_FAILURE_LABELS[safeFailureReason] || '',
    isStale: source.is_stale,
    lastAttemptAt: source.last_attempt_at || '',
  };
}

export function adaptAutomaticReadStatus(value = {}) {
  const source = value || {};
  return {
    orders: adaptAutomaticReadResource(source.orders),
    customerInquiries: adaptAutomaticReadResource(source.customer_inquiries || source.customerInquiries),
    products: adaptAutomaticReadResource(source.products),
    logistics: adaptAutomaticReadResource(source.logistics),
  };
}
