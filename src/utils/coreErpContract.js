const SOURCE_TYPES = {
  officialApi: {
    key: 'official_api',
    label: '已接入官方 API',
    description: '来自官方开放 API 的只读结果，写入动作仍需单独审批。',
  },
  localSaved: {
    key: 'local_saved_record',
    label: '读取自本地保存记录',
    description: '系统本地保存的运营记录，不代表正在实时读取平台后台。',
  },
  localAssistant: {
    key: 'local_assistant',
    label: '本地辅助功能',
    description: '只用于人工核对、导出、备注或资料整理，不会操作平台。',
  },
  demo: {
    key: 'demo_data',
    label: '演示数据',
    description: '仅用于页面演示或本地 mock 流程。',
  },
  unavailable: {
    key: 'unavailable',
    label: '暂未开放',
    description: '当前阶段不提供真实平台能力。',
  },
  manualPlatform: {
    key: 'manual_platform',
    label: '需人工到平台后台处理',
    description: '系统只做提醒和资料整理，最终处理需人工进入平台后台。',
  },
};

const LOCAL_SAVED_PATTERNS = [
  'real_sync',
  'real_order_sync',
  'product_sync',
  'local_order',
  'local_products',
  'local_saved',
  'backend',
];

const DEMO_PATTERNS = [
  'mock',
  'demo',
  'shipping_mock',
  'local_frontend_mock',
];

export const DANGEROUS_PLATFORM_ACTIONS = {
  platform_inventory_write: '修改平台库存',
  platform_price_write: '修改平台商品价格',
  product_publish_write: '批量上下架',
  product_delete_write: '删除真实平台商品',
  shipment_writeback: '发货回填平台',
  customer_auto_reply: '自动回复客户',
  appeal_auto_submit: '自动提交申诉',
  email_auto_send: '自动发送邮件',
};

export const CORE_API_CAPABILITY_MATRIX = [
  {
    platform: 'naver',
    feature: 'auth',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '可只读检测',
    permission: 'Commerce API Center 应用、Client ID/Secret、店铺权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Naver 平台认证/连接检测',
  },
  {
    platform: 'naver',
    feature: 'product_read',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '可开发真实读取',
    permission: '商品 API 权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Naver 商品读取',
  },
  {
    platform: 'naver',
    feature: 'order_read',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '可开发真实读取',
    permission: '订单 API 权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Naver 订单读取',
  },
  {
    platform: 'naver',
    feature: 'shipment_writeback',
    category: 'A',
    apiDirection: '写入',
    currentPhase: '本阶段关闭',
    permission: '发货/配送相关 API 权限，接口级别需再次核对',
    risk: '会改变平台配送数据',
    humanConfirm: true,
    label: 'Naver 发货回填',
  },
  {
    platform: 'naver',
    feature: 'claim_processing',
    category: 'A',
    apiDirection: '写入',
    currentPhase: '本阶段关闭',
    permission: '取消/退货/换货相关 API 权限，动作级别需逐项核对',
    risk: '会改变平台售后状态',
    humanConfirm: true,
    label: 'Naver 售后处理',
  },
  {
    platform: 'naver',
    feature: 'customer_message',
    category: 'A',
    apiDirection: '读取/写入',
    currentPhase: '先做入口和本地管理',
    permission: '客户咨询 API 权限',
    risk: '回复会改变平台客服记录',
    humanConfirm: true,
    label: 'Naver 客户咨询',
  },
  {
    platform: 'coupang',
    feature: 'product_read',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '可开发真实读取',
    permission: 'Coupang Open API 商品权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Coupang 商品读取',
  },
  {
    platform: 'coupang',
    feature: 'order_read',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '可开发真实读取',
    permission: 'Coupang Open API 订单权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Coupang 订单读取',
  },
  {
    platform: 'coupang',
    feature: 'settlement_read',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '高级财务暂缓',
    permission: '结算 API 权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Coupang 结算读取',
  },
  {
    platform: 'gmarket',
    feature: 'product_read',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '待接入',
    permission: 'ESM Trading API 使用权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Gmarket/ESM 商品读取',
  },
  {
    platform: 'gmarket',
    feature: 'order_read',
    category: 'A',
    apiDirection: '读取',
    currentPhase: '待接入',
    permission: 'ESM Trading API 使用权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: 'Gmarket/ESM 订单读取',
  },
  {
    platform: 'gmarket',
    feature: 'appeal_submit',
    category: 'C',
    apiDirection: '写入',
    currentPhase: '不能做真实自动提交',
    permission: '未确认开放自动申诉提交接口',
    risk: '可能改变平台审核/申诉状态',
    humanConfirm: true,
    label: 'Gmarket/ESM 自动申诉提交',
  },
  {
    platform: 'all',
    feature: 'local_shipping_assistant',
    category: 'B',
    apiDirection: '本地',
    currentPhase: '本地辅助功能',
    permission: '不需要平台写入权限',
    risk: '不改变平台数据',
    humanConfirm: false,
    label: '发货表格、库存编号、物流单号匹配',
  },
  {
    platform: 'all',
    feature: 'internal_note',
    category: 'B',
    apiDirection: '本地',
    currentPhase: '本地辅助功能',
    permission: '不需要平台写入权限',
    risk: '只保存系统内备注',
    humanConfirm: false,
    label: '内部备注',
  },
  {
    platform: 'all',
    feature: 'ai_auto_actions',
    category: 'C',
    apiDirection: '自动写入',
    currentPhase: '暂未开放',
    permission: '未进入本阶段',
    risk: '可能自动改变平台、邮箱或客服状态',
    humanConfirm: true,
    label: 'AI 自动回复/自动上架/自动发送',
  },
];

export function normalizePlatform(value = '') {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized.includes('naver')) return 'naver';
  if (normalized.includes('coupang')) return 'coupang';
  if (normalized.includes('gmarket') || normalized.includes('esm')) return 'gmarket';
  return normalized || 'all';
}

export function classifyCoreDataSource(record = {}) {
  if (record.localAssistant) return SOURCE_TYPES.localAssistant;
  if (record.manualPlatform) return SOURCE_TYPES.manualPlatform;
  if (record.unavailable) return SOURCE_TYPES.unavailable;
  if (record.officialApi) return SOURCE_TYPES.officialApi;

  const sourceText = String(
    record.sourceType
      || record.source_type
      || record.dataSource
      || record.source
      || '',
  ).toLowerCase();

  if (DEMO_PATTERNS.some((pattern) => sourceText.includes(pattern))) return SOURCE_TYPES.demo;
  if (LOCAL_SAVED_PATTERNS.some((pattern) => sourceText.includes(pattern))) return SOURCE_TYPES.localSaved;
  return SOURCE_TYPES.localSaved;
}

export function getCoreApiCapability(platform, feature) {
  const normalizedPlatform = normalizePlatform(platform);
  return CORE_API_CAPABILITY_MATRIX.find((item) => (
    item.feature === feature
    && (item.platform === normalizedPlatform || item.platform === 'all')
  )) || {
    platform: normalizedPlatform,
    feature,
    category: 'B',
    apiDirection: '本地',
    currentPhase: '本地辅助功能',
    permission: '未确认官方接口',
    risk: '不能宣称已操作平台',
    humanConfirm: true,
    label: feature,
  };
}

export function getDangerousActionState(actionKey) {
  void actionKey;
  return {
    enabled: false,
    label: '暂未开放',
    note: '平台写入动作本阶段保持关闭，必须单独审批后才能开启。',
  };
}

export function sourceLabelForRecord(record = {}) {
  return classifyCoreDataSource(record).label;
}
