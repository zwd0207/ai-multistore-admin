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
    test_passed: '授权状态正常',
  };
  return labels[value] || value || '-';
}

const columns = [
  { key: 'name', title: '连接名称', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'connectionStatus', title: '连接资料' },
  { key: 'secretStatus', title: '敏感信息', render: () => '已隐藏' },
  { key: 'authStatusText', title: '授权状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'status', title: '启用状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'updatedAt', title: '最近更新' },
];

function CredentialBusinessStatus({ selectedStoreId, readiness }) {
  const storeBound = readiness?.storeBoundReadiness;
  const platform = String(storeBound?.rawPlatform || storeBound?.platform || '').toLowerCase();
  if (!selectedStoreId) return null;

  const isNaver = platform === 'naver';
  const title = isNaver ? 'Naver 连接资料' : platform === 'coupang' ? 'Coupang 连接资料' : '平台连接资料';
  const configured = Boolean(storeBound?.configured);
  const secretReady = Boolean(storeBound?.secretKeyConfigured && storeBound?.secretKeyDecryptable);
  const channelReady = Boolean(storeBound?.channelNoConfigured);

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
            <strong>{isNaver ? 'Naver 连接资料' : 'Coupang 连接资料'}</strong>
            <span>{configured ? '已配置' : '待配置'}</span>
          </div>
          <p>{configured ? '当前店铺已有平台连接资料。' : '请联系管理员补齐平台连接资料。'}</p>
        </article>
        <article className={`business-capability-card ${secretReady ? 'success' : 'warning'}`}>
          <div className="business-capability-head">
            <strong>授权状态</strong>
            <span>{secretReady ? '正常' : '待确认'}</span>
          </div>
          <p>敏感连接信息已隐藏，不会在页面显示明文。</p>
        </article>
        {isNaver ? (
          <article className={`business-capability-card ${channelReady ? 'success' : 'warning'}`}>
            <div className="business-capability-head">
              <strong>店铺连接</strong>
              <span>{channelReady ? '成功' : '待确认'}</span>
            </div>
            <p>店铺频道只显示是否识别，不展示完整编号。</p>
          </article>
        ) : (
          <article className="business-capability-card success">
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
          { label: 'channel_no_configured', value: channelReady },
        ]}
      />
    </section>
  );
}

export default function BackendCredentialPage({ embedded = false }) {
  const {
    selectedStoreId,
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
      return;
    }
    let cancelled = false;
    dataProvider.getApiCredentialReadiness({ storeId: selectedStoreId })
      .then((nextReadiness) => {
        if (!cancelled) setReadiness(nextReadiness);
      })
      .catch(() => {
        if (!cancelled) setReadiness(null);
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

      <CredentialBusinessStatus selectedStoreId={selectedStoreId} readiness={readiness} />

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
              <option key={item} value={item}>{item === 'active' ? '启用' : '停用'}</option>
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
