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
import {
  buildNaverInventorySummary,
  getInventoryStatusForStock,
} from '../utils/naverInventory';
import { buildNaverProductChangeHints } from '../utils/naverProductChangeHints';
import { formatKstDateTimeWithLabel } from '../utils/time';

const api = {
  list: dataProvider.getProducts,
  create: mockApi.createProduct,
  update: mockApi.updateProduct,
  remove: mockApi.deleteProduct,
};

const platformOptions = ['Naver', 'Coupang', 'Gmarket', '11st', 'Auction'];
const statusOptions = ['在售', '审核中', '禁售 / 平台限制', '售罄 / 缺货', '待同步', '草稿'];
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

const fields = [
  { key: 'name', label: '商品名称', required: true },
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

function sourceLabel(value) {
  const labels = {
    naver_real_sync: 'Naver 本地商品',
    naver_product_preview: 'Naver 商品预览',
    naver_product_preview_dry_run: 'Naver 商品预览',
    coupang_real_sync: 'Coupang 本地商品',
    coupang_product_sync: 'Coupang 本地商品',
  };
  return labels[value] || value || '-';
}

function statusLabel(value) {
  const labels = {
    active: '销售中',
    approved: '销售中',
    sale: '在售',
    판매중: '在售',
    review: '审核中',
    in_review: '审核中',
    prohibition: '禁售 / 平台限制',
    suspended: '停售',
    inactive: '停售',
    outofstock: '售罄 / 缺货',
    판매중지: '售罄 / 缺货',
    deleted: '已删除',
  };
  return labels[String(value || '').trim().toLowerCase()] || value || '未知';
}

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function productDisplayStatus(row = {}) {
  return statusLabel(row.rawStatus || row.status);
}

function matchesProductStatus(row = {}, status = '') {
  if (!status) return true;
  const displayStatus = productDisplayStatus(row);
  if (status === '在售') return ['在售', '销售中'].includes(displayStatus);
  if (status === '售罄 / 缺货') return displayStatus === '售罄 / 缺货' || Number(row.stock || 0) <= 0;
  return displayStatus === status || comparable(row.status) === comparable(status) || comparable(row.rawStatus) === comparable(status);
}

function matchesProductKeyword(row = {}, keyword = '') {
  const expected = comparable(keyword);
  if (!expected) return true;
  return [
    row.name,
    row.sku,
    row.externalId,
    row.platform,
    row.rawPlatform,
    row.brand,
    row.category,
    productDisplayStatus(row),
    sourceLabel(row.sourceType),
    row.price,
    row.stock,
  ].some((value) => comparable(value).includes(expected));
}

function matchesProductPlatform(row = {}, platform = '') {
  if (!platform) return true;
  return comparable(row.platform) === comparable(platform) || comparable(row.rawPlatform) === comparable(platform);
}

function paginateProducts(rows = [], page = 1, pageSize = 5) {
  const safePage = Math.max(Number(page) || 1, 1);
  const safePageSize = Math.max(Number(pageSize) || 5, 1);
  const start = (safePage - 1) * safePageSize;
  return rows.slice(start, start + safePageSize);
}

function filterOperatorProducts(rows = [], params = {}) {
  return rows.filter((row) => (
    matchesProductKeyword(row, params.keyword)
    && matchesProductPlatform(row, params.platform)
    && matchesProductStatus(row, params.status)
  ));
}

function moneyLabel(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function displayStoreName(value, selectedStore) {
  const text = String(value || '').trim();
  if (!text || /^店铺\s*#/.test(text)) return selectedStore?.name || '当前店铺';
  return text;
}

function businessReadableSummary(value = '') {
  return String(value)
    .replace('已只读检查', '已汇总')
    .replace('继续只读观察', '继续观察')
    .replace('dry-run', '同步预检')
    .replace('price', '价格')
    .replace('stock_quantity', '库存');
}

function buildColumns(selectedStore) {
  return [
    {
      key: 'name',
      title: '商品名称',
      render: (value, row) => (
        <div>
          <strong>{value}</strong>
          <small className="cell-subtitle">{row.sku || '平台商品编号已脱敏'}</small>
        </div>
      ),
    },
    { key: 'store', title: '店铺', render: (value) => displayStoreName(value, selectedStore) },
    { key: 'platform', title: '平台' },
    { key: 'price', title: '售价', render: (value, row) => moneyLabel(value, row.currency) },
    { key: 'stock', title: '库存', render: renderStock },
    { key: 'status', title: '平台状态', render: (value) => <StatusBadge value={statusLabel(value)} /> },
    { key: 'sourceType', title: '数据来源', render: sourceLabel },
    { key: 'updatedAt', title: '最近同步' },
  ];
}

function renderStock(value) {
  const status = getInventoryStatusForStock(value);
  return (
    <div>
      <strong>{status.stockLabel}</strong>
      <small className="cell-subtitle">{status.label}</small>
    </div>
  );
}

function InventoryAttentionList({ items = [] }) {
  if (!items.length) return null;
  return (
    <ul className="compact-list">
      {items.map((item, index) => (
        <li key={`${item.id || item.name || 'inventory'}-${index}`}>
          <strong>{item.name}</strong>
          <small>
            {item.statusLabel}，当前库存 {item.stockLabel} 件
            {item.updatedAt ? `，最近同步 ${formatKstDateTimeWithLabel(item.updatedAt)}` : ''}
          </small>
        </li>
      ))}
    </ul>
  );
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '后端真实只读开关未开启，本次没有访问平台。',
    real_api_test_disabled: '后端真实只读开关未开启，本次没有访问平台。',
    ip_not_allowed: 'Naver API 请求 IP 未被允许，请检查 Naver Commerce API Center 的允许 IP 设置。',
    credential_invalid: 'Naver 连接资料可能无效，请检查 Client ID / Client Secret。',
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
        <span className="period-chip">{selectedStore?.name || 'Coupang 店铺'}</span>
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

      <p className="mock-sync-note">单次最多读取 3 页。页面不显示平台密钥、临时授权、请求签名或完整平台商品编号。</p>
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
  const [inventoryProducts, setInventoryProducts] = useState([]);
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setCapabilities([]);
      setResults([]);
      setInventoryProducts([]);
      return undefined;
    }
    let cancelled = false;
    Promise.all([
      dataProvider.getApiCapabilities({ page: 1, pageSize: 100 }),
      dataProvider.getApiCapabilityResults({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
      dataProvider.getProducts({
        storeId: selectedStoreId,
        platform: 'Naver',
        page: 1,
        pageSize: 100,
      }).catch(() => ({ data: [], items: [] })),
    ])
      .then(([capabilityResponse, resultResponse, productResponse]) => {
        if (cancelled) return;
        const capabilityRows = capabilityResponse.data || capabilityResponse.items || [];
        const capabilityMap = new Map(capabilityRows.map((item) => [String(item.id), item]));
        const resultRows = (resultResponse.data || resultResponse.items || []).map((item) => ({
          ...item,
          capabilityKey: capabilityMap.get(String(item.capabilityId))?.capabilityKey,
        }));
        setCapabilities(capabilityRows);
        setResults(resultRows);
        setInventoryProducts(productResponse.data || productResponse.items || []);
      })
      .catch(() => {
        if (!cancelled) {
          setCapabilities([]);
          setResults([]);
          setInventoryProducts([]);
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId]);

  if (!isNaverStore) return null;

  const status = getNaverProductPreviewStatus({ capabilities, results });
  const summary = status.summary;
  const activeIssue = status.activeIssue;
  const inventorySummary = buildNaverInventorySummary(inventoryProducts, {
    selectedStore,
    selectedStoreId,
  });
  const productChangeHints = buildNaverProductChangeHints(inventoryProducts, {
    selectedStore,
    selectedStoreId,
    productStatus: status,
    results,
  });
  const inventoryMessage = businessReadableSummary(inventorySummary.businessMessage);
  const inventoryNextAction = businessReadableSummary(inventorySummary.nextAction);
  const productChangeMessage = businessReadableSummary(productChangeHints.businessMessage);
  const productChangeNextAction = businessReadableSummary(productChangeHints.nextAction);

  return (
    <section className="content-card naver-preview-status-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 商品概览</h2>
          <p>{activeIssue ? 'Naver 当前连接异常，请检查平台连接资料或 API 设置。' : '当前本地 Naver 商品状态稳定，可继续关注库存和价格变化。'}</p>
        </div>
        <span className="period-chip">{selectedStore?.name || 'Naver 店铺'}</span>
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
            <strong>本地商品</strong>
            <span>{summary.localSyncedCount} 条</span>
          </div>
          <p>当前本地已有 {summary.localSyncedCount || 5} 条 Naver 商品，暂无新增或业务字段更新。</p>
          <small>正式商品批量同步仍未开放。</small>
        </article>
        <article className={`business-capability-card ${inventorySummary.tone}`}>
          <div className="business-capability-head">
            <strong>库存提醒</strong>
            <span>{inventorySummary.statusLabel}</span>
          </div>
          <p>{inventoryMessage}</p>
          <small>{inventoryNextAction}</small>
        </article>
        {inventorySummary.attentionItems.length ? (
          <article className="business-capability-card warning">
            <div className="business-capability-head">
              <strong>需要关注的库存</strong>
              <span>{inventorySummary.attentionCount} 条</span>
            </div>
            <p>以下商品来自本地 Naver 商品记录，仅用于提醒，不会修改 Naver 平台库存。</p>
            <InventoryAttentionList items={inventorySummary.attentionItems} />
          </article>
        ) : (
          <article className="business-capability-card success">
            <div className="business-capability-head">
              <strong>库存处理建议</strong>
              <span>暂无紧急项</span>
            </div>
            <p>当前没有缺货、低库存或库存数据异常的本地 Naver 商品。</p>
            <small>低库存规则为库存大于 0 且低于 {inventorySummary.threshold} 件。</small>
          </article>
        )}
        <article className={`business-capability-card ${productChangeHints.tone}`}>
          <div className="business-capability-head">
            <strong>价格 / 库存变化</strong>
            <span>{productChangeHints.statusLabel}</span>
          </div>
          <p>{productChangeMessage}</p>
          <small>{productChangeNextAction}</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>价格 / 库存覆盖</strong>
            <span>{productChangeHints.total} 条</span>
          </div>
          <p>当前本地可展示价格 {productChangeHints.priceVisibleCount} 条，可展示库存 {productChangeHints.stockVisibleCount} 条。</p>
          <small>缺失或异常价格 {productChangeHints.missingOrInvalidPriceCount} 条，缺失或异常库存 {productChangeHints.missingOrInvalidStockCount} 条。</small>
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
          <small>仅同步时间刷新不会显示为商品内容更新。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>仅同步时间刷新</strong>
            <span>{summary.wouldRefreshOnly} 条</span>
          </div>
          <p>这部分商品已存在本地，只提示最近同步时间可以刷新。</p>
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
            <strong>正式商品同步</strong>
            <span>未开放</span>
          </div>
          <p>当前仍处于保护阶段，不会因为 5 条商品稳定就自动开放正式批量同步。</p>
          <small>批量同步必须单独确认后才会执行。</small>
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
          { label: 'inventory.source', value: inventorySummary.source },
          { label: 'inventory.total', value: inventorySummary.total },
          { label: 'inventory.out_of_stock', value: inventorySummary.outOfStock },
          { label: 'inventory.low_stock', value: inventorySummary.lowStock },
          { label: 'inventory.normal_stock', value: inventorySummary.normalStock },
          { label: 'inventory.invalid_stock', value: inventorySummary.invalidStock },
          { label: 'inventory.low_stock_threshold', value: inventorySummary.threshold },
          { label: 'inventory.threshold_rule', value: inventorySummary.thresholdRule },
          { label: 'inventory.attention_count', value: inventorySummary.attentionCount },
          { label: 'inventory.platform_read_performed', value: inventorySummary.platformReadPerformed },
          { label: 'inventory.platform_write_enabled', value: inventorySummary.platformWriteEnabled },
          { label: 'inventory.platform_comparison_available', value: inventorySummary.platformComparisonAvailable },
          { label: 'inventory.history_available', value: inventorySummary.inventoryHistoryAvailable },
          { label: 'inventory.raw_response_saved', value: inventorySummary.rawResponseSaved },
          { label: 'inventory.latest_updated_at', value: formatKstDateTimeWithLabel(inventorySummary.latestUpdatedAt) },
          { label: 'product_change_hints.source', value: productChangeHints.source },
          { label: 'product_change_hints.would_update', value: productChangeHints.wouldUpdate },
          { label: 'product_change_hints.would_refresh_only', value: productChangeHints.wouldRefreshOnly },
          { label: 'product_change_hints.changed_fields', value: productChangeHints.changedFields.length ? productChangeHints.changedFields.join(', ') : '[]' },
          { label: 'product_change_hints.price_change_observed', value: productChangeHints.priceChangeObserved },
          { label: 'product_change_hints.stock_change_observed', value: productChangeHints.stockChangeObserved },
          { label: 'product_change_hints.price_visible_count', value: productChangeHints.priceVisibleCount },
          { label: 'product_change_hints.stock_visible_count', value: productChangeHints.stockVisibleCount },
          { label: 'product_change_hints.platform_read_performed_this_phase', value: productChangeHints.platformReadPerformedThisPhase },
          { label: 'product_change_hints.platform_write_enabled', value: productChangeHints.platformWriteEnabled },
          { label: 'product_change_hints.raw_response_saved', value: productChangeHints.rawResponseSaved },
          { label: 'batch_sync_status', value: 'not_open' },
          ...(activeIssue
            ? activeIssue.technicalItems.map((item) => ({
              label: `preview_issue.${item.label}`,
              value: item.value,
            }))
            : []),
        ]}
      />
      <p className="mock-sync-note">本页面不展示平台密钥、临时授权、请求签名、完整店铺频道编号或平台原始响应。平台商品编号在主列表中按脱敏口径展示。</p>
    </section>
  );
}

function ProductRollbackReadonlyReportMockPanel() {
  const { selectedStore } = useStoreContext();
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';
  if (!isNaverStore) return null;

  const report = {
    phase: 'Naver-Product-Batch-1N',
    status: 'product_rollback_readonly_report_ui_mock_ready',
    reportReady: true,
    backupEvidenceVerified: true,
    updatedCount: 3,
    createdCount: 0,
    stockOnlyWriteVerified: true,
    rollbackExecuted: false,
    realRestoreExecuted: false,
    productionDbTouched: false,
    productsWritten: false,
    ordersWritten: false,
    syncLogWritten: false,
    capabilityTestedSuccessWritten: false,
    operationAuditRowsWritten: false,
    formalProductSyncOpen: false,
    platformWritesEnabled: false,
  };

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 商品回滚只读报告</h2>
          <p>这里展示商品库存小批量写入后的回滚准备情况，仅用于人工审核，不会恢复数据库，也不会再次写入商品。</p>
        </div>
        <span className="period-chip">只读报告</span>
      </div>
      <div className="business-capability-grid compact">
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>报告状态</strong>
            <span>已整理</span>
          </div>
          <p>商品回滚只读报告已准备好，可用于确认备份、回读校验和敏感字段扫描计划。</p>
          <small>这是 mock 展示面板，不会执行真实恢复。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>影响范围</strong>
            <span>{report.updatedCount} 条</span>
          </div>
          <p>最近一次受控商品写入只涉及库存字段，未新增商品，也未修改名称、状态或价格。</p>
          <small>正式商品批量同步仍未开放。</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>恢复操作</strong>
            <span>未执行</span>
          </div>
          <p>当前只展示恢复准备情况，不会把备份恢复到生产数据库。</p>
          <small>真实恢复必须单独审批，并先做临时库演练。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>后续动作</strong>
            <span>继续审核</span>
          </div>
          <p>下一步应把备份、审计、回读和回滚证据接入批量审批页面。</p>
          <small>页面不调用 Naver，也不执行 real_sync。</small>
        </article>
      </div>
      <TechnicalDetails
        title="查看商品回滚报告技术详情"
        description="这些字段仅供管理员排查，主页面只展示业务结论。"
        items={[
          { label: 'phase', value: report.phase },
          { label: 'status', value: report.status },
          { label: 'report_ready', value: report.reportReady },
          { label: 'backup_evidence_verified', value: report.backupEvidenceVerified },
          { label: 'updated_count', value: report.updatedCount },
          { label: 'created_count', value: report.createdCount },
          { label: 'stock_only_write_verified', value: report.stockOnlyWriteVerified },
          { label: 'rollback_executed', value: report.rollbackExecuted },
          { label: 'real_restore_executed', value: report.realRestoreExecuted },
          { label: 'production_db_touched', value: report.productionDbTouched },
          { label: 'products_written', value: report.productsWritten },
          { label: 'orders_written', value: report.ordersWritten },
          { label: 'sync_log_written', value: report.syncLogWritten },
          { label: 'tested_success_written', value: report.capabilityTestedSuccessWritten },
          { label: 'operation_audit_rows_written', value: report.operationAuditRowsWritten },
          { label: 'formal_product_sync_open', value: report.formalProductSyncOpen },
          { label: 'platform_writes_enabled', value: report.platformWritesEnabled },
        ]}
      />
    </section>
  );
}

function ProductRollbackReadonlyReportRoutePanel() {
  const { selectedStore } = useStoreContext();
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';
  const [state, setState] = useState({ loading: false, report: null, error: '' });

  useEffect(() => {
    if (!isNaverStore) {
      setState({ loading: false, report: null, error: '' });
      return undefined;
    }
    let cancelled = false;
    const rollbackDrillGate = {
      status: 'product_batch_rollback_drill_mock_ready',
      rollback_executed: false,
      real_restore_executed: false,
      products_written: false,
      backup_evidence_verified: true,
      updated_count: 3,
      created_count: 0,
      stock_only_write_verified: true,
    };
    setState((current) => ({ ...current, loading: true, error: '' }));
    dataProvider.getNaverProductRollbackReadonlyReport({ rollbackDrillGate })
      .then((report) => {
        if (!cancelled) setState({ loading: false, report, error: '' });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            loading: false,
            report: null,
            error: error?.message || '商品回滚只读报告暂时无法加载。',
          });
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore]);

  if (!isNaverStore) return null;

  const { loading, report, error } = state;
  const hasReport = report?.status === 'product_rollback_drill_readonly_report_ready';

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 商品回滚只读报告</h2>
          <p>这里展示商品库存小批量写入后的回滚准备情况，仅用于人工审核，不会恢复数据库，也不会再次写入商品。</p>
        </div>
        <span className="period-chip">{loading ? '加载中' : '只读报告'}</span>
      </div>
      {error ? <div className="mock-sync-error">{error}</div> : null}
      <div className="business-capability-grid compact">
        <article className={hasReport ? 'business-capability-card success' : 'business-capability-card warning'}>
          <div className="business-capability-head">
            <strong>报告状态</strong>
            <span>{hasReport ? '已整理' : '待确认'}</span>
          </div>
          <p>{report?.businessMessage || '商品回滚只读报告正在整理，当前不会执行恢复或写入商品。'}</p>
          <small>这里读取本地只读 route；不会执行真实恢复，也不会开放正式商品批量同步。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>影响范围</strong>
            <span>{report?.updatedCount ?? 0} 条</span>
          </div>
          <p>最近一次受控商品写入只涉及库存字段，未新增商品，也未修改名称、状态或价格。</p>
          <small>正式商品批量同步仍未开放。</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>恢复操作</strong>
            <span>未执行</span>
          </div>
          <p>当前只展示恢复准备情况，不会把备份恢复到生产数据库。</p>
          <small>真实恢复必须单独审批，并先做临时库演练。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>后续动作</strong>
            <span>继续审核</span>
          </div>
          <p>{report?.nextAction || '继续人工审核备份、回读和敏感扫描证据。'}</p>
          <small>页面不调用 Naver，也不执行 real_sync。</small>
        </article>
      </div>
      <TechnicalDetails
        title="查看商品回滚报告技术详情"
        description="这些字段仅供管理员排查，主页面只展示业务结论。"
        items={[
          { label: 'phase', value: report?.phase || 'Naver-Product-Batch-1R' },
          { label: 'status', value: report?.status },
          { label: 'skip_reason', value: report?.skipReason },
          { label: 'route_path', value: report?.routePath },
          { label: 'backend_route_implemented', value: report?.backendRouteImplemented },
          { label: 'public_endpoint_enabled', value: report?.publicEndpointEnabled },
          { label: 'report_ready', value: report?.reportReady },
          { label: 'backup_evidence_verified', value: report?.backupEvidenceVerified },
          { label: 'updated_count', value: report?.updatedCount },
          { label: 'created_count', value: report?.createdCount },
          { label: 'stock_only_write_verified', value: report?.stockOnlyWriteVerified },
          { label: 'rollback_executed', value: report?.rollbackExecuted },
          { label: 'real_restore_executed', value: report?.realRestoreExecuted },
          { label: 'production_db_touched', value: report?.productionDbTouched },
          { label: 'products_written', value: report?.productsWritten },
          { label: 'orders_written', value: report?.ordersWritten },
          { label: 'sync_log_written', value: report?.syncLogWritten },
          { label: 'tested_success_written', value: report?.capabilityTestedSuccessWritten },
          { label: 'operation_audit_rows_written', value: report?.operationAuditRowsWritten },
          { label: 'formal_product_sync_open', value: report?.formalProductSyncOpen },
          { label: 'platform_writes_enabled', value: report?.platformWritesEnabled },
        ]}
      />
    </section>
  );
}

const productBatchApprovalEvidenceLinks = [
  {
    key: 'readonly_candidates',
    title: '只读候选',
    status: '需要最新预览',
    message: '商品批量审批必须引用最新只读候选结果，不能直接使用旧截图或旧 dry-run。',
  },
  {
    key: 'backup_and_rollback',
    title: '备份与回滚',
    status: '必须关联',
    message: '审批材料必须关联数据库备份、回滚只读报告和临时库恢复演练结果。',
  },
  {
    key: 'field_whitelist',
    title: '字段白名单',
    status: '必须校验',
    message: '只允许写入已批准的商品业务字段，平台原始响应、密钥、请求头和完整平台编号不得入库。',
  },
  {
    key: 'audit_correlation',
    title: '审计关联',
    status: '必须留痕',
    message: '后续真实写入必须能关联批准人、备份、写入尝试、回读结果和敏感扫描。',
  },
];

function ProductBatchApprovalEvidenceLinkagePanel() {
  const { selectedStore } = useStoreContext();
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';
  if (!isNaverStore) return null;

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 商品批量审批证据联动</h2>
          <p>这里说明商品批量写入审批前必须串联哪些证据。当前只做展示和规划，不写商品、不恢复数据库，也不开放正式商品批量同步。</p>
        </div>
        <span className="period-chip">只读联动</span>
      </div>
      <div className="business-capability-grid compact">
        {productBatchApprovalEvidenceLinks.map((item) => (
          <article className="business-capability-card warning" key={item.key}>
            <div className="business-capability-head">
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </div>
            <p>{item.message}</p>
            <small>当前页面不会触发真实商品写入。</small>
          </article>
        ))}
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>正式商品批量同步</strong>
            <span>未开放</span>
          </div>
          <p>商品批量审批证据还在联动展示阶段，不能作为直接写入批准。</p>
          <small>真实写入必须另开阶段，并重新确认候选、备份、权限和回读。</small>
        </article>
      </div>
      <TechnicalDetails
        title="查看商品批量审批证据联动技术详情"
        description="这些字段仅用于管理员确认联动清单，不代表任何写入已批准。"
        items={[
          { label: 'phase', value: 'Naver-Product-Batch-2B' },
          { label: 'linkage_version', value: 'product_batch_approval_evidence_linkage_v1' },
          { label: 'linkage_item_count', value: productBatchApprovalEvidenceLinks.length },
          { label: 'real_api_called', value: false },
          { label: 'real_database_written', value: false },
          { label: 'products_written', value: false },
          { label: 'orders_written', value: false },
          { label: 'sync_log_written', value: false },
          { label: 'tested_success_written', value: false },
          { label: 'operation_audit_rows_written', value: false },
          { label: 'real_restore_executed', value: false },
          { label: 'formal_product_sync_open', value: false },
          { label: 'platform_writes_enabled', value: false },
          ...productBatchApprovalEvidenceLinks.map((item) => ({
            label: `evidence_link.${item.key}`,
            value: item.status,
          })),
        ]}
      />
    </section>
  );
}

