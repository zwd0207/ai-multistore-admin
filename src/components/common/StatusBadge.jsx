const toneKeywords = [
  { tone: 'danger', words: ['失败', '错误', '异常', '风险', '紧急', '缺货', '取消', '退款', '退货', '侵权', '冻结', '停用', '未通过'] },
  { tone: 'warning', words: ['待', '需要', '预警', '低库存', '审核', '申诉', '补充', '处理中', '未开放', '暂未', '待同步', '待配置'] },
  { tone: 'success', words: ['正常', '成功', '完成', '已配置', '已启用', '已保存', '已发货', '销售中', '可导出', '可查询', '可使用'] },
  { tone: 'info', words: ['本地', '只读', '演示', '提示', '同步中', '配送中', '读取', '预览'] },
];

const valueLabels = {
  active: '已启用',
  inactive: '已停用',
  normal: '正常',
  success: '正常',
  warning: '提醒',
  danger: '风险',
  info: '提示',
  pending: '待处理',
  not_open: '暂未开放',
  configured: '已配置',
  unconfigured: '未配置',
};

function normalizeDisplay(value) {
  const text = String(value ?? '').trim();
  return valueLabels[text] || text || '-';
}

function getTone(value) {
  const text = normalizeDisplay(value).toLowerCase();
  if (['success', 'warning', 'danger', 'info', 'neutral', 'pending'].includes(String(value))) return String(value);
  const matched = toneKeywords.find((item) => item.words.some((word) => text.includes(word.toLowerCase())));
  return matched?.tone || 'neutral';
}

export default function StatusBadge({ value, tone }) {
  const displayValue = normalizeDisplay(value);
  return <span className={`status-badge ${tone || getTone(value)}`}><i />{displayValue}</span>;
}
