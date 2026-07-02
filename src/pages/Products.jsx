import { useEffect, useMemo, useState } from 'react';
import ResourcePage from '../components/common/ResourcePage';
import MockSyncPanel from '../components/common/MockSyncPanel';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
import { getNaverProductPreviewStatus } from '../utils/capabilityStatusMapper';
import { formatKstDateTimeWithLabel } from '../utils/time';

const api = {
  list: dataProvider.getProducts,
  create: mockApi.createProduct,
  update: mockApi.updateProduct,
  remove: mockApi.deleteProduct,
};

const platformOptions = ['Naver', 'Coupang', 'Gmarket', '11st', 'Auction'];
const statusOptions = ['销售中', '审核中', '停售', '待同步', '草稿'];
const coupangStatusOptions = [
  'APPROVED',
  'IN_REVIEW',
  'SAVED',
  'APPROVING',
  'PARTIAL_APPROVED',
  'DENIED',
  'DELETED',
  'all',
];

function sourceLabel(value) {
  const labels = {
    naver_real_sync: 'Naver 小批量写入测试',
    naver_product_preview: 'Naver 商品预览',
    naver_product_preview_dry_run: 'Naver 商品预览',
    coupang_real_sync: 'Coupang 本地同步',
    coupang_product_sync: 'Coupang 本地同步',
  };
  return labels[value] || value || '-';
}

const columns = [
  { key: 'name', title: '商品名', render: (value, row) => <div><strong>{value}</strong><small className="cell-subtitle">{row.sku || '平台商品编号已脱敏'}</small></div> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'price', title: '售价', render: (value, row) => `${Number(value || 0).toLocaleString()} ${row.currency || 'KRW'}` },
  { key: 'stock', title: '库存' },
  { key: 'status', title: '平台状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'sourceType', title: '来源', render: sourceLabel },
  { key: 'updatedAt', title: '最近更新' },
];

const fields = [
  { key: 'name', label: '商品名', required: true },
  { key: 'sku', label: 'SKU', required: true },
  { key: 'store', label: '店铺', required: true },
  { key: 'platform', label: '平台', type: 'select', required: true, options: platformOptions },
  { key: 'price', label: '售价（KRW）', type: 'number', required: true },
  { key: 'stock', label: '库存', type: 'number', required: true },
  { key: 'status', label: '平台状态', type: 'select', required: true, options: statusOptions },
];

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '后端真实只读开关未开启，本次没有访问平台。',
    real_api_test_disabled: '后端真实只读开关未开启，本次没有访问平台。',
    ip_not_allowed: 'Naver API 请求 IP 未被允许，请检查 Naver Commerce API Center 的允许 IP 设置。',
    credential_invalid: 'Naver 连接资料可能无效，请检查 Client ID / Client Secret 是否正确。',
    permission_forbidden: 'Naver API 权限不足，请检查该应用是否已开通对应接口权限。',
    product_api_not_allowed: 'Naver 商品接口暂无权限或未开放，请检查商品 API 使用权限。',
    token_auth_failed: 'Naver 授权失败，请检查连接资料、平台权限或 Naver API 设置。',
    unknown_forbidden: 'Naver 请求被拒绝，请检查允许 IP、平台权限和连接资料。',
    auth_failed: 'Naver 授权失败，请检查连接资料、平台权限或 Naver API 设置。',
    CREDENTIAL_DECRYPT_FAILED: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
    decrypt_failed: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
  };
  return messages[code] || error?.message || '商品请求失败，请检查后端服务状态。';
}

function validateForm(status, maxPages) {
  if (!coupangStatusOptions.includes(status)) return '请选择有效的 Coupang 商品状态。';
  if (Number(maxPages) < 1 || Number(maxPages) > 3) return '单次最多读取 3 页。';
  return '';
}

function clampMaxPages(value) {
  const nextValue = Number(value || 1);
  if (Number.isNaN(nextValue)) return 1;
  return Math.min(3, Math.max(1, nextValue));
}

