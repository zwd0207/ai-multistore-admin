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
    assert.ok(
      text.includes(phrase),
      `${file} should include "${phrase}"`,
    );
  }
}

includesAll('src/pages/Products.jsx', [
  '商品记录',
  '暂不支持在线编辑',
  '运营建议',
  '进入仓库发货',
  '修改平台库存暂未开放',
  '删除真实平台商品暂未开放',
]);

includesAll('src/pages/InventoryAlerts.jsx', [
  '缺货商品',
  '低库存商品',
  '库存正常商品',
  '处理优先级',
  '先处理缺货',
  '已检查商品',
]);

includesAll('src/pages/ShippingAssistant.jsx', [
  '待生成发货批次',
  '已发仓库，等待回传',
  '仓库表导入与异常校验',
  '待确认平台回填',
  '已完成与失败',
  '创建发货批次',
  '下载仓库发货表',
  '上传仓库回传表',
  '仓库发货',
]);

const shippingText = read('src/pages/ShippingAssistant.jsx');
const visibleShippingText = [
  ...[...shippingText.matchAll(/>([^<>{}]+)</g)].map((match) => match[1]),
  ...[...shippingText.matchAll(/(?:title|description|note|placeholder|aria-label)="([^"]+)"/g)].map((match) => match[1]),
  ...[...shippingText.matchAll(/setNotice\('([^']+)'\)/g)].map((match) => match[1]),
].join(' ');
assert.ok(!/\b(API|token|hash|readonly|gate|mock)\b/i.test(visibleShippingText), 'shipping page must not expose technical terms to operators');

includesAll('src/pages/Dashboard.jsx', [
  '今日工作台',
  '今天先处理什么',
  '常用任务集中在这里',
]);

includesAll('src/services/adapters.js', [
  'adaptOperatorWorkbench',
  'operator_workbench',
  'actionPath',
  'sourceStatus',
]);

includesAll('src/pages/Dashboard.jsx', [
  'operatorWorkbench',
  'workbench-section',
  'completed_today',
  'customer_inquiries',
]);

assert.ok(
  !read('src/pages/Dashboard.jsx').includes('function isPendingShipment'),
  'dashboard must consume backend workbench rules instead of duplicating shipment classification',
);
assert.ok(
  !read('src/pages/Dashboard.jsx').includes('function isAbnormalOrder'),
  'dashboard must consume backend workbench rules instead of duplicating abnormal-order classification',
);

includesAll('src/pages/Orders.jsx', ['useSearchParams', "searchParams.get('orderId')"]);
includesAll('src/pages/ShippingAssistant.jsx', ['useSearchParams', "searchParams.get('batchId')", 'WORKBENCH_STAGE_MAP']);
includesAll('src/pages/CustomerService.jsx', ['useSearchParams', "searchParams.get('inquiryId')"]);

const { adaptDashboardSummary } = await import('../src/services/adapters.js');
const adaptedWorkbench = adaptDashboardSummary({
  operator_workbench: {
    summary: { urgent: 1, action_required: 2, waiting: 3, completed_today: 4 },
    sections: {
      urgent: [{
        task_id: 'abnormal_order:1', task_type: 'abnormal_order', priority: 100,
        title: '异常订单', description: '需要查看', status: 'urgent', count: 1,
        action_path: '/orders?status=abnormal&orderId=1', action_label: '查看订单',
        related_order_id: 1, related_batch_id: null, related_inquiry_id: null,
        updated_at: '2026-07-13T00:00:00+00:00', stale: false,
      }],
      action_required: [], waiting: [], completed_today: [],
    },
    sources: {
      orders: { status: 'ready' }, shipping: { status: 'ready' },
      customer_inquiries: { status: 'blocked', reason_code: 'cleanup_failed' },
    },
  },
}).summary.operatorWorkbench;
assert.equal(adaptedWorkbench.summary.actionRequired, 2);
assert.equal(adaptedWorkbench.sections.urgent[0].actionPath, '/orders?status=abnormal&orderId=1');
assert.equal(adaptedWorkbench.sources.customer_inquiries.sourceStatus, 'blocked');

includesAll('src/pages/Orders.jsx', [
  '订单状态分组',
  '共 {rows.length} 条订单',
  'Pagination',
]);

includesAll('src/pages/CustomerService.jsx', [
  '客户咨询',
  '更新客户咨询',
  '提交到 Naver',
  '人工确认发送',
]);

includesAll('src/components/common/Modal.jsx', [
  '<button type="button" className="modal-close" onClick={onClose} aria-label="关闭">',
  '<button type="button" className="button ghost" onClick={onClose}>取消</button>',
  '<button type="button" className="button primary" onClick={onConfirm} disabled={confirmDisabled}>',
]);

const modalText = read('src/components/common/Modal.jsx');
assert.ok(
  !modalText.includes('className="modal-close" onClick={onClose} disabled={confirmDisabled}'),
  'modal close button must remain clickable when confirm action is disabled',
);
assert.ok(
  !modalText.includes('className="button ghost" onClick={onClose} disabled={confirmDisabled}'),
  'modal cancel button must remain clickable when confirm action is disabled',
);

includesAll('src/pages/Appeals.jsx', [
  '正品审核',
  '知识产权 / 侵权',
  '结算冻结',
  '新建申诉案件（暂未开放）',
]);

includesAll('src/pages/Emails.jsx', [
  '不是邮箱登录密码',
  '授权码或应用专用密码',
  '不做邮箱深度 AI 识别',
]);

includesAll('src/pages/Settings.jsx', [
  '管理员设置',
  '韩国时间（KST',
  '韩元（KRW',
]);

includesAll('src/layouts/AdminLayout.jsx', [
  '今日工作台',
  '订单处理',
  '仓库发货',
  '商品管理',
  '库存预警',
  '店铺与平台连接',
  '客户咨询',
  '售后异常',
  '邮箱与平台通知',
  '管理员设置',
]);

console.log('core ERP page contract checks passed');
