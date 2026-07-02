const STATUS_LABELS = {
  tested_success: '已通过',
  tested_failed: '需要检查',
  not_tested: '暂未检测',
  planned: '计划中',
  unavailable: '暂不可用',
  permission_required: '需要平台权限',
  docs_pending: '等待确认',
  credential_not_ready: '连接资料未配齐',
  auth_failed: '授权失败',
  token_auth_failed: '平台授权失败',
  readonly_request_failed: '读取失败',
  ip_not_allowed: '服务器 IP 受限',
  guardrail_blocked: '保护中',
  success_empty: '已连接，暂无新数据',
  preview_success: '预览已完成',
};

const CAPABILITY_LABELS = {
  'naver.token_auth': '平台授权',
  'naver.seller_account_read': '卖家账号',
  'naver.seller_channels_read': '店铺连接',
  'naver.product_read': '商品读取',
  'naver.order_read': '订单读取',
  'naver.order_detail_preview': '订单详情',
  'naver.sales_read': '销售额读取',
  'naver.settlement_read': '结算读取',
  'naver.customer_inquiry_read': '客户咨询',
  'naver.shipping_delivery_read': '发货配送',
  'coupang.auth_read': '平台连接',
  'coupang.product_read': '商品管理',
  'coupang.order_read': '订单管理',
  'coupang.sales_read': '销售额',
  'coupang.settlement_read': '结算',
  'coupang.cs_read': '客服咨询',
};

const NaverProtectedMessage = '当前仍处于保护阶段：主页面只展示业务状态，正式批量同步需要单独确认后才会开放。';

const NAVER_PRODUCT_SMALL_BATCH_SUMMARY = {
  localSyncedCount: 5,
  createdInLocalSync: 4,
  updatedInLocalSync: 1,
  matchedExistingCount: 5,
  wouldCreate: 0,
  wouldUpdate: 0,
  wouldRefreshOnly: 5,
  wouldSkip: 0,
  storeId: 8,
  credentialId: 7,
};

const NAVER_PRODUCT_PREVIEW_STATUS = {
  statusLabel: '暂无',
  reason: 'Naver 已完成 5 条商品小批量写入测试。再次预览时没有发现需要新增或更新的商品，仅同步时间需要刷新。正式批量同步仍未开放。',
  nextAction: '当前 5 条本地商品状态稳定；如需继续扩大范围，必须先单独确认。',
};

const NAVER_PRODUCT_LOCAL_SYNC_STATUS = {
  statusLabel: '已完成',
  reason: '本地已写入 5 条 Naver 商品，其中新增 4 条、更新 1 条，本次未保存平台原始响应。',
  nextAction: '当前只完成最多 5 条的小批量写入测试，不会自动扩大为正式批量同步。',
};

const NAVER_PRODUCT_BATCH_SYNC_STATUS = {
  statusLabel: '未开放',
  reason: '正式批量同步未开放。当前仅完成最多 5 条商品的小批量写入测试，不代表商品同步已全面可用。',
  nextAction: '如需继续扩大范围，必须再次人工确认。',
};

const NAVER_ORDER_PREVIEW_STATUS = {
  statusLabel: '接口已连接',
  reason: 'Naver 订单接口已连接。当前时间范围内没有新的订单变更，暂时不需要处理订单同步。',
  nextAction: '出现新订单变更后，再检测订单详情并确认后续同步策略。',
};

const NAVER_ORDER_DETAIL_STATUS = {
  statusLabel: '等待新订单后检测',
  reason: '当前没有新的订单变更，因此暂时没有需要查看的订单详情。',
  nextAction: '等店铺出现新订单后，再查看单条订单详情预览。',
};

const NAVER_SYNC_PROTECTION_STATUS = {
  statusLabel: '正式批量同步未开放',
  reason: '当前不会批量写入商品或订单，也不会保存平台原始响应。',
  nextAction: '批量同步必须单独确认后才会执行。',
};

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function labelForStatus(status, errorCode) {
  if (errorCode && STATUS_LABELS[errorCode]) return STATUS_LABELS[errorCode];
  return STATUS_LABELS[status] || status || '暂未检测';
}

function toneForStatus(status, errorCode) {
  if (errorCode || status === 'tested_failed') return 'danger';
  if (status === 'tested_success' || status === 'preview_success' || status === 'success_empty') return 'success';
  if (status === 'permission_required' || status === 'guardrail_blocked') return 'warning';
  if (status === 'not_tested' || status === 'planned') return 'muted';
  return 'info';
}

export function parseObservedFields(text = '') {
  return String(text || '')
    .split(';')
    .map((item) => item.trim())
    .filter(Boolean)
    .reduce((acc, item) => {
      const [key, ...rest] = item.split('=');
      if (key && rest.length) acc[key.trim()] = rest.join('=').trim();
      return acc;
    }, {});
}

