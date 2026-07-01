const STATUS_LABELS = {
  tested_success: '已通过检测',
  tested_failed: '检测失败',
  not_tested: '暂未检测',
  planned: '计划中',
  unavailable: '暂不可用',
  permission_required: '需要平台权限',
  docs_pending: '接口文档确认中 / 暂未开放真实测试',
  credential_not_ready: '凭证未配置完整',
  auth_failed: '授权失败，请检查 API 凭证或权限',
  token_auth_failed: '平台授权失败',
  readonly_request_failed: '只读请求失败',
  ip_not_allowed: '平台 IP 白名单限制',
};

const CAPABILITY_LABELS = {
  'naver.token_auth': '平台授权检测',
  'naver.seller_account_read': '卖家账号信息读取',
  'naver.seller_channels_read': '店铺频道信息读取',
  'naver.product_read': '商品读取',
  'naver.order_read': '订单读取',
  'naver.sales_read': '销售读取',
  'naver.settlement_read': '结算读取',
  'naver.customer_inquiry_read': '客户咨询读取',
  'naver.shipping_delivery_read': '配送读取',
  'coupang.auth_read': '平台连接',
  'coupang.product_read': '商品读取/同步',
  'coupang.order_read': '订单读取/同步',
  'coupang.sales_read': '销售明细',
  'coupang.settlement_read': '结算明细',
  'coupang.cs_read': 'CS/咨询读取',
};

const NaverProtectedMessage = '为避免误触真实业务数据，商品/订单接口当前仍处于保护状态，暂未开放真实请求。';

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function labelForStatus(status, errorCode) {
  if (errorCode && STATUS_LABELS[errorCode]) return STATUS_LABELS[errorCode];
  return STATUS_LABELS[status] || status || '暂未检测';
}

function toneForStatus(status, errorCode) {
  if (errorCode || status === 'tested_failed') return 'danger';
  if (status === 'tested_success') return 'success';
  if (status === 'permission_required') return 'warning';
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
  key, title, status, statusLabel, errorCode, reason, nextAction, details,
}) {
  return {
    key,
    title: title || CAPABILITY_LABELS[key] || key,
    status,
    statusLabel: statusLabel || labelForStatus(status, errorCode),
    tone: toneForStatus(status, errorCode),
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
      reason: '授权失败，请检查 API 凭证或平台权限。',
      nextAction: '请核对 Client ID / Client Secret，或确认 Naver Commerce API Center 权限。',
      details: result,
    });
  }
  if (errorCode === 'credential_not_ready') {
    return resultCard({
      key,
      status,
      errorCode,
      reason: '凭证未配置完整。',
      nextAction: '请先在 API 凭证管理页补齐必填配置。',
      details: result,
    });
  }
  return resultCard({
    key,
    status,
    errorCode,
    reason: fallback.reason || '当前还没有完成真实只读检测。',
    nextAction: fallback.nextAction || '请先完成前置凭证配置，再按阶段开放真实只读检测。',
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
      '平台授权检测已通过，可以继续进行账号与频道读取检测。',
      '下一步可查看卖家账号与店铺频道读取状态。',
    ),
    cardFromResult(
      'naver.seller_account_read',
      sellerAccount,
      '卖家账号信息读取成功，系统已确认该 Naver 凭证可用于账号级只读检测。',
      '可继续确认店铺频道信息，作为后续商品/订单同步前置条件。',
    ),
    cardFromResult(
      'naver.seller_channels_read',
      sellerChannels,
      '店铺频道信息读取成功，系统已确认该 Naver 凭证可读取频道信息。',
      channelConfigured ? '频道编号已识别，可进入商品/订单前置设计。' : '请继续识别或补充店铺频道编号。',
    ),
    resultCard({
      key: 'naver.channel_no',
      title: '店铺频道编号',
      status: channelConfigured ? 'tested_success' : 'not_tested',
      statusLabel: channelConfigured ? '已识别' : '暂未识别',
      tone: channelConfigured ? 'success' : 'warning',
      reason: channelConfigured
        ? '已识别店铺频道编号。'
        : '暂未识别到店铺频道编号，后续商品/订单同步可能需要补充。',
      nextAction: channelConfigured
        ? '后续商品/订单读取设计可以使用该前置状态。'
        : '请先完成 seller/channels 只读识别，或由运营人员确认 channel_no。',
    }),
    resultCard({
      key: 'naver.product_read',
      status: 'not_tested',
      statusLabel: '暂未开放真实测试',
      tone: 'muted',
      reason: NaverProtectedMessage,
      nextAction: '需等待后端完成 Naver 商品接口前置设计。',
    }),
    resultCard({
      key: 'naver.order_read',
      status: 'not_tested',
      statusLabel: '暂未开放真实测试',
      tone: 'muted',
      reason: NaverProtectedMessage,
      nextAction: '需等待后端完成 Naver 订单接口前置设计。',
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
      reason: '平台连接已通过检测，当前 Coupang 真实只读链路已完成阶段验收。',
      nextAction: '可继续通过商品、订单、销售与结算页面查看本地同步结果。',
    }),
    resultCard({
      key: 'coupang.product_read',
      status: 'tested_success',
      statusLabel: '可用',
      reason: '商品读取/同步入口可用，当前本地 products 已按 Coupang 状态同步。',
      nextAction: '可在商品页按 APPROVED / DELETED 等状态核对。',
    }),
    resultCard({
      key: 'coupang.order_read',
      status: 'tested_success',
      statusLabel: '可用',
      reason: '订单读取/同步入口可用。',
      nextAction: '可在订单页核对当前查询窗口内是否有订单。',
    }),
    resultCard({
      key: 'coupang.sales_read',
      status: 'tested_success',
      statusLabel: salesRows > 0 ? '可查询' : '可查询，本地暂无明细数据',
      reason: salesRows > 0 ? '销售明细已有本地持久化数据。' : '销售明细链路可查询，当前本地暂无明细数据。',
      nextAction: '等真实 sales 有非 0 样本后再做抽检，不要与结算金额混算。',
    }),
    resultCard({
      key: 'coupang.settlement_read',
      status: 'tested_success',
      statusLabel: settlementRows > 0 ? '可用，已有本地结算数据' : '可用，暂无本地结算数据',
      reason: settlementRows > 0 ? `结算明细已有 ${settlementRows} 行本地数据。` : '结算明细链路可用。',
      nextAction: '结算金额按结算口径展示，不等同于销售额或利润。',
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
  if (normalized === 'naver') return 'Naver SmartStore 能力状态';
  if (normalized === 'coupang') return 'Coupang 能力状态';
  return '平台能力状态';
}

export function statusLabel(value, errorCode) {
  return labelForStatus(value, errorCode);
}

export { CAPABILITY_LABELS, NaverProtectedMessage };
