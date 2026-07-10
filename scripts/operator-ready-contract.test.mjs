import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function includesAll(file, phrases) {
  const text = read(file);
  for (const phrase of phrases) {
    assert.ok(text.includes(phrase), `${file} should include "${phrase}"`);
  }
}

function exists(file) {
  assert.ok(fs.existsSync(path.join(root, file)), `${file} should exist`);
}

exists('scripts/operator-start.ps1');
exists('scripts/operator-db-backup.ps1');
exists('scripts/operator-readiness-check.mjs');
exists('PHASE_CORE_ERP_OPERATOR_READY_1.md');

includesAll('scripts/operator-start.ps1', [
  'Core-ERP-Operator-Ready-1',
  'dashboard/store-overview',
  'sync/manual-batch/all',
  'REAL_API_WRITE_ENABLED=false',
  'Controlled Naver platform writes stay on operation gates',
]);

includesAll('scripts/operator-db-backup.ps1', [
  'create_local_backup.py',
  'Core-ERP-Operator-Ready-1',
  'manual_checkpoint',
]);

includesAll('scripts/operator-readiness-check.mjs', [
  'operator_readiness',
  'controlled_platform_write_ready',
  'generic_platform_write_closed',
  '/dashboard/store-overview',
  '/backups/local-report/summary',
]);

includesAll('src/pages/Settings.jsx', [
  '交付检查',
  '后端服务',
  '平台写入边界',
  'Naver 受控开放',
  '当前数据源',
  '备份状态',
  '运营 SOP',
]);

includesAll('src/services/dataProvider.js', [
  'getOperatorReadiness',
  'controlledPlatformWriteReady',
  'unknownStoreCount',
]);

includesAll('src/services/backendApi.js', [
  'getBackupLocalReportSummary',
  'healthCheck',
]);

includesAll('codex1/backend/app/api/v1/endpoints/health.py', [
  'real_api_write_enabled',
  'platform_write_closed',
  'controlled_platform_writes_enabled',
  'approved_platform_write_operations',
]);

includesAll('PHASE_CORE_ERP_OPERATOR_READY_1.md', [
  '运营试用交付',
  'Naver 订单模块',
  '手动批量刷新',
  'Naver 客服消息模块',
  '同步平台消息',
  '不是 0',
  'IP 白名单',
  'Naver 发货回填',
  '受控平台写入',
]);

console.log('operator ready contract checks passed');