function PerStatusSummary({ rows = [] }) {
  if (!rows.length) return null;
  return (
    <TechnicalDetails title="查看按状态统计" description="这里保留平台返回状态的诊断摘要，默认不占用主页面。">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>status</th>
              <th>item_count</th>
              <th>would_create</th>
              <th>would_update</th>
              <th>skipped_count</th>
              <th>page_count</th>
              <th>next_cursor_exists</th>
              <th>sample_ids</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.status}>
                <td><strong>{item.status}</strong><small className="cell-subtitle">{item.statusSemantic || '平台商品状态'}</small></td>
                <td>{item.itemCount}</td>
                <td>{item.wouldCreate}</td>
                <td>{item.wouldUpdate}</td>
                <td>{item.skippedCount}</td>
                <td>{item.pageCount}</td>
                <td>{item.nextCursorExists ? 'true' : 'false'}</td>
                <td>{item.sampleIds?.length ? item.sampleIds.join(', ') : '[]'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TechnicalDetails>
  );
}

function ResultGrid({ result, mode }) {
  if (!result) return null;
  const isPreview = mode === 'preview';
  const createCount = Number(isPreview ? result.wouldCreate : result.createdCount || 0);
  const updateCount = Number(isPreview ? result.wouldUpdate : result.updatedCount || 0);
  const skippedCount = Number(result.skippedCount || 0);

  return (
    <div className="coupang-sync-result">
      <div className="sync-result-banner">
        {isPreview
          ? `预览完成：预计新增 ${createCount} 条，预计更新 ${updateCount} 条，预计跳过 ${skippedCount} 条。`
          : `本地写入完成：新增 ${createCount} 条，更新 ${updateCount} 条，跳过 ${skippedCount} 条。`}
      </div>
      <div className="business-capability-grid compact">
        <article className="business-capability-card info">
          <div className="business-capability-head"><strong>预计新增</strong><span>{createCount} 条</span></div>
          <p>本地暂未找到相同平台商品编号的商品。</p>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head"><strong>预计更新</strong><span>{updateCount} 条</span></div>
          <p>本地已有同一平台商品编号的商品。</p>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head"><strong>跳过</strong><span>{skippedCount} 条</span></div>
          <p>字段不完整或规则不允许时会跳过。</p>
        </article>
      </div>
      <TechnicalDetails
        items={[
          { label: 'would_create', value: result.wouldCreate },
          { label: 'would_update', value: result.wouldUpdate },
          { label: 'created_count', value: result.createdCount },
          { label: 'updated_count', value: result.updatedCount },
          { label: 'skipped_count', value: result.skippedCount },
          { label: 'status_filter', value: result.statusFilter },
          { label: 'page_count', value: result.pageCount },
          { label: 'next_cursor_exists', value: result.nextCursorExists },
          { label: 'max_pages', value: result.maxPages },
          { label: 'last_synced_at', value: formatKstDateTimeWithLabel(result.lastSyncedAt) },
          { label: 'sample_ids', value: result.sampleIds?.length ? result.sampleIds.join(', ') : '[]' },
        ]}
      />
      <PerStatusSummary rows={result.perStatus || []} />
    </div>
  );
}

function CoupangProductSyncPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const { markSynced } = useSyncRefresh();
  const [form, setForm] = useState({ status: 'APPROVED', maxPages: 1 });
  const [mode, setMode] = useState('');
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loadingAction, setLoadingAction] = useState('');

  const isCoupangStore = normalizePlatform(selectedStore?.platform) === 'coupang';
  const validationError = useMemo(
    () => validateForm(form.status, form.maxPages),
    [form.maxPages, form.status],
  );

  if (!isCoupangStore) return null;

  const run = async (action) => {
    setMessage('');
    setError('');
    setResult(null);
    setMode(action);

    if (validationError) {
      setError(validationError);
      return;
    }

    setLoadingAction(action);
    try {
      const payload = {
        storeId: selectedStoreId,
        status: form.status,
        maxPages: Number(form.maxPages),
      };
      const nextResult = action === 'preview'
        ? await dataProvider.previewCoupangProducts(payload)
        : await dataProvider.syncCoupangProducts(payload);
      setResult(nextResult);
      setMessage(action === 'preview'
        ? '商品预览已完成，本次只估算影响，不写入本地商品。'
        : '商品已写入本地数据库，不会对 Coupang 平台做写操作。');
      if (action === 'sync') markSynced('products');
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoadingAction('');
    }
  };

  return (
    <section className="content-card coupang-product-sync-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Coupang 商品读取</h2>
          <p>先预览会影响多少本地商品，再按需写入本地。不会修改 Coupang 平台商品。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>

      <div className="sync-control-grid product-sync-control-grid">
        <label>
          <span>商品状态</span>
          <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
            {coupangStatusOptions.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </label>
        <label>
          <span>最多读取页数</span>
          <input
            type="number"
            min="1"
            max="3"
            value={form.maxPages}
            onChange={(event) => setForm({ ...form, maxPages: clampMaxPages(event.target.value) })}
          />
        </label>
        <div className="sync-action-row">
          <button className="button ghost" onClick={() => run('preview')} disabled={Boolean(loadingAction)}>预览影响</button>
          <button className="button primary" onClick={() => run('sync')} disabled={Boolean(loadingAction)}>写入本地</button>
        </div>
      </div>

      <p className="mock-sync-note">单次最多读取 3 页。页面不会显示平台密钥、临时授权、请求签名或完整平台商品编号。</p>
      {form.status === 'APPROVED' && (
        <div className="sync-inline-warning">APPROVED 是 Coupang 平台状态，不一定完全等于后台“销售中”。</div>
      )}
      {validationError && <div className="sync-inline-warning">{validationError}</div>}
      {loadingAction && <div className="sync-inline-warning">{loadingAction === 'preview' ? '正在预览商品影响...' : '正在写入本地商品...'}</div>}
      {message && <div className="mock-sync-success">{message}</div>}
      {error && <div className="mock-sync-error">{error}</div>}
      <ResultGrid result={result} mode={mode} />
    </section>
  );
}

function NaverProductPreviewStatusPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [capabilities, setCapabilities] = useState([]);
  const [results, setResults] = useState([]);
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setCapabilities([]);
      setResults([]);
      return undefined;
    }
    let cancelled = false;
    Promise.all([
      dataProvider.getApiCapabilities({ page: 1, pageSize: 100 }),
      dataProvider.getApiCapabilityResults({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
    ])
      .then(([capabilityResponse, resultResponse]) => {
        if (cancelled) return;
        const capabilityRows = capabilityResponse.data || capabilityResponse.items || [];
        const capabilityMap = new Map(capabilityRows.map((item) => [String(item.id), item]));
        const resultRows = (resultResponse.data || resultResponse.items || []).map((item) => ({
          ...item,
          capabilityKey: capabilityMap.get(String(item.capabilityId))?.capabilityKey,
        }));
        setCapabilities(capabilityRows);
        setResults(resultRows);
      })
      .catch(() => {
        if (!cancelled) {
          setCapabilities([]);
          setResults([]);
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId]);

  if (!isNaverStore) return null;

  const status = getNaverProductPreviewStatus({ capabilities, results });
  const summary = status.summary;
  const activeIssue = status.activeIssue;

  return (
    <section className="content-card naver-preview-status-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 商品状态</h2>
          <p>{activeIssue ? 'Naver 当前连接异常，请检查平台连接资料或 API 设置。' : status.productRead.reason}</p>
        </div>
        <span className="period-chip">{selectedStore?.name || '当前店铺'}</span>
      </div>
      <div className="business-capability-grid compact">
        {activeIssue ? (
          <article className={`business-capability-card ${activeIssue.tone}`}>
            <div className="business-capability-head">
              <strong>当前连接异常</strong>
              <span>{activeIssue.statusLabel}</span>
            </div>
            <p>Naver 当前连接异常，请检查平台连接资料或 API 设置。</p>
            <small>{activeIssue.description}</small>
          </article>
        ) : null}
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>已写入本地商品</strong>
            <span>{summary.localSyncedCount} 条</span>
          </div>
          <p>Naver 商品小批量写入测试已完成。当前本地已有 5 条商品。</p>
          <small>其中新增 {summary.createdInLocalSync} 条，更新 {summary.updatedInLocalSync} 条。</small>
        </article>
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>当前需新增</strong>
            <span>{summary.wouldCreate} 条</span>
          </div>
          <p>再次预览没有发现需要新增到本地的商品。</p>
          <small>同一组商品已经存在于当前店铺本地记录中。</small>
        </article>
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>当前需更新</strong>
            <span>{summary.wouldUpdate} 条</span>
          </div>
          <p>当前没有发现商品名、状态、价格、币种或库存需要更新。</p>
          <small>不会把仅同步时间刷新误显示为商品内容更新。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>仅同步时间刷新</strong>
            <span>{summary.wouldRefreshOnly} 条</span>
          </div>
          <p>这 5 条商品都已存在本地，再次预览只提示同步时间需要刷新。</p>
          <small>当前没有新的业务字段变化需要处理。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>跳过</strong>
            <span>{summary.wouldSkip} 条</span>
          </div>
          <p>本次预览没有遇到需要跳过的异常商品。</p>
          <small>没有重复编号、状态异常或数值格式异常。</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>正式批量同步</strong>
            <span>{status.batchSync.statusLabel}</span>
          </div>
          <p>{status.batchSync.reason}</p>
          <small>{status.batchSync.nextAction}</small>
        </article>
      </div>
      <TechnicalDetails
        description="技术字段仅供管理员排查，主页面不直接展示这些字段。"
        items={[
          { label: 'store_id', value: summary.storeId },
          { label: 'credential_id', value: summary.credentialId },
          { label: 'real_preview', value: 'true' },
          { label: 'real_sync', value: 'false' },
          { label: 'matched_existing_count', value: summary.matchedExistingCount },
          { label: 'dry_run_diff.would_create', value: summary.wouldCreate },
          { label: 'dry_run_diff.would_update', value: summary.wouldUpdate },
          { label: 'dry_run_diff.would_refresh_only', value: summary.wouldRefreshOnly },
          { label: 'dry_run_diff.would_skip', value: summary.wouldSkip },
          { label: 'batch_sync_status', value: 'not_open' },
          ...(activeIssue
            ? activeIssue.technicalItems.map((item) => ({
              label: `preview_issue.${item.label}`,
              value: item.value,
            }))
            : []),
        ]}
      />
      <p className="mock-sync-note">本次未保存平台原始响应。页面不展示技术原文、完整平台商品编号、完整店铺频道编号、平台密钥、临时授权或请求签名。</p>
    </section>
  );
}

export default function Products() {
  const { selectedStoreId } = useStoreContext();
  const { versions } = useSyncRefresh();
  return (
    <>
      <NaverProductPreviewStatusPanel />
      <CoupangProductSyncPanel />
      <ResourcePage
        title="商品管理"
        description="查看各平台商品、价格、库存和来源。技术编号已默认脱敏。"
        resourceName="商品"
        api={api}
        columns={columns}
        fields={fields}
        statuses={statusOptions}
        platforms={platformOptions}
        initialForm={{ name: '', sku: '', store: '', platform: '', price: 0, stock: 0, status: '' }}
        readOnly={isBackendSource}
        extraParams={isBackendSource ? { storeId: selectedStoreId } : {}}
        reloadKey={`${selectedStoreId}-${versions.products}`}
        extraActions={!isBackendSource ? <MockSyncPanel types={['products']} compact /> : null}
      />
    </>
  );
}
