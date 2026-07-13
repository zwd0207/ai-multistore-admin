export const STORE_SYNC_STATUS_LABELS = {
  idle: '等待自动同步',
  due: '等待自动同步',
  running: '正在自动同步',
  retry_wait: '同步失败，系统将自动重试',
  blocked: '需要管理员处理',
  success: '数据已更新',
  stale: '数据可能已过期',
  disabled: '自动读取已关闭',
};

export function storeSyncStatusLabel(status) {
  return STORE_SYNC_STATUS_LABELS[status] || '等待自动同步';
}

export function formatStoreSyncTime(value) {
  return value || '暂无记录';
}
