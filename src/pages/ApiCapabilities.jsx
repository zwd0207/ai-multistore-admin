import { useEffect, useMemo, useState } from 'react';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { formatKstDateTimeWithLabel } from '../utils/time';

const emptyReadiness = {
  semanticNotice: 'mock 模式只展示页面状态，不维护后端连接检测记录。',
  platforms: [],
  storeBoundReadiness: null,
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
  'coupang.auth_read': '平台连接',
  'coupang.product_read': '商品管理',
  'coupang.order_read': '订单管理',
  'coupang.sales_read': '销售额',
  'coupang.settlement_read': '结算',
};

const STATUS_LABELS = {
  tested_success: '已通过',
  tested_failed: '需要检查',
  not_tested: '暂未确认',
  planned: '计划中',
  unavailable: '暂不可用',
  permission_required: '需要平台权限',
  docs_pending: '等待确认',
  guardrail_blocked: '保护中',
  success_empty: '已连接，暂无新数据',
  preview_success: '预览已完成',
};

const NAVER_ERROR_PRESENTATIONS = {
  ip_not_allowed: {
    title: 'Naver API 请求 IP 未被允许。',
    description: '请在 Naver Commerce API Center 检查 API 使用 IP / 允许 IP 设置，确认当前服务器公网 IP 已加入允许列表。',
    statusLabel: '需要处理',
    tone: 'danger',
  },
  credential_invalid: {
    title: 'Naver 连接资料可能无效。',
    description: '请检查 Client ID / Client Secret 是否正确，或是否被重新生成。',
    statusLabel: '需要处理',
    tone: 'danger',
  },
  permission_forbidden: {
    title: 'Naver API 权限不足。',
    description: '请检查该应用是否已开通对应接口权限。',
    statusLabel: '需要处理',
    tone: 'danger',
  },
  product_api_not_allowed: {
    title: 'Naver 商品接口暂无权限或未开放。',
    description: '请检查 Naver Commerce API Center 中商品 API 的使用权限。',
    statusLabel: '需要处理',
    tone: 'danger',
  },
  token_auth_failed: {
    title: 'Naver 授权失败。',
    description: '请检查连接资料、平台权限或 Naver API 设置。',
    statusLabel: '需要处理',
    tone: 'danger',
  },
  unknown_forbidden: {
    title: 'Naver 请求被拒绝。',
    description: '系统无法确认具体原因，请检查 Naver API 权限、允许 IP 和连接资料。',
    statusLabel: '需要处理',
    tone: 'danger',
  },
  auth_failed: {
    title: 'Naver 授权失败。',
    description: '请检查连接资料、平台权限或 Naver API 设置。',
    statusLabel: '需要处理',
    tone: 'danger',
  },
};

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function parseObservedFields(text = '') {
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

function normalizeErrorCode(value) {
  const normalized = String(value || '').trim();
  if (!normalized || normalized.toLowerCase() === 'none') return null;
  return normalized;
}

function latestResultForKey(results = [], capabilities = [], capabilityKey) {
  const scopeAliases = {
    'naver.token_auth': 'token_auth',
    'naver.seller_account_read': 'seller_account',
    'naver.seller_channels_read': 'seller_channels',
    'naver.product_read': 'product_read',
    'naver.order_read': 'order_read',
    'naver.order_detail_preview': 'order_detail_preview',
  };
  const expectedScope = scopeAliases[capabilityKey];
  const capabilityIds = new Set(
    capabilities
      .filter((item) => item.capabilityKey === capabilityKey)
      .map((item) => String(item.id)),
  );
  const matches = results.filter((item) => {
    const observed = parseObservedFields(item.responseFieldsObserved || '');
    return item.capabilityKey === capabilityKey
      || capabilityIds.has(String(item.capabilityId))
      || (expectedScope && observed.capability_scope === expectedScope);
  });
  return matches.sort((a, b) => new Date(b.testedAt || b.createdAt || 0) - new Date(a.testedAt || a.createdAt || 0))[0] || null;
}

function issueFromResult(result = null) {
  if (!result) return null;
  const observed = parseObservedFields(result.responseFieldsObserved || '');
  const errorCode = normalizeErrorCode(result.errorCode || observed.error_code);
  if (!errorCode) return null;
  const presentation = NAVER_ERROR_PRESENTATIONS[errorCode] || {
    title: 'Naver 请求需要检查。',
    description: result.businessErrorHint || '请检查连接资料、平台权限、允许 IP 和当前店铺连接状态。',
    statusLabel: '需要检查',
    tone: 'warning',
  };
  return {
    ...presentation,
    errorCode,
    httpStatus: result.httpStatus || observed.http_status || '-',
    businessErrorHint: result.businessErrorHint || observed.business_error_hint || '-',
    safeKeywordFlags: result.safeKeywordFlags || observed.safe_keyword_flags || '-',
    capabilityScope: result.capabilityScope || observed.capability_scope || '-',
    pathKind: result.pathKind || observed.path_kind || '-',
    result,
  };
}

function findLatestIssue({ capabilities = [], results = [], capabilityKeys = [] } = {}) {
  return capabilityKeys
    .map((key) => {
      const result = latestResultForKey(results, capabilities, key);
      const issue = issueFromResult(result);
      if (!issue) return null;
      return { ...issue, capabilityKey: key, testedAt: result?.testedAt || result?.createdAt || null };
    })
    .filter(Boolean)
    .sort((left, right) => Date.parse(right.testedAt || 0) - Date.parse(left.testedAt || 0))[0] || null;
}

function statusLabel(value, errorCode) {
  const normalizedError = normalizeErrorCode(errorCode);
  if (normalizedError && NAVER_ERROR_PRESENTATIONS[normalizedError]) return NAVER_ERROR_PRESENTATIONS[normalizedError].statusLabel;
  return STATUS_LABELS[value] || value || '暂未确认';
}

function businessCapabilityTitle(platform) {
  const normalized = normalizePlatform(platform);
  if (normalized === 'naver') return 'Naver 店铺连接状态';
  if (normalized === 'coupang') return 'Coupang 店铺连接状态';
  return '平台连接状态';
}

function resultCard({
  key,
  title,
  statusLabel: nextStatusLabel,
  tone = 'info',
  reason,
  nextAction,
  technical = {},
}) {
  return {
    key,
    title: title || CAPABILITY_LABELS[key] || key,
    statusLabel: nextStatusLabel,
    tone,
    reason,
    nextAction,
    technical,
  };
}

function errorCard(key, title, issue) {
  return resultCard({
    key,
    title,
    statusLabel: issue.statusLabel,
    tone: issue.tone,
    reason: issue.title,
    nextAction: issue.description,
    technical: {
      error_code: issue.errorCode,
      http_status: issue.httpStatus,
      business_error_hint: issue.businessErrorHint,
      safe_keyword_flags: issue.safeKeywordFlags,
      capability_scope: issue.capabilityScope,
      path_kind: issue.pathKind,
    },
  });
}

function successOrPendingCard({
  key,
  title,
  result,
  successReason,
  successNextAction,
  pendingReason,
  pendingNextAction,
}) {
  const issue = issueFromResult(result);
  if (issue) return errorCard(key, title, issue);
  if (result?.testStatus === 'tested_success') {
    return resultCard({
      key,
      title,
      statusLabel: '正常',
      tone: 'success',
      reason: successReason,
      nextAction: successNextAction,
      technical: {
        test_status: result.testStatus,
        http_status: result.httpStatus,
        tested_at: result.testedAt,
      },
    });
  }
  return resultCard({
    key,
    title,
    statusLabel: '待确认',
    tone: 'muted',
    reason: pendingReason,
    nextAction: pendingNextAction,
    technical: {
      test_status: result?.testStatus || 'not_tested',
      tested_at: result?.testedAt || '-',
    },
  });
}

function buildNaverCards({ capabilities, results, readiness }) {
  const token = latestResultForKey(results, capabilities, 'naver.token_auth');
  const sellerAccount = latestResultForKey(results, capabilities, 'naver.seller_account_read');
  const sellerChannels = latestResultForKey(results, capabilities, 'naver.seller_channels_read');
  const productIssue = findLatestIssue({
    capabilities,
    results,
    capabilityKeys: ['naver.product_read', 'naver.token_auth', 'naver.seller_channels_read', 'naver.seller_account_read'],
  });
  const orderIssue = findLatestIssue({
    capabilities,
    results,
    capabilityKeys: ['naver.order_read', 'naver.token_auth', 'naver.seller_channels_read', 'naver.seller_account_read'],
  });
  const channelReady = Boolean(readiness?.storeBoundReadiness?.channelNoConfigured);

  return [
    successOrPendingCard({
      key: 'naver.token_auth',
      title: '平台授权',
      result: token,
      successReason: 'Naver 授权可用，可以继续读取卖家账号和店铺连接状态。',
      successNextAction: '后续商品、订单读取仍按阶段单独确认。',
      pendingReason: '当前还没有完成授权确认。',
      pendingNextAction: '请先确认连接资料和平台权限。',
    }),
    successOrPendingCard({
      key: 'naver.seller_account_read',
      title: '卖家账号',
      result: sellerAccount,
      successReason: '卖家账号信息读取正常。',
      successNextAction: '可继续确认店铺连接、商品和订单状态。',
      pendingReason: '卖家账号读取状态还未确认。',
      pendingNextAction: '请先完成平台授权和账号读取确认。',
    }),
    successOrPendingCard({
      key: 'naver.seller_channels_read',
      title: '店铺连接',
      result: sellerChannels,
      successReason: channelReady ? '店铺连接已识别，页面不会展示完整频道编号。' : '店铺读取可用，但频道配置仍需管理员确认。',
      successNextAction: '店铺连接正常后，继续按商品和订单阶段推进。',
      pendingReason: '店铺连接状态还未确认。',
      pendingNextAction: '请先完成店铺连接识别。',
    }),
    productIssue
      ? errorCard('naver.product_read', '商品读取', productIssue)
      : resultCard({
        key: 'naver.product_read',
        title: '商品读取',
        statusLabel: '状态稳定',
        tone: 'success',
        reason: '当前本地已有 5 条 Naver 商品，暂无新增或业务字段更新，仅同步时间需要刷新。',
        nextAction: '正式商品批量同步仍未开放。',
      }),
    orderIssue
      ? errorCard('naver.order_read', '订单读取', orderIssue)
      : resultCard({
        key: 'naver.order_read',
        title: '订单读取',
        statusLabel: '已接入',
        tone: 'success',
        reason: '本地已有 Naver 运营订单，可用于订单、履约和售后状态展示。',
        nextAction: '正式订单批量同步仍未开放。',
      }),
    resultCard({
      key: 'naver.sync_protection',
      title: '正式批量同步',
      statusLabel: '未开放',
      tone: 'warning',
      reason: '商品或订单批量同步必须单独确认，不会因为连接成功而自动开放。',
      nextAction: '需要写入或扩大范围时，必须另开阶段并保留备份、审核和回读校验。',
    }),
  ];
}

function buildCoupangCards({ financialSummary }) {
  const salesRows = financialSummary?.platformSalesDetailSummary?.salesDetailRows ?? 0;
  const settlementRows = financialSummary?.settlementSummary?.settlementRows ?? 0;
  return [
    resultCard({
      key: 'coupang.auth_read',
      title: '平台连接',
      statusLabel: '正常',
      tone: 'success',
      reason: 'Coupang 店铺连接资料可用于业务页面。',
      nextAction: '请在商品、订单、销售额页面继续核对业务数据。',
    }),
    resultCard({
      key: 'coupang.product_read',
      title: '商品管理',
      statusLabel: '可查看',
      tone: 'success',
      reason: '商品读取和本地同步入口可用。',
      nextAction: '请在商品页按状态核对商品和库存。',
    }),
    resultCard({
      key: 'coupang.order_read',
      title: '订单管理',
      statusLabel: '可查看',
      tone: 'success',
      reason: '订单读取和本地同步入口可用。',
      nextAction: '请在订单页核对待发货和异常订单。',
    }),
    resultCard({
      key: 'coupang.sales_read',
      title: '销售额',
      statusLabel: salesRows > 0 ? '已有数据' : '待接入明细',
      tone: salesRows > 0 ? 'success' : 'muted',
      reason: salesRows > 0 ? '本地已有销售明细。' : '当前本地暂无销售明细。',
      nextAction: '请在销售额页面查看销售与结算口径。',
    }),
    resultCard({
      key: 'coupang.settlement_read',
      title: '结算',
      statusLabel: settlementRows > 0 ? '已有数据' : '待接入明细',
      tone: settlementRows > 0 ? 'success' : 'muted',
      reason: settlementRows > 0 ? `本地已有 ${settlementRows} 条结算明细。` : '当前本地暂无结算明细。',
      nextAction: '结算金额不等同于利润或账户可提取资金。',
    }),
  ];
}

function buildPlatformBusinessStatus({ platform, capabilities, results, readiness }) {
  const normalized = normalizePlatform(platform);
  if (normalized === 'naver') return buildNaverCards({ capabilities, results, readiness });
  if (normalized === 'coupang') return buildCoupangCards({});
  return [];
}

function BusinessCards({ cards }) {
  if (!cards.length) {
    return <EmptyState title="暂无平台连接状态" description="请选择 Naver 或 Coupang 店铺后查看连接状态。" />;
  }
  return (
    <div className="business-capability-grid">
      {cards.map((card) => (
        <article className={`business-capability-card ${card.tone || 'info'}`} key={card.key}>
          <div className="business-capability-head">
            <strong>{card.title}</strong>
            <span>{card.statusLabel}</span>
          </div>
          <p>{card.reason}</p>
          <small>{card.nextAction}</small>
        </article>
      ))}
    </div>
  );
}

function CapabilityTechnicalTable({ capabilities = [] }) {
  if (!capabilities.length) return null;
  return (
    <TechnicalDetails title="查看平台能力定义" description="这里保留接口路径、方法和文档记录，仅供管理员维护。">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>平台</th>
              <th>业务能力</th>
              <th>状态</th>
              <th>方法</th>
              <th>路径</th>
              <th>最近确认</th>
            </tr>
          </thead>
          <tbody>
            {capabilities.map((item) => (
              <tr key={item.id}>
                <td>{item.platform}</td>
                <td><strong>{CAPABILITY_LABELS[item.capabilityKey] || item.capabilityName}</strong><small className="cell-subtitle">{item.capabilityKey}</small></td>
                <td>{statusLabel(item.testStatus)}</td>
                <td>{item.method || '-'}</td>
                <td>{item.endpointPath || '-'}</td>
                <td>{formatKstDateTimeWithLabel(item.lastCheckedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TechnicalDetails>
  );
}

function ResultTechnicalTable({ results = [] }) {
  if (!results.length) return null;
  return (
    <TechnicalDetails title="查看店铺检测记录" description="技术检测记录默认折叠，不作为普通卖家的主判断依据。">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业务能力</th>
              <th>状态</th>
              <th>错误码</th>
              <th>HTTP</th>
              <th>记录时间</th>
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <tr key={item.id}>
                <td>{CAPABILITY_LABELS[item.capabilityKey] || item.capabilityLabel || `Capability #${item.capabilityId}`}</td>
                <td>{statusLabel(item.testStatus, item.errorCode)}</td>
                <td>{item.errorCode || '-'}</td>
                <td>{item.httpStatus || '-'}</td>
                <td>{formatKstDateTimeWithLabel(item.testedAt || item.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TechnicalDetails>
  );
}

function ReadinessSummary({ readiness, capabilities, results, currentStore }) {
  const storeBound = readiness?.storeBoundReadiness;
  const platform = normalizePlatform(storeBound?.rawPlatform || storeBound?.platform || currentStore?.rawPlatform || currentStore?.platform);
  const isNaver = platform === 'naver';
  const title = isNaver ? 'Naver 连接资料' : platform === 'coupang' ? 'Coupang 连接资料' : '平台连接资料';
  const configured = Boolean(storeBound?.configured);
  const channelReady = Boolean(storeBound?.channelNoConfigured);
  const connectionIssue = isNaver
    ? findLatestIssue({
      capabilities,
      results,
      capabilityKeys: ['naver.token_auth', 'naver.seller_channels_read', 'naver.seller_account_read'],
    })
    : null;
  const authTone = connectionIssue ? connectionIssue.tone : configured ? 'success' : 'warning';
  const authStatus = connectionIssue ? connectionIssue.statusLabel : configured ? '可使用' : '待配置';
  const authReason = connectionIssue ? connectionIssue.title : '平台连接资料已保存，敏感内容不会在页面明文展示。';
  const authNextAction = connectionIssue ? connectionIssue.description : '需要修改密钥或重新检测时，请走管理员受控流程。';
  const channelTone = connectionIssue ? 'warning' : isNaver && channelReady ? 'success' : 'info';
  const channelStatus = connectionIssue ? '待确认' : isNaver ? (channelReady ? '已识别' : '待确认') : '可使用';
  const channelReason = connectionIssue
    ? '当前连接问题处理前，暂不判断店铺频道状态。'
    : isNaver
      ? 'Naver 店铺频道只显示是否识别，不展示完整编号。'
      : 'Coupang 店铺连接资料已进入业务页面使用。';

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>{title}</h2>
          <p>默认只展示连接是否可用，不显示密钥、Token、请求头或完整店铺频道编号。</p>
        </div>
      </div>
      <div className="business-capability-grid compact">
        <article className={`business-capability-card ${configured ? 'success' : 'warning'}`}>
          <div className="business-capability-head">
            <strong>{title}</strong>
            <span>{configured ? '已配置' : '待配置'}</span>
          </div>
          <p>{configured ? '平台连接资料已配置。' : '请先补齐平台连接资料。'}</p>
        </article>
        <article className={`business-capability-card ${authTone}`}>
          <div className="business-capability-head">
            <strong>授权与权限</strong>
            <span>{authStatus}</span>
          </div>
          <p>{authReason}</p>
          <small>{authNextAction}</small>
        </article>
        <article className={`business-capability-card ${channelTone}`}>
          <div className="business-capability-head">
            <strong>店铺连接</strong>
            <span>{channelStatus}</span>
          </div>
          <p>{channelReason}</p>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>正式批量同步</strong>
            <span>未开放</span>
          </div>
          <p>商品或订单批量同步必须单独确认，不会因为连接成功而自动开放。</p>
        </article>
      </div>
      <TechnicalDetails
        items={[
          { label: 'credential_id', value: storeBound?.credentialId || '-' },
          { label: 'auth_status', value: storeBound?.authStatus || '-' },
          { label: 'real_api_test_enabled', value: readiness?.realApiTestEnabled },
          { label: 'real_api_write_enabled', value: readiness?.realApiWriteEnabled },
          { label: 'channel_no_configured', value: channelReady },
          ...(connectionIssue ? [
            { label: 'connection_issue.error_code', value: connectionIssue.errorCode },
            { label: 'connection_issue.http_status', value: connectionIssue.httpStatus },
            { label: 'connection_issue.business_error_hint', value: connectionIssue.businessErrorHint },
            { label: 'connection_issue.safe_keyword_flags', value: connectionIssue.safeKeywordFlags },
            { label: 'connection_issue.capability_scope', value: connectionIssue.capabilityScope },
            { label: 'connection_issue.path_kind', value: connectionIssue.pathKind },
          ] : []),
        ]}
      />
    </section>
  );
}

export default function ApiCapabilities() {
  const {
    selectedStoreId, selectedStore, stores, loading: storeLoading, error: storeError,
  } = useStoreContext();
  const [capabilities, setCapabilities] = useState([]);
  const [results, setResults] = useState([]);
  const [readiness, setReadiness] = useState(emptyReadiness);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const currentStore = useMemo(
    () => selectedStore || stores.find((item) => String(item.id) === String(selectedStoreId)),
    [selectedStore, selectedStoreId, stores],
  );

  useEffect(() => {
    if (storeLoading) return;
    if (storeError) {
      setError(storeError);
      setLoading(false);
      return;
    }
    if (!selectedStoreId) {
      setCapabilities([]);
      setResults([]);
      setReadiness(emptyReadiness);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');
    Promise.all([
      dataProvider.getApiCapabilities({ page: 1, pageSize: 100 }),
      dataProvider.getApiCapabilityResults({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
      isBackendSource ? dataProvider.getApiCredentialReadiness({ storeId: selectedStoreId }) : Promise.resolve(emptyReadiness),
    ])
      .then(([capabilityResponse, resultResponse, readinessResponse]) => {
        const capabilityRows = capabilityResponse.data || capabilityResponse.items || [];
        const capabilityMap = new Map(capabilityRows.map((item) => [String(item.id), item]));
        const resultRows = (resultResponse.data || resultResponse.items || []).map((item) => ({
          ...item,
          capabilityKey: capabilityMap.get(String(item.capabilityId))?.capabilityKey || item.capabilityKey,
        }));
        setCapabilities(capabilityRows);
        setResults(resultRows);
        setReadiness(readinessResponse || emptyReadiness);
      })
      .catch((requestError) => {
        setError(requestError.message || '平台连接状态加载失败。');
        setCapabilities([]);
        setResults([]);
        setReadiness(emptyReadiness);
      })
      .finally(() => setLoading(false));
  }, [selectedStoreId, storeError, storeLoading]);

  const platform = normalizePlatform(currentStore?.rawPlatform || currentStore?.platform);
  const cards = buildPlatformBusinessStatus({
    platform,
    capabilities,
    results,
    readiness,
  });

  return (
    <>
      <PageHeader
        title="平台连接状态"
        description="用业务语言确认平台授权、店铺连接、商品读取、订单读取和批量同步保护状态。"
        actions={<span className="period-chip">技术详情默认折叠</span>}
      />

      {loading ? (
        <div className="table-state"><span className="spinner" />正在加载平台连接状态...</div>
      ) : error ? (
        <EmptyState title="平台连接状态加载失败" description={error} />
      ) : (
        <>
          <section className="content-card">
            <div className="card-title">
              <div>
                <h2>{businessCapabilityTitle(platform)}</h2>
                <p>默认展示卖家需要知道的状态：平台授权、店铺连接、商品读取、订单读取和正式批量同步是否开放。</p>
              </div>
              <span className="period-chip">{currentStore?.name || '当前店铺'}</span>
            </div>
            <BusinessCards cards={cards} />
          </section>

          <ReadinessSummary readiness={readiness} capabilities={capabilities} results={results} currentStore={currentStore} />

          <CapabilityTechnicalTable capabilities={capabilities} />
          <ResultTechnicalTable results={results} />
        </>
      )}
    </>
  );
}
