import { useCallback, useEffect, useState } from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useStoreContext } from '../context/StoreContext';
import dataProvider from '../services/dataProvider';

const statusOptions = ['active', 'inactive'];
const platformOptions = [
  { value: 'naver', label: 'Naver' },
  { value: 'coupang', label: 'Coupang' },
];

const CAPABILITY_LABELS = {
  'naver.token_auth': '平台授权',
  'naver.seller_account_read': '卖家账号',
  'naver.seller_channels_read': '店铺连接',
  'naver.product_read': '商品读取',
  'naver.order_read': '订单读取',
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

function connectionLabel(row) {
  const hasMainKey = row.rawPlatform === 'naver' ? Boolean(row.clientId) : Boolean(row.hasAccessKey);
  const hasSecret = Boolean(row.hasSecretKey);
  if (hasMainKey && hasSecret) return '连接资料已配置';
  if (hasMainKey || hasSecret) return '连接资料待补齐';
  return '连接资料未配置';
}

function authLabel(value) {
  const labels = {
    not_configured: '未配置',
    configured: '已配置',
    needs_test: '待确认',
    test_failed: '需要检查',
    test_passed: '连接正常',
  };
  return labels[value] || value || '-';
}

function activeLabel(value) {
  const labels = { active: '启用', inactive: '停用' };
  return labels[value] || value || '-';
}

function displayStoreName(value) {
  const text = String(value || '').trim();
  if (!text || /^店铺\s*#/.test(text)) return '当前店铺';
  return text;
}

const columns = [
  { key: 'name', title: '连接名称', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺', render: (value) => displayStoreName(value) },
  { key: 'platform', title: '平台' },
  { key: 'connectionStatus', title: '连接资料' },
  { key: 'secretStatus', title: '敏感信息', render: () => '已隐藏' },
  { key: 'authStatusText', title: '连接状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'status', title: '启用状态', render: (value) => <StatusBadge value={activeLabel(value)} /> },
  { key: 'updatedAt', title: '最近更新' },
];

function CredentialBusinessStatus({
  selectedStoreId,
  selectedStore,
  readiness,
  capabilities,
  results,
}) {
  const storeBound = readiness?.storeBoundReadiness;
  const platform = normalizePlatform(storeBound?.rawPlatform || storeBound?.platform || selectedStore?.rawPlatform || selectedStore?.platform);
  if (!selectedStoreId) return null;

  const isNaver = platform === 'naver';
  const isCoupang = platform === 'coupang';
  const title = isNaver ? 'Naver 连接资料' : isCoupang ? 'Coupang 连接资料' : '平台连接资料';
  const configured = Boolean(storeBound?.configured);
  const secretReady = Boolean(storeBound?.secretKeyConfigured && storeBound?.secretKeyDecryptable);
  const channelReady = Boolean(storeBound?.channelNoConfigured);
  const connectionIssue = isNaver
    ? findLatestIssue({
      capabilities,
      results,
      capabilityKeys: ['naver.token_auth', 'naver.seller_channels_read', 'naver.seller_account_read'],
    })
    : null;
  const authTone = connectionIssue ? connectionIssue.tone : secretReady || configured ? 'success' : 'warning';
  const authStatus = connectionIssue ? connectionIssue.statusLabel : secretReady || configured ? '可使用' : '待确认';
  const authReason = connectionIssue ? connectionIssue.title : '连接资料已保存，敏感内容不会在页面明文展示。';
  const authNextAction = connectionIssue ? connectionIssue.description : '如要重新检测或修改密钥，请由管理员在受控流程中处理。';
  const channelTone = connectionIssue ? 'warning' : channelReady || !isNaver ? 'success' : 'warning';
  const channelStatus = connectionIssue ? '待确认' : channelReady || !isNaver ? '已识别' : '待确认';
  const channelReason = isNaver
    ? '店铺频道只显示是否识别成功，不展示完整频道编号。'
    : '当前店铺连接资料已进入业务页面使用。';

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>{title}</h2>
          <p>这里只展示卖家需要理解的连接状态。平台密钥、Token、请求头和签名默认隐藏。</p>
        </div>
      </div>
      <div className="business-capability-grid compact">
        <article className={`business-capability-card ${configured ? 'success' : 'warning'}`}>
          <div className="business-capability-head">
            <strong>{title}</strong>
            <span>{configured ? '已配置' : '待配置'}</span>
          </div>
          <p>{configured ? '当前店铺已有平台连接资料。' : '请联系管理员补齐平台连接资料。'}</p>
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
          <p>{connectionIssue ? '当前连接需要先处理上方问题，处理后再确认店铺连接状态。' : channelReason}</p>
        </article>
        {isNaver ? (
          <article className="business-capability-card success">
            <div className="business-capability-head">
              <strong>商品状态</strong>
              <span>5 条稳定</span>
            </div>
            <p>当前本地已有 5 条 Naver 商品，暂无新增或业务字段更新，仅同步时间需要刷新。</p>
            <small>正式商品批量同步仍未开放。</small>
          </article>
        ) : (
          <article className="business-capability-card info">
            <div className="business-capability-head">
              <strong>业务页面</strong>
              <span>可查看</span>
            </div>
            <p>商品、订单、销售额和结算请在对应业务页面核对。</p>
          </article>
        )}
      </div>
      <TechnicalDetails
        description="维护字段仅供管理员排查。"
        items={[
          { label: 'credential_id', value: storeBound?.credentialId || '-' },
          { label: 'auth_status', value: storeBound?.authStatus || '-' },
          { label: 'client_id_configured', value: Boolean(storeBound?.clientIdConfigured) },
          { label: 'secret_key_configured', value: Boolean(storeBound?.secretKeyConfigured) },
          { label: 'secret_key_decryptable', value: Boolean(storeBound?.secretKeyDecryptable) },
          { label: 'channel_no_configured', value: channelReady },
          ...(connectionIssue ? [
            { label: 'connection_issue.error_code', value: connectionIssue.errorCode },
            { label: 'connection_issue.http_status', value: connectionIssue.httpStatus },
            { label: 'connection_issue.business_error_hint', value: connectionIssue.businessErrorHint },
            { label: 'connection_issue.safe_keyword_flags', value: connectionIssue.safeKeywordFlags },
            { label: 'connection_issue.capability_scope', value: connectionIssue.capabilityScope },
            { label: 'connection_issue.path_kind', value: connectionIssue.pathKind },
            { label: 'connection_issue.capability', value: CAPABILITY_LABELS[connectionIssue.capabilityKey] || connectionIssue.capabilityKey },
          ] : []),
        ]}
      />
    </section>
  );
}

export default function BackendCredentialPage({ embedded = false }) {
  const {
    selectedStoreId,
    selectedStore,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [query, setQuery] = useState({
    keyword: '',
    status: '',
    platform: '',
    page: 1,
    pageSize: 5,
  });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({
    data: [],
    total: 0,
    page: 1,
    pageSize: 5,
  });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [readiness, setReadiness] = useState(null);
  const [capabilities, setCapabilities] = useState([]);
  const [capabilityResults, setCapabilityResults] = useState([]);

  const load = useCallback(async () => {
    if (storeLoading) return;
    if (storeError) {
      setLoadError(storeError);
      setLoading(false);
      return;
    }
    if (!selectedStoreId) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError('');
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError('');
    try {
      setResult(await dataProvider.getCredentials({ ...query, storeId: selectedStoreId }));
    } catch (error) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError(error.message || '平台连接资料加载失败。');
    } finally {
      setLoading(false);
    }
  }, [query, selectedStoreId, storeError, storeLoading]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedStoreId || storeLoading || storeError) {
      setReadiness(null);
      setCapabilities([]);
      setCapabilityResults([]);
      return;
    }
    let cancelled = false;
    Promise.all([
      dataProvider.getApiCredentialReadiness({ storeId: selectedStoreId }),
      dataProvider.getApiCapabilities({ page: 1, pageSize: 100 }),
      dataProvider.getApiCapabilityResults({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
    ])
      .then(([nextReadiness, capabilityResponse, resultResponse]) => {
        if (cancelled) return;
        const capabilityRows = capabilityResponse.data || capabilityResponse.items || [];
        const capabilityMap = new Map(capabilityRows.map((item) => [String(item.id), item]));
        const resultRows = (resultResponse.data || resultResponse.items || []).map((item) => ({
          ...item,
          capabilityKey: capabilityMap.get(String(item.capabilityId))?.capabilityKey || item.capabilityKey,
        }));
        setReadiness(nextReadiness);
        setCapabilities(capabilityRows);
        setCapabilityResults(resultRows);
      })
      .catch(() => {
        if (!cancelled) {
          setReadiness(null);
          setCapabilities([]);
          setCapabilityResults([]);
        }
      });
    return () => { cancelled = true; };
  }, [selectedStoreId, storeError, storeLoading]);

  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => {
    const clean = {
      keyword: '',
      status: '',
      platform: '',
      page: 1,
      pageSize: 5,
    };
    setDraftQuery(clean);
    setQuery(clean);
  };

  const pageDescription = storeError
    || (!selectedStoreId && !storeLoading
      ? '请先选择店铺。'
      : '查看当前店铺的平台连接资料状态。敏感信息默认隐藏，维护操作请由管理员处理。');

  const rows = (result.data || []).map((row) => ({
    ...row,
    connectionStatus: connectionLabel(row),
    secretStatus: '已隐藏',
    authStatusText: authLabel(row.authStatus),
  }));

  return (
    <>
      {!embedded && (
        <PageHeader
          title="平台连接资料"
          description={pageDescription}
          actions={(
            <>
              <button className="button ghost" onClick={load}>刷新</button>
              <span className="period-chip">敏感信息已隐藏</span>
            </>
          )}
        />
      )}

      <CredentialBusinessStatus
        selectedStoreId={selectedStoreId}
        selectedStore={selectedStore}
        readiness={readiness}
        capabilities={capabilities}
        results={capabilityResults}
      />

      <section className="content-card">
        {embedded && (
          <div className="section-heading">
            <div>
              <h2>平台连接资料</h2>
              <p>{pageDescription}</p>
            </div>
            <div className="page-actions">
              <button className="button ghost" onClick={load}>刷新</button>
            </div>
          </div>
        )}

        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索连接名称或平台"
        >
          <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => (
              <option key={item} value={item}>{activeLabel(item)}</option>
            ))}
          </select>
        </SearchBar>

        {loadError ? (
          <EmptyState title="平台连接资料加载失败" description={loadError} />
        ) : !selectedStoreId && !storeLoading ? (
          <EmptyState title="暂无店铺数据" description="请先选择店铺后再查看平台连接资料。" />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={rows}
              loading={loading || storeLoading}
            />
            <Pagination
              page={query.page}
              pageSize={query.pageSize}
              total={result.total}
              onChange={(page) => setQuery({ ...query, page })}
            />
          </>
        )}
      </section>
    </>
  );
}
