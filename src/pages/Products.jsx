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
    review: '审核中',
    in_review: '审核中',
    suspended: '停售',
    inactive: '停售',
    deleted: '已删除',
  };
  return labels[String(value || '').trim().toLowerCase()] || value || '未知';
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
    .replace('dry-run', '预览')
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

export default function Products() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const { versions } = useSyncRefresh();
  const columns = useMemo(() => buildColumns(selectedStore), [selectedStore]);

  return (
    <>
      <NaverProductPreviewStatusPanel />
      <ProductRollbackReadonlyReportRoutePanel />
      <CoupangProductSyncPanel />
      <ResourcePage
        title="商品管理"
        description="查看各平台商品、售价、库存、状态和最近同步情况。技术编号默认脱敏，正式批量同步未开放。"
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