function latestResultForKey(results = [], capabilities = [], capabilityKey) {
  const scopeAliases = {
    'naver.token_auth': 'token_auth',
    'naver.seller_account_read': 'seller_account',
    'naver.seller_channels_read': 'seller_channels',
  };
  const expectedScope = scopeAliases[capabilityKey];
  const capabilityIds = new Set(
    capabilities
      .filter((item) => item.capabilityKey === capabilityKey)
      .map((item) => String(item.id)),
  );
  const matches = results.filter((item) => (
    item.capabilityKey === capabilityKey
    || capabilityIds.has(String(item.capabilityId))
    || (expectedScope && parseObservedFields(item.responseFieldsObserved || '').capability_scope === expectedScope)
  ));
  return matches.sort((a, b) => new Date(b.testedAt || b.createdAt || 0) - new Date(a.testedAt || a.createdAt || 0))[0] || null;
}

function resultCard({
  key,
  title,
  status,
  statusLabel,
  errorCode,
  reason,
  nextAction,
  details,
  tone,
}) {
  return {
    key,
    title: title || CAPABILITY_LABELS[key] || key,
    status,
    statusLabel: statusLabel || labelForStatus(status, errorCode),
    tone: tone || toneForStatus(status, errorCode),
    reason,
    nextAction,
    details,
  };
}

function cardFromResult(key, result, successReason, successNextAction, fallback = {}) {
  const status = result?.testStatus || fallback.status || 'not_tested';
  const errorCode = result?.errorCode || fallback.errorCode || null;
  if (status === 'tested_success') {
    return resultCard({
      key,
      status,
      errorCode,
      reason: successReason,
      nextAction: successNextAction,
      details: result,
    });
  }
  if (errorCode === 'auth_failed' || errorCode === 'token_auth_failed') {
    return resultCard({
      key,
      status,
      errorCode,
      reason: '平台授权失败，请检查连接资料和平台权限。',
      nextAction: '请到平台连接资料页面核对 Client ID、Secret 或权限配置。',
      details: result,
    });
  }
  if (errorCode === 'credential_not_ready') {
    return resultCard({
      key,
      status,
      errorCode,
      reason: '平台连接资料还没有配齐。',
      nextAction: '请先补齐当前店铺的平台连接资料。',
      details: result,
    });
  }
  return resultCard({
    key,
    status,
    errorCode,
    reason: fallback.reason || '当前还没有完成这项业务能力确认。',
    nextAction: fallback.nextAction || '请按阶段继续完成连接资料和只读预览确认。',
    details: result,
  });
}

function buildNaverCards({ capabilities, results, readiness }) {
  const storeReadiness = readiness?.storeBoundReadiness || {};
  const token = latestResultForKey(results, capabilities, 'naver.token_auth');
  const sellerAccount = latestResultForKey(results, capabilities, 'naver.seller_account_read');
  const sellerChannels = latestResultForKey(results, capabilities, 'naver.seller_channels_read');
  const channelObserved = parseObservedFields(sellerChannels?.responseFieldsObserved || '');
  const channelConfigured = Boolean(storeReadiness.channelNoConfigured)
    || channelObserved.channel_no_configured === 'True'
    || channelObserved.channel_no_persisted === 'True';

  return [
    cardFromResult(
      'naver.token_auth',
      token,
      '平台授权正常，可以继续读取卖家账号和店铺连接状态。',
      '下一步请确认商品、订单预览状态。',
    ),
    cardFromResult(
      'naver.seller_account_read',
      sellerAccount,
      '卖家账号信息读取正常。',
      '可继续确认店铺频道和商品订单读取状态。',
    ),
    cardFromResult(
      'naver.seller_channels_read',
      sellerChannels,
      '店铺连接成功，系统已识别店铺频道状态。',
      channelConfigured ? '店铺连接资料已准备好，页面不会显示完整频道编号。' : '请先完成店铺频道识别。',
    ),
    resultCard({
      key: 'naver.product_read',
      title: '商品业务字段变化',
      status: 'success_empty',
      statusLabel: NAVER_PRODUCT_PREVIEW_STATUS.statusLabel,
      tone: 'success',
      reason: NAVER_PRODUCT_PREVIEW_STATUS.reason,
      nextAction: NAVER_PRODUCT_PREVIEW_STATUS.nextAction,
    }),
    resultCard({
      key: 'naver.product_local_sync',
      title: '商品小批量写入测试',
      status: 'preview_success',
      statusLabel: NAVER_PRODUCT_LOCAL_SYNC_STATUS.statusLabel,
      tone: 'success',
      reason: NAVER_PRODUCT_LOCAL_SYNC_STATUS.reason,
      nextAction: NAVER_PRODUCT_LOCAL_SYNC_STATUS.nextAction,
    }),
    resultCard({
      key: 'naver.product_batch_sync',
      title: '批量同步',
      status: 'guardrail_blocked',
      statusLabel: NAVER_PRODUCT_BATCH_SYNC_STATUS.statusLabel,
      tone: 'warning',
      reason: NAVER_PRODUCT_BATCH_SYNC_STATUS.reason,
      nextAction: NAVER_PRODUCT_BATCH_SYNC_STATUS.nextAction,
    }),
    resultCard({
      key: 'naver.order_read',
      status: 'success_empty',
      statusLabel: NAVER_ORDER_PREVIEW_STATUS.statusLabel,
      tone: 'success',
      reason: NAVER_ORDER_PREVIEW_STATUS.reason,
      nextAction: NAVER_ORDER_PREVIEW_STATUS.nextAction,
    }),
    resultCard({
      key: 'naver.order_detail_preview',
      status: 'not_tested',
      statusLabel: NAVER_ORDER_DETAIL_STATUS.statusLabel,
      tone: 'muted',
      reason: NAVER_ORDER_DETAIL_STATUS.reason,
      nextAction: NAVER_ORDER_DETAIL_STATUS.nextAction,
    }),
    resultCard({
      key: 'naver.sync_protection',
      title: '同步保护',
      status: 'guardrail_blocked',
      statusLabel: NAVER_SYNC_PROTECTION_STATUS.statusLabel,
      tone: 'warning',
      reason: NAVER_SYNC_PROTECTION_STATUS.reason,
      nextAction: NAVER_SYNC_PROTECTION_STATUS.nextAction,
    }),
  ];
}

