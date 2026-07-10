import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource } from '../utils/coreErpContract';
import { formatKstDateTimeWithLabel } from '../utils/time';

const PAGE_SIZE = 20;
const platformOptions = ['Naver', 'Coupang', 'Gmarket'];
const salesStatusOptions = ['在售', '审核中', '停售', '缺货', '待确认'];
const inventoryStatusOptions = ['缺货', '低库存', '库存正常'];

function text(value, fallback = '-') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function money(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function normalizeStatus(value) {
  const normalized = comparable(value);
  if (['판매중', 'sale', 'active', 'approved', '销售中', '在售'].includes(normalized)) return '在售';
  if (['심사중', 'review', 'in_review', 'approving', '审核中'].includes(normalized)) return '审核中';
  if (['판매중지', 'inactive', 'suspended', 'deleted', '停售'].includes(normalized)) return '停售';
  if (['outofstock', 'soldout', '缺货', '售罄'].includes(normalized)) return '缺货';
  return value ? '待确认' : '待确认';
}

function inventoryStatus(stock) {
  const count = Number(stock || 0);
  if (count <= 0) return '缺货';
  if (count <= 5) return '低库存';
  return '库存正常';
}

function storeName(row = {}, stores = []) {
  const id = row.storeId || row.store_id;
  const store = stores.find((item) => String(item.id) === String(id));
  return text(row.store || row.storeName || row.store_name || store?.name, '未关联店铺');
}

function normalizeProduct(row = {}, stores = []) {
  const stock = Number(row.stock ?? row.stock_quantity ?? 0);
  const salesStatus = normalizeStatus(row.status || row.rawStatus);
  const stockStatus = inventoryStatus(stock);
  const sourceInfo = classifyCoreDataSource(row);
  return {
    ...row,
    name: text(row.name || row.productName || row.product_name),
    sku: text(row.sku || row.externalId || row.platformProductId || row.platform_product_id, '平台商品编号已脱敏'),
    platform: text(row.platform || row.rawPlatform),
    store: storeName(row, stores),
    storeId: row.storeId || row.store_id,
    price: Number(row.price || row.salePrice || row.sellingPrice || 0),
    currency: row.currency || 'KRW',
    stock,
    salesStatus,
    stockStatus,
    platformStatus: salesStatus,
    sourceInfo,
    sourceLabel: sourceInfo.label,
    updatedAt: row.updatedAt || row.lastSyncedAt || row.syncedAt || '',
  };
}

function matches(row, query = {}) {
  const keyword = comparable(query.keyword);
  const haystack = [
    row.name,
    row.sku,
    row.platform,
    row.store,
    row.salesStatus,
    row.stockStatus,
    row.sourceLabel,
  ].map(comparable).join(' ');

  if (keyword && !haystack.includes(keyword)) return false;
  if (query.platform && comparable(row.platform) !== comparable(query.platform)) return false;
  if (query.storeId && String(row.storeId || '') !== String(query.storeId)) return false;
  if (query.salesStatus && row.salesStatus !== query.salesStatus) return false;
  if (query.inventoryStatus && row.stockStatus !== query.inventoryStatus) return false;
  return true;
}

const columns = [
  {
    key: 'name',
    title: '商品名',
    render: (value, row) => (
      <div>
        <strong>{value}</strong>
        <small className="cell-subtitle">{row.sku}</small>
      </div>
    ),
  },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'price', title: '售价', render: (value, row) => money(value, row.currency) },
  { key: 'stock', title: '库存' },
  { key: 'platformStatus', title: '平台状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'sourceLabel', title: '记录状态' },
  { key: 'updatedAt', title: '最近同步时间' },
];

export default function Products() {
  const {
    stores,
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [query, setQuery] = useState({
    keyword: '',
    platform: '',
    storeId: '',
    salesStatus: '',
    inventoryStatus: '',
    page: 1,
  });
  const [draft, setDraft] = useState(query);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeProduct, setActiveProduct] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (storeLoading) return;
      setLoading(true);
      setError('');
      try {
        const params = { page: 1, pageSize: 200 };
        if (isBackendSource && (query.storeId || selectedStoreId)) params.storeId = query.storeId || selectedStoreId;
        if (query.platform) params.platform = query.platform;
        const result = await dataProvider.getProducts(params);
        const normalized = (result.data || result.items || []).map((item) => normalizeProduct(item, stores));
        const filtered = normalized.filter((item) => matches(item, query));
        if (!cancelled) setRows(filtered);
      } catch (requestError) {
        if (!cancelled) {
          setRows([]);
          setError(requestError.message || '商品数据加载失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading, stores]);

  const summary = useMemo(() => ({
    total: rows.length,
    active: rows.filter((item) => item.salesStatus === '在售').length,
    low: rows.filter((item) => item.stockStatus === '低库存').length,
    out: rows.filter((item) => item.stockStatus === '缺货').length,
    attention: rows.filter((item) => item.salesStatus !== '在售' || item.stockStatus !== '库存正常').length,
  }), [rows]);

  const pageRows = rows.slice((query.page - 1) * PAGE_SIZE, query.page * PAGE_SIZE);

  const search = () => setQuery({ ...draft, page: 1 });
  const reset = () => {
    const clean = { keyword: '', platform: '', storeId: '', salesStatus: '', inventoryStatus: '', page: 1 };
    setDraft(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="商品管理"
        description="查看商品售价、库存和销售状态，帮助安排补货和发货。商品资料修改请按店铺流程处理。"
        actions={(
          <>
            <Link className="button ghost" to="/inventory">查看库存预警</Link>
            <Link className="button ghost" to="/shipping">进入仓库发货</Link>
            <span className="period-chip">暂不支持在线编辑</span>
          </>
        )}
      />

      <div className="summary-grid">
        <SummaryCard title="商品记录" value={summary.total} note="当前可查看商品" tone="info" />
        <SummaryCard title="在售商品" value={summary.active} note="当前销售状态" tone="success" />
        <SummaryCard title="低库存商品" value={summary.low} note="建议补货或人工确认" tone={summary.low ? 'warning' : 'success'} />
        <SummaryCard title="缺货商品" value={summary.out} note="建议补货或人工下架" tone={summary.out ? 'danger' : 'success'} />
      </div>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>运营建议</h2>
            <p>先看库存和销售状态，再决定补货、下架或进入仓库发货核对待发货订单。</p>
          </div>
        </div>
        <div className="business-capability-grid compact">
          <article className={summary.out ? 'business-capability-card danger' : 'business-capability-card success'}>
            <div className="business-capability-head"><strong>缺货处理</strong><span>{summary.out} 个</span></div>
            <p>缺货商品先确认能否补货；不能补货时由运营人工到平台后台处理销售状态。</p>
          </article>
          <article className={summary.low ? 'business-capability-card warning' : 'business-capability-card success'}>
            <div className="business-capability-head"><strong>低库存复核</strong><span>{summary.low} 个</span></div>
            <p>低库存商品优先核对物流商库存编号和实际库存，避免待发货订单缺货。</p>
          </article>
          <article className="business-capability-card info">
            <div className="business-capability-head"><strong>需要关注</strong><span>{summary.attention} 个</span></div>
            <p>把非在售、缺货和低库存商品作为每日商品巡检重点。</p>
          </article>
          <article className="business-capability-card muted">
            <div className="business-capability-head"><strong>发货联动</strong><span>待发货</span></div>
            <p>进入仓库发货核对待发货订单和仓库货号。</p>
          </article>
        </div>
      </section>

      <FilterPanel>
        <SearchBar
          value={draft.keyword}
          onChange={(keyword) => setDraft({ ...draft, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索商品名、平台商品编号、店铺或状态"
        >
          <select value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={draft.storeId} onChange={(event) => setDraft({ ...draft, storeId: event.target.value })}>
            <option value="">全部店铺</option>
            {stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}
          </select>
          <select value={draft.salesStatus} onChange={(event) => setDraft({ ...draft, salesStatus: event.target.value })}>
            <option value="">全部销售状态</option>
            {salesStatusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={draft.inventoryStatus} onChange={(event) => setDraft({ ...draft, inventoryStatus: event.target.value })}>
            <option value="">全部库存状态</option>
            {inventoryStatusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {storeError ? <EmptyState title="店铺信息不可用" description={storeError} /> : null}
        {error ? <EmptyState title="商品数据加载失败" description={error} /> : null}
        {!error ? (
          <>
            <DataTable
              columns={columns}
              rows={pageRows}
              loading={loading || storeLoading}
              renderActions={(row) => (
                <>
                  <button type="button" onClick={() => setActiveProduct(row)}>详情</button>
                  <button type="button" disabled title="暂不支持在线编辑">编辑暂未开放</button>
                </>
              )}
            />
            <Pagination
              page={query.page}
              pageSize={PAGE_SIZE}
              total={rows.length}
              onChange={(page) => setQuery({ ...query, page })}
            />
          </>
        ) : null}
      </section>

      <DetailModal
        open={Boolean(activeProduct)}
        title={activeProduct ? `商品详情 · ${activeProduct.name}` : '商品详情'}
        onClose={() => setActiveProduct(null)}
        width="min(980px, 94vw)"
      >
        {activeProduct ? (
          <>
            <div className="detail-grid">
              {[
                ['平台', activeProduct.platform],
                ['店铺', activeProduct.store],
                ['商品名', activeProduct.name],
                ['平台商品编号', activeProduct.sku],
                ['售价', money(activeProduct.price, activeProduct.currency)],
                ['库存', `${activeProduct.stock} 件`],
                ['销售状态', <StatusBadge value={activeProduct.salesStatus} />],
                ['库存状态', <StatusBadge value={activeProduct.stockStatus} />],
                ['记录状态', activeProduct.sourceInfo.label],
                ['最近更新时间', activeProduct.updatedAt ? formatKstDateTimeWithLabel(activeProduct.updatedAt) : '-'],
                ['当前编辑状态', '暂不支持在线编辑'],
              ].map(([label, value]) => (
                <div className="detail-item" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <section className="detail-section">
              <h3>商品记录说明</h3>
              <p>商品信息用于日常查看和发货核对；平台资料以平台后台显示为准。</p>
            </section>
            <section className="detail-section">
              <h3>暂未开放功能</h3>
              <div className="badge-row">
                <StatusBadge value="修改平台商品价格暂未开放" />
                <StatusBadge value="修改平台库存暂未开放" />
                <StatusBadge value="批量上下架暂未开放" />
                <StatusBadge value="删除真实平台商品暂未开放" />
              </div>
              <p>商品价格、库存和上下架需要按店铺权限在平台后台处理。</p>
            </section>
          </>
        ) : (
          <EmptyState title="暂无商品详情" description="请选择商品查看详情。" />
        )}
      </DetailModal>
    </>
  );
}
