import { useMemo, useState } from 'react';
import ResourcePage from '../components/common/ResourcePage';
import MockSyncPanel from '../components/common/MockSyncPanel';
import StatusBadge from '../components/common/StatusBadge';
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

const columns = [
  { key: 'name', title: '商品名称', render: (value, row) => <div><strong>{value}</strong><small className="cell-subtitle">{row.sku}</small></div> },
  { key: 'store', title: '所属店铺' },
  { key: 'platform', title: '平台' },
  { key: 'price', title: '售价', render: (value, row) => `${Number(value || 0).toLocaleString()} ${row.currency || 'KRW'}` },
  { key: 'stock', title: '库存' },
  { key: 'status', title: '销售状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'sourceType', title: '来源', render: (value) => value || '-' },
  { key: 'updatedAt', title: '最近同步' },
];

const fields = [
  { key: 'name', label: '商品名称', required: true },
  { key: 'sku', label: 'SKU', required: true },
  { key: 'store', label: '所属店铺', required: true },
  { key: 'platform', label: '平台', type: 'select', required: true, options: platformOptions },
  { key: 'price', label: '售价（KRW）', type: 'number', required: true },
  { key: 'stock', label: '库存', type: 'number', required: true },
  { key: 'status', label: '销售状态', type: 'select', required: true, options: statusOptions },
];

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '真实只读检测开关未启用，后端已拒绝发起外部请求。',
    real_api_test_disabled: '真实只读检测开关未启用，后端已拒绝发起外部请求。',
    ip_not_allowed: '当前服务器公网 IP 不在 Coupang OpenAPI allowlist 中。',
    auth_failed: 'Coupang 认证失败，请检查凭证、vendorId、权限或 IP allowlist。',
    CREDENTIAL_DECRYPT_FAILED: '本地凭证解密失败，请在当前加密 key 环境下重新保存凭证。',
    decrypt_failed: '本地凭证解密失败，请在当前加密 key 环境下重新保存凭证。',
  };
  return messages[code] || error?.message || '商品同步请求失败，请检查 Codex1 后端状态。';
}

function validateForm(status, maxPages) {
  if (!coupangStatusOptions.includes(status)) return '请选择有效的 Coupang 商品状态。';
  if (Number(maxPages) < 1 || Number(maxPages) > 3) return 'max_pages 必须在 1 到 3 之间。';
  return '';
}

function clampMaxPages(value) {
  const nextValue = Number(value || 1);
  if (Number.isNaN(nextValue)) return 1;
  return Math.min(3, Math.max(1, nextValue));
}

function PerStatusSummary({ rows = [] }) {
  if (!rows.length) {
    return <div className="empty-state compact">暂无 per_status 明细。mock 模式不会伪造真实商品检测结果。</div>;
  }

  return (
    <div className="per-status-summary">
      <h3>per_status summary</h3>
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
                <td><strong>{item.status}</strong><small className="cell-subtitle">{item.statusSemantic || 'Coupang API 商品审核/刊登状态'}</small></td>
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
    </div>
  );
}

