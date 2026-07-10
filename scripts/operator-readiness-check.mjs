import process from 'node:process';

const baseUrl = (process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8012/api/v1').replace(/\/+$/, '');

async function request(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { Accept: 'application/json', ...(options.headers || {}) },
    ...options,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok || payload?.success === false) {
    const error = new Error(payload?.message || `${path} returned ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload?.data ?? payload;
}

async function main() {
  const result = {
    status: 'operator_readiness',
    base_url: baseUrl,
    checked_at: new Date().toISOString(),
    backend_online: false,
    platform_write_closed: false,
    generic_platform_write_closed: false,
    controlled_platform_writes_enabled: false,
    controlled_platform_write_ready: false,
    platform_write_mode: 'unknown',
    endpoint_status: {},
    store_count: 0,
    unknown_store_count: 0,
    ip_blocked_store_count: 0,
    backup_count: 0,
    backup_needs_attention_count: 0,
    hard_gate_passed: false,
    next_actions: [],
  };

  const health = await request('/health');
  result.backend_online = health.status === 'ok';
  result.platform_write_closed = health.platform_write_closed === true && health.real_api_write_enabled === false;
  result.generic_platform_write_closed = (health.generic_platform_write_closed ?? health.platform_write_closed) === true
    && health.real_api_write_enabled === false;
  result.controlled_platform_writes_enabled = health.controlled_platform_writes_enabled === true;
  result.controlled_platform_write_ready = result.generic_platform_write_closed
    && result.controlled_platform_writes_enabled
    && health.platform_write_mode === 'controlled_naver_official_writes';
  result.platform_write_mode = health.platform_write_mode || 'unknown';
  result.endpoint_status.health = 'ok';

  const overview = await request('/dashboard/store-overview?include_inactive=false');
  result.endpoint_status['/dashboard/store-overview'] = 'ok';
  result.store_count = Number(overview.summary?.store_count || 0);
  result.unknown_store_count = Math.max(
    Number(overview.summary?.orders_unknown_store_count || 0),
    Number(overview.summary?.inventory_unknown_store_count || 0),
  );
  result.ip_blocked_store_count = Number(overview.summary?.ip_blocked_store_count || 0);

  const backup = await request('/backups/local-report/summary?limit=5');
  result.endpoint_status['/backups/local-report/summary'] = 'ok';
  result.backup_count = Number(backup.existing_backup_count || backup.backup_count || 0);
  result.backup_needs_attention_count = Number(backup.needs_attention_count || 0);

  const syncProbe = await fetch(`${baseUrl}/sync/manual-batch/all`, { method: 'OPTIONS' });
  result.endpoint_status['/sync/manual-batch/all'] = syncProbe.status === 404 ? 'missing' : 'available';

  if (!result.backend_online) result.next_actions.push('启动或重启后端服务');
  if (!result.generic_platform_write_closed) result.next_actions.push('关闭通用平台写入开关 REAL_API_WRITE_ENABLED=false，仅保留受控 Naver 写入入口');
  if (!result.controlled_platform_write_ready) result.next_actions.push('确认受控平台写入边界：只允许 Naver 发货回填和人工客服回复');
  if (!result.store_count) result.next_actions.push('先在店铺管理中创建或导入店铺');
  if (result.ip_blocked_store_count) result.next_actions.push('处理 Coupang / Naver IP 白名单或访问权限');
  if (!result.backup_count) result.next_actions.push('运行 scripts/operator-db-backup.ps1 创建本地备份');

  result.hard_gate_passed = result.backend_online
    && result.controlled_platform_write_ready
    && result.endpoint_status['/dashboard/store-overview'] === 'ok'
    && result.endpoint_status['/sync/manual-batch/all'] === 'available';

  console.log(JSON.stringify(result, null, 2));
  if (!result.hard_gate_passed) process.exitCode = 1;
}

main().catch((error) => {
  console.error(JSON.stringify({
    status: 'operator_readiness_failed',
    base_url: baseUrl,
    message: error.message,
    http_status: error.status || 0,
  }, null, 2));
  process.exitCode = 1;
});