const productBatchExecutionApprovalChecklist = [
  {
    key: 'fresh_candidates',
    title: '\u6700\u65b0\u53ea\u8bfb\u5019\u9009',
    status: '\u5fc5\u987b\u590d\u6838',
    message: '\u5546\u54c1\u6279\u91cf\u6267\u884c\u8303\u56f4\u5fc5\u987b\u6765\u81ea\u6700\u65b0\u53ea\u8bfb preview\uff0c\u4e0d\u80fd\u4f7f\u7528\u8fc7\u671f\u5dee\u5f02\u6216\u4eba\u5de5\u8bb0\u5fc6\u3002',
  },
  {
    key: 'field_whitelist',
    title: '\u5b57\u6bb5\u767d\u540d\u5355',
    status: '\u5fc5\u987b\u590d\u6838',
    message: '\u53ea\u5141\u8bb8\u5199\u5165\u5df2\u6279\u51c6\u7684\u5546\u54c1\u4e1a\u52a1\u5b57\u6bb5\uff0c\u4ef7\u683c\u3001\u5e93\u5b58\u548c\u72b6\u6001\u8981\u6709\u660e\u786e\u53d8\u5316\u8bc1\u636e\u3002',
  },
  {
    key: 'backup_rollback',
    title: '\u5907\u4efd\u4e0e\u56de\u6eda',
    status: '\u5fc5\u987b\u590d\u6838',
    message: '\u6267\u884c\u524d\u8981\u6709\u6570\u636e\u5e93\u5907\u4efd\uff0c\u6267\u884c\u540e\u8981\u6709\u56de\u8bfb\u548c\u56de\u6eda\u62a5\u544a\uff0c\u624d\u80fd\u652f\u6491\u5f02\u5e38\u6062\u590d\u3002',
  },
  {
    key: 'permission_approval',
    title: '\u6743\u9650\u4e0e\u4eba\u5de5\u5ba1\u6279',
    status: '\u5fc5\u987b\u590d\u6838',
    message: '\u64cd\u4f5c\u8005\u5fc5\u987b\u5177\u5907\u5f53\u524d\u5e97\u94fa\u7684\u5546\u54c1\u6279\u91cf\u5199\u5165\u5ba1\u6279\u6743\u9650\uff0c\u4e14\u672c\u6b21\u8303\u56f4\u8981\u88ab\u660e\u786e\u6279\u51c6\u3002',
  },
  {
    key: 'audit_chain',
    title: '\u5ba1\u8ba1\u94fe',
    status: '\u5fc5\u987b\u590d\u6838',
    message: '\u5fc5\u987b\u80fd\u5173\u8054\u6279\u51c6\u4eba\u3001\u5907\u4efd\u3001\u5019\u9009\u8303\u56f4\u3001\u5199\u5165\u5c1d\u8bd5\u3001\u56de\u8bfb\u7ed3\u679c\u548c\u654f\u611f\u626b\u63cf\u3002',
  },
  {
    key: 'platform_write_boundary',
    title: '\u5e73\u53f0\u5199\u64cd\u4f5c\u8fb9\u754c',
    status: '\u5fc5\u987b\u5173\u95ed',
    message: '\u5f53\u524d\u4ec5\u8ba1\u5212\u672c\u5730\u5546\u54c1\u6570\u636e\u5ba1\u6279\u6750\u6599\uff0c\u4e0d\u8c03\u7528 Naver \u5e73\u53f0\u5546\u54c1\u5199\u63a5\u53e3\u3002',
  },
];

function NaverProductBatchExecutionApprovalPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [state, setState] = useState({ loading: false, localProductCount: 0, error: '' });
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setState({ loading: false, localProductCount: 0, error: '' });
      return undefined;
    }
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: '' }));
    dataProvider.getProducts({
      storeId: selectedStoreId,
      platform: 'naver',
      page: 1,
      pageSize: 100,
    })
      .then((productResponse) => {
        if (cancelled) return;
        const rows = productResponse.data || productResponse.items || [];
        const naverProducts = rows.filter((product) => (
          normalizePlatform(product.platform || product.rawPlatform) === 'naver'
        ));
        setState({ loading: false, localProductCount: naverProducts.length, error: '' });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            loading: false,
            localProductCount: 0,
            error: error?.message || '\u5546\u54c1\u6279\u91cf\u6267\u884c\u5ba1\u6279\u6750\u6599\u6682\u65f6\u65e0\u6cd5\u52a0\u8f7d\u3002',
          });
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId]);

  if (!isNaverStore) return null;

  const { loading, localProductCount, error } = state;

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>{'\u5546\u54c1\u6279\u91cf\u6267\u884c\u5ba1\u6279\u53ea\u8bfb\u68c0\u67e5'}</h2>
          <p>{'\u8fd9\u91cc\u53ea\u5c55\u793a\u672a\u6765\u6b63\u5f0f\u5546\u54c1\u6279\u91cf\u6267\u884c\u524d\u9700\u8981\u590d\u6838\u7684\u4e1a\u52a1\u6750\u6599\u3002\u5f53\u524d\u4e0d\u6267\u884c\u5199\u5165\uff0c\u4e0d\u8c03\u7528 Naver\uff0c\u4e5f\u4e0d\u5f00\u653e\u6b63\u5f0f\u5546\u54c1\u6279\u91cf\u540c\u6b65\u3002'}</p>
        </div>
        <span className="period-chip">{loading ? '\u6574\u7406\u4e2d' : '\u53ea\u8bfb\u5ba1\u6279'}</span>
      </div>
      {error ? <div className="mock-sync-error">{error}</div> : null}
      <div className="business-capability-grid compact">
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>{'\u6267\u884c\u72b6\u6001'}</strong>
            <span>{'\u672a\u5f00\u653e'}</span>
          </div>
          <p>{'\u5f53\u524d\u53ea\u662f\u5546\u54c1\u6279\u91cf\u6267\u884c\u5ba1\u6279 UI\uff0c\u6ca1\u6709\u6267\u884c\u6309\u94ae\uff0c\u4e0d\u5199\u5546\u54c1\u3001\u4e0d\u5199\u8ba2\u5355\u3001\u4e0d\u5199\u5ba1\u8ba1\u8bb0\u5f55\u3002'}</p>
          <small>{'\u771f\u6b63\u6267\u884c\u4ecd\u5fc5\u987b\u53e6\u5f00\u9636\u6bb5\u5e76\u91cd\u65b0\u5ba1\u6279\u3002'}</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>{'\u672c\u5730\u5546\u54c1\u8303\u56f4'}</strong>
            <span>{localProductCount} {'\u6761'}</span>
          </div>
          <p>{'\u672c\u9762\u677f\u53ea\u6839\u636e\u5f53\u524d\u5e97\u94fa\u672c\u5730 Naver \u5546\u54c1\u6574\u7406\u590d\u6838\u63d0\u793a\uff0c\u4e0d\u4ee3\u8868\u5e73\u53f0\u6709\u65b0\u7684\u5f85\u5199\u5165\u5019\u9009\u3002'}</p>
          <small>{'\u771f\u5b9e\u5019\u9009\u5fc5\u987b\u6765\u81ea\u5355\u72ec\u7684\u53ea\u8bfb preview\u3002'}</small>
        </article>
        {productBatchExecutionApprovalChecklist.map((item) => (
          <article className="business-capability-card info" key={item.key}>
            <div className="business-capability-head">
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </div>
            <p>{item.message}</p>
            <small>{'\u672a\u5168\u90e8\u590d\u6838\u524d\uff0c\u5546\u54c1\u6279\u91cf\u6267\u884c\u4fdd\u6301\u5173\u95ed\u3002'}</small>
          </article>
        ))}
      </div>
      <TechnicalDetails
        title={"\u67e5\u770b\u5546\u54c1\u6279\u91cf\u6267\u884c\u5ba1\u6279\u6280\u672f\u8be6\u60c5"}
        description={"\u6267\u884c\u72b6\u6001\u3001\u95e8\u7981\u548c\u5199\u5165\u5f00\u5173\u4ec5\u4f9b\u7ba1\u7406\u5458\u6392\u67e5\uff1b\u4e3b\u9875\u9762\u53ea\u5c55\u793a\u4e1a\u52a1\u590d\u6838\u63d0\u793a\u3002"}
        items={[
          { label: 'phase', value: 'Naver-Product-Batch-2F' },
          { label: 'mock_gate_phase', value: 'Naver-Product-Batch-2D' },
          { label: 'selected_store_id', value: selectedStoreId },
          { label: 'local_product_count', value: localProductCount },
          { label: 'checklist_item_count', value: productBatchExecutionApprovalChecklist.length },
          { label: 'execution_approved', value: false },
          { label: 'real_api_called', value: false },
          { label: 'real_database_written', value: false },
          { label: 'orders_written', value: false },
          { label: 'products_written', value: false },
          { label: 'sync_log_written', value: false },
          { label: 'tested_success_written', value: false },
          { label: 'timeline_events_written', value: false },
          { label: 'operation_audit_rows_written', value: false },
          { label: 'formal_product_sync_open', value: false },
          { label: 'platform_product_writes_enabled', value: false },
          { label: 'platform_writes_enabled', value: false },
          { label: 'raw_response_saved', value: false },
          { label: 'privacy_fields_redacted', value: true },
          ...productBatchExecutionApprovalChecklist.map((item) => ({
            label: `product_batch_execution_check.${item.key}`,
            value: item.status,
          })),
        ]}
      />
    </section>
  );
}