function ResultGrid({ result, mode }) {
  if (!result) return null;
  const isPreview = mode === 'preview';
  const emptyCount = isPreview
    ? Number(result.wouldCreate || 0) + Number(result.wouldUpdate || 0)
    : Number(result.createdCount || 0) + Number(result.updatedCount || 0) + Number(result.skippedCount || 0);
  const emptyMessage = emptyCount === 0 ? '同步成功，无符合条件商品。' : '';

  return (
    <div className="coupang-sync-result">
      <div className="sync-result-banner">{emptyMessage || '请求完成，结果如下。'}</div>
      <div className="sync-result-grid">
        {isPreview ? (
          <>
            <span>would_create</span><strong>{result.wouldCreate}</strong>
            <span>would_update</span><strong>{result.wouldUpdate}</strong>
          </>
        ) : (
          <>
            <span>created_count</span><strong>{result.createdCount}</strong>
            <span>updated_count</span><strong>{result.updatedCount}</strong>
            <span>skipped_count</span><strong>{result.skippedCount}</strong>
          </>
        )}
        <span>status_filter</span><strong>{result.statusFilter}</strong>
        <span>page_count</span><strong>{result.pageCount}</strong>
        <span>next_cursor_exists</span><strong>{result.nextCursorExists ? 'true' : 'false'}</strong>
        <span>max_pages</span><strong>{result.maxPages}</strong>
        <span>last_synced_at</span><strong>{formatKstDateTimeWithLabel(result.lastSyncedAt)}</strong>
        <span>sample_ids</span><strong>{result.sampleIds?.length ? result.sampleIds.join(', ') : '[]'}</strong>
      </div>
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
      if (!isBackendSource) {
        setMessage('mock 模式仅显示空态说明，不会伪造 Coupang 商品只读检测结果。');
      } else {
        setMessage(action === 'preview'
          ? 'Preview 完成：只读取 Coupang 商品只读接口，未写入 products。'
          : 'Sync 完成：只写入本地 products，不会对 Coupang 平台做写操作。');
      }
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
          <h2>Coupang 商品只读同步</h2>
          <p>这是 Coupang 商品只读接口；Sync 只写本地数据库，不会对 Coupang 平台做写操作。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>

      <div className="sync-control-grid product-sync-control-grid">
        <label>
          <span>status</span>
          <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
            {coupangStatusOptions.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </label>
        <label>
          <span>max_pages</span>
          <input
            type="number"
            min="1"
            max="3"
            value={form.maxPages}
            onChange={(event) => setForm({ ...form, maxPages: clampMaxPages(event.target.value) })}
          />
        </label>
        <div className="sync-action-row">
          <button className="button ghost" onClick={() => run('preview')} disabled={Boolean(loadingAction)}>Preview</button>
          <button className="button primary" onClick={() => run('sync')} disabled={Boolean(loadingAction)}>Sync</button>
        </div>
      </div>

      <p className="mock-sync-note">max_pages 默认 1，最大 3。不会显示平台密钥、临时授权凭证或请求签名，也不会新增 API key 输入逻辑。</p>
      {form.status === 'APPROVED' && (
        <div className="sync-inline-warning">APPROVED 是 Coupang API 商品审核/刊登状态，不一定完全等于后台“销售中”。</div>
      )}
      {validationError && <div className="sync-inline-warning">{validationError}</div>}
      {loadingAction && <div className="sync-inline-warning">{loadingAction === 'preview' ? 'Preview 请求中...' : 'Sync 请求中...'}</div>}
      {message && <div className="mock-sync-success">{message}</div>}
      {error && <div className="mock-sync-error">{error}</div>}
      <ResultGrid result={result} mode={mode} />
    </section>
  );
}

function NaverProductPreviewStatusPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';
  if (!isNaverStore) return null;
  const status = getNaverProductPreviewStatus();

  return (
    <section className="content-card naver-preview-status-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 商品读取状态</h2>
          <p>单条商品写库微测已完成；当前仅完成 1 条 Naver 商品本地写库微测，后续批量同步需单独确认。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>
      <div className="business-capability-grid">
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>商品读取</strong>
            <span>{status.productRead.statusLabel}</span>
          </div>
          <p>{status.productRead.reason}</p>
          <small>{status.productRead.nextAction}</small>
        </article>
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>本地写库</strong>
            <span>{status.localSync.statusLabel}</span>
          </div>
          <p>{status.localSync.reason}</p>
          <small>{status.localSync.nextAction}</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>批量同步</strong>
            <span>{status.batchSync.statusLabel}</span>
          </div>
          <p>{status.batchSync.reason}</p>
          <small>{status.batchSync.nextAction}</small>
        </article>
      </div>
      <p className="mock-sync-note">已写入 1 条本地商品；正式批量同步未开放；本次未保存平台原始响应。页面不会展示 raw_data 原文、完整平台商品编号、平台密钥、临时授权凭证、请求签名或完整店铺频道编号。</p>
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
        description="查看并维护跨平台商品、价格和库存信息"
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
        extraActions={isBackendSource ? <MockSyncPanel types={['products']} compact /> : null}
      />
    </>
  );
}