function buildCoupangCards({ financialSummary }) {
  const salesRows = financialSummary?.platformSalesDetailSummary?.salesDetailRows ?? 0;
  const settlementRows = financialSummary?.settlementSummary?.settlementRows ?? 0;
  return [
    resultCard({
      key: 'coupang.auth_read',
      status: 'tested_success',
      reason: 'Coupang 店铺连接正常。',
      nextAction: '可在商品、订单、销售额页面继续核对业务数据。',
    }),
    resultCard({
      key: 'coupang.product_read',
      status: 'tested_success',
      statusLabel: '可使用',
      reason: '商品读取和本地同步入口可用。',
      nextAction: '请在商品页按状态核对商品和库存。',
    }),
    resultCard({
      key: 'coupang.order_read',
      status: 'tested_success',
      statusLabel: '可使用',
      reason: '订单读取和本地同步入口可用。',
      nextAction: '请在订单页核对待发货和异常订单。',
    }),
    resultCard({
      key: 'coupang.sales_read',
      status: 'tested_success',
      statusLabel: salesRows > 0 ? '可查询' : '可查询，暂无本地明细',
      reason: salesRows > 0 ? '销售明细已有本地数据。' : '销售明细查询链路可用，当前本地暂无明细。',
      nextAction: '请在销售额页面查看销售和结算口径。',
    }),
    resultCard({
      key: 'coupang.settlement_read',
      status: 'tested_success',
      statusLabel: settlementRows > 0 ? '已有结算数据' : '可查询，暂无本地结算',
      reason: settlementRows > 0 ? `本地已有 ${settlementRows} 条结算明细。` : '结算明细查询链路可用。',
      nextAction: '结算金额不等同于利润或可提现余额，请按页面说明核对。',
    }),
  ];
}

export function buildPlatformBusinessStatus({
  platform,
  capabilities = [],
  results = [],
  readiness = null,
  financialSummary = null,
}) {
  const normalized = normalizePlatform(platform);
  if (normalized === 'naver') return buildNaverCards({ capabilities, results, readiness });
  if (normalized === 'coupang') return buildCoupangCards({ financialSummary });
  return [];
}

export function businessCapabilityTitle(platform) {
  const normalized = normalizePlatform(platform);
  if (normalized === 'naver') return 'Naver 店铺连接状态';
  if (normalized === 'coupang') return 'Coupang 店铺连接状态';
  return '平台连接状态';
}

export function statusLabel(value, errorCode) {
  return labelForStatus(value, errorCode);
}

export function getNaverProductPreviewStatus() {
  return {
    productRead: NAVER_PRODUCT_PREVIEW_STATUS,
    localSync: NAVER_PRODUCT_LOCAL_SYNC_STATUS,
    batchSync: NAVER_PRODUCT_BATCH_SYNC_STATUS,
    summary: NAVER_PRODUCT_SMALL_BATCH_SUMMARY,
  };
}

export function getNaverOrderPreviewStatus() {
  return {
    feed: NAVER_ORDER_PREVIEW_STATUS,
    detail: NAVER_ORDER_DETAIL_STATUS,
    sync: NAVER_SYNC_PROTECTION_STATUS,
  };
}

export { CAPABILITY_LABELS, NaverProtectedMessage };
