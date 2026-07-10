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
  '系统已保存商品记录',
  '暂不支持在线编辑',
  '运营建议',
  '跳转发货辅助',
  '修改平台库存暂未开放',
  '删除真实平台商品暂未开放',
]);

includesAll('src/pages/InventoryAlerts.jsx', [
  '缺货商品',
  '低库存商品',
  '库存正常商品',
  '处理优先级',
  '先处理缺货',
  '本地库存判断',
]);

includesAll('src/pages/ShippingAssistant.jsx', [
  '提交 Naver 发货回填',
  '人工确认回填',
  '下一步',
  '发货处理顺序',
  '生成发货表格',
  '导入物流单号表',
  '已按官方 API 开放',
]);

includesAll('src/pages/Dashboard.jsx', [
  '核心运营工作台',
  '今天先处理什么',
  '只打磨核心运营链路',
]);

includesAll('src/pages/Orders.jsx', [
  '订单状态分组',
  '共 {rows.length} 条订单',
  'Pagination',
]);

includesAll('src/pages/CustomerService.jsx', [
  '已接入 Naver 官方 API 读取',
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
  '多店铺电商管理后台',
  '韩国时间（KST',
  '韩元（KRW',
]);

includesAll('src/layouts/AdminLayout.jsx', [
  '首页工作台',
  '订单管理',
  '发货辅助',
  '商品管理',
  '库存预警',
  '店铺管理',
  '平台消息',
  '申诉中心',
  '邮箱中心',
  '系统设置',
]);

console.log('core ERP page contract checks passed');