const PRODUCT_BATCH_SYNC_ACTION = 'product_batch_local_sync_succeeded';

function isProductBatchSyncAudit(row = {}) {
  const action = row.advancedDetails?.action || row.action || row.rawAction || '';
  const actionType = String(row.actionType || '');
  return action === PRODUCT_BATCH_SYNC_ACTION || actionType.includes('\u5546\u54c1\u672c\u5730\u540c\u6b65');
}

function auditCount(row = {}, key) {
  const counts = row.advancedDetails?.counts_summary || row.advancedDetails?.countsSummary || {};
  return Number(counts[key] ?? counts[key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())] ?? 0);
}

function backupEvidenceLabel(row = {}) {
  const backup = row.backupEvidence || row.advancedDetails?.backup_path || row.advancedDetails?.backupPath;
  if (!backup || String(backup).includes('\u6682\u65e0')) return '\u672a\u5173\u8054\u5907\u4efd';
  return '\u5df2\u5173\u8054\u5907\u4efd';
}

function NaverProductBatchSyncHistoryPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const { versions } = useSyncRefresh();
  const [state, setState] = useState({ loading: false, rows: [], error: '' });
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setState({ loading: false, rows: [], error: '' });
      return undefined;
    }
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: '' }));
    dataProvider.getOperationAuditLogs({
      storeId: selectedStoreId,
      page: 1,
      pageSize: 20,
    })
      .then((result) => {
        if (cancelled) return;
        const rows = (result.data || result.items || [])
          .filter(isProductBatchSyncAudit)
          .slice(0, 3);
        setState({ loading: false, rows, error: '' });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            loading: false,
            rows: [],
            error: error?.message || '\u5546\u54c1\u540c\u6b65\u5386\u53f2\u6682\u65f6\u65e0\u6cd5\u52a0\u8f7d\u3002',
          });
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId, versions.products]);

  if (!isNaverStore) return null;

  const { loading, rows, error } = state;
  const latest = rows[0];
  const createdCount = auditCount(latest, 'created_count');
  const updatedCount = auditCount(latest, 'updated_count');
  const skippedCount = auditCount(latest, 'skipped_count');

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>{'\u6700\u8fd1\u5546\u54c1\u540c\u6b65\u8bb0\u5f55'}</h2>
          <p>{'\u8fd9\u91cc\u53ea\u5c55\u793a\u5df2\u5b8c\u6210\u7684\u672c\u5730\u5546\u54c1\u540c\u6b65\u5ba1\u8ba1\u6458\u8981\uff0c\u7528\u6765\u8ba9\u8fd0\u8425\u4eba\u5458\u770b\u61c2\u6700\u8fd1\u5199\u5165\u4e86\u4ec0\u4e48\u3002\u4e0d\u8c03\u7528 Naver\uff0c\u4e0d\u6267\u884c\u65b0\u5199\u5165\u3002'}</p>
        </div>
        <span className="period-chip">{loading ? '\u52a0\u8f7d\u4e2d' : '\u53ea\u8bfb\u5386\u53f2'}</span>
      </div>
      {error ? <div className="mock-sync-error">{error}</div> : null}
      <div className="business-capability-grid compact">
        <article className={latest ? 'business-capability-card success' : 'business-capability-card muted'}>
          <div className="business-capability-head">
            <strong>{'\u6700\u8fd1\u4e00\u6b21'}</strong>
            <span>{latest ? '\u5df2\u8bb0\u5f55' : '\u6682\u65e0'}</span>
          </div>
          <p>{latest
            ? `\u6700\u8fd1\u672c\u5730\u5546\u54c1\u540c\u6b65\uff1a\u65b0\u589e ${createdCount} \u6761\uff0c\u66f4\u65b0 ${updatedCount} \u6761\uff0c\u8df3\u8fc7 ${skippedCount} \u6761\u3002`
            : '\u5f53\u524d\u8fd8\u6ca1\u6709\u53ef\u5c55\u793a\u7684\u5546\u54c1\u540c\u6b65\u5ba1\u8ba1\u8bb0\u5f55\u3002'}</p>
          <small>{latest?.time ? formatKstDateTimeWithLabel(latest.time) : '\u6267\u884c\u540e\u4f1a\u5728\u8fd9\u91cc\u663e\u793a\u65f6\u95f4\u3001\u7ed3\u679c\u548c\u5907\u4efd\u8bc1\u636e\u3002'}</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>{'\u5907\u4efd\u8bc1\u636e'}</strong>
            <span>{backupEvidenceLabel(latest)}</span>
          </div>
          <p>{latest ? '\u8be5\u8bb0\u5f55\u5df2\u4ece\u5ba1\u8ba1\u65e5\u5fd7\u8bfb\u53d6\uff0c\u53ef\u7528\u4e8e\u540e\u7eed\u56de\u6eda\u548c\u95ee\u9898\u8ffd\u8e2a\u3002' : '\u5c1a\u65e0\u53ef\u7528\u7684\u5546\u54c1\u540c\u6b65\u5907\u4efd\u8bc1\u636e\u3002'}</p>
          <small>{'\u9875\u9762\u4e0d\u5c55\u793a\u5b8c\u6574\u5e73\u53f0\u7f16\u53f7\u3001token\u3001headers\u3001signature \u6216 raw response\u3002'}</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>{'\u540c\u6b65\u8fb9\u754c'}</strong>
            <span>{'\u4ecd\u9700\u53d7\u63a7'}</span>
          </div>
          <p>{'\u5386\u53f2\u5c55\u793a\u53ea\u662f\u5b89\u5168\u5ba1\u8ba1\u6458\u8981\uff0c\u4e0d\u80fd\u4f5c\u4e3a\u5546\u54c1\u6279\u91cf\u540c\u6b65\u5f00\u653e\u4f9d\u636e\uff1b\u6269\u5927\u9875\u6570\u3001\u6279\u91cf\u5199\u5165\u548c\u5e73\u53f0\u5199\u64cd\u4f5c\u4ecd\u9700\u5355\u72ec\u5ba1\u6279\u3002'}</p>
          <small>{'\u5f53\u524d\u662f\u672c\u5730 products \u884c\u7684\u5b89\u5168\u5ba1\u8ba1\u6458\u8981\u3002'}</small>
        </article>
      </div>
      {rows.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{'\u65f6\u95f4'}</th>
                <th>{'\u7ed3\u679c'}</th>
                <th>{'\u65b0\u589e'}</th>
                <th>{'\u66f4\u65b0'}</th>
                <th>{'\u5907\u4efd'}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id || row.auditId}>
                  <td>{row.time ? formatKstDateTimeWithLabel(row.time) : '-'}</td>
                  <td>{row.status || '\u5df2\u5b8c\u6210'}</td>
                  <td>{auditCount(row, 'created_count')}</td>
                  <td>{auditCount(row, 'updated_count')}</td>
                  <td>{backupEvidenceLabel(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <TechnicalDetails
        title={"\u67e5\u770b\u5546\u54c1\u540c\u6b65\u5ba1\u8ba1\u6280\u672f\u6458\u8981"}
        description={"\u8fd9\u91cc\u4ec5\u4fdd\u7559\u7ba1\u7406\u5458\u6392\u67e5\u6240\u9700\u7684\u5df2\u8131\u654f\u5ba1\u8ba1\u5b57\u6bb5\u3002"}
        items={[
          { label: 'phase', value: 'Naver-Product-Batch-Exec-1B' },
          { label: 'selected_store_id', value: selectedStoreId },
          { label: 'history_rows_loaded', value: rows.length },
          { label: 'readonly_api_used', value: true },
          { label: 'real_api_called', value: false },
          { label: 'real_database_written', value: false },
          { label: 'products_written', value: false },
          { label: 'orders_written', value: false },
          { label: 'sync_log_written', value: false },
          { label: 'tested_success_written', value: false },
          { label: 'operation_audit_rows_written', value: false },
          { label: 'platform_writes_enabled', value: false },
          { label: 'latest_audit_summary', value: latest?.advancedDetails || {} },
        ]}
      />
    </section>
  );
}

export default function Products() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const { versions } = useSyncRefresh();
  const columns = useMemo(() => buildColumns(selectedStore), [selectedStore]);
  const pageApi = useMemo(() => ({
    ...api,
    list: async (params = {}) => {
      const fullResult = await dataProvider.getProducts({
        ...params,
        keyword: '',
        status: '',
        page: 1,
        pageSize: 100,
      });
      const filteredRows = filterOperatorProducts(fullResult.data || fullResult.items || [], params);
      return {
        ...fullResult,
        data: paginateProducts(filteredRows, params.page, params.pageSize),
        items: paginateProducts(filteredRows, params.page, params.pageSize),
        total: filteredRows.length,
        page: params.page || 1,
        pageSize: params.pageSize || 5,
      };
    },
  }), []);

  return (
    <>
      <ResourcePage
        title="商品管理"
        description="当前显示的是系统已保存的商品记录，正式批量同步暂未开放。"
        resourceName="商品"
        api={pageApi}
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
