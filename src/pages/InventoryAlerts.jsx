import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource } from '../utils/coreErpContract';

const inventoryTabs = [
  { key: '', label: '全部库存' },
  { key: '缺货', label: '缺货商品' },
  { key: '低库存', label: '低库存商品' },
  { key: '库存正常', label: '库存正常商品' },
];

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function money(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function inventoryStatus(stock) {
  const count = Number(stock || 0);
  if (count <= 0) return '缺货';
  if (count <= 5) return '低库存';
  return '库存正常';
}

function suggestionForStatus(status) {
  if (status === '缺货') return '建议尽快补货；无法补货时由运营人工到平台后台下架或暂停销售。';
  if (status === '低库存') return '建议核对物流商库存编号和实际库存，确认是否补货。';
  return '库存暂时正常，继续观察最近订单和补货周期。';
}

function normalizeProduct(row = {}, stores = []) {
  const stock = Number(row.stock ?? row.stock_quantity ?? 0);
  const status = inventoryStatus(stock);
  const store = stores.find((item) => String(item.id) === String(row.storeId || row.store_id));
  const sourceInfo = classifyCoreDataSource(row);
  return {
    ...row,
    name: row.name || row.productName || row.product_name || '-',
    platform: row.platform || row.rawPlatform || '-',
    store: row.store || row.storeName || row.store_name || store?.name || '未关联店铺',
    storeId: row.storeId || row.store_id,
    price: Number(row.price || 0),
    currency: row.currency || 'KRW',
    stock,
    inventoryStatus: status,
    sourceLabel: sourceInfo.label,
    sourceDescription: sourceInfo.description,
    suggestion: suggestionForStatus(status),
    updatedAt: row.updatedAt || row.lastSyncedAt || '',
  };
}

function matches(row, query = {}) {
  const keyword = comparable(query.keyword);
  const haystack = [row.name, row.platform, row.store, row.inventoryStatus, row.sourceLabel].map(comparable).join(' ');
  if (keyword && !haystack.includes(keyword)) return false;
  if (query.status && row.inventoryStatus !== query.status) return false;
  if (query.platform && comparable(row.platform) !== comparable(query.platform)) return false;
  if (query.storeId && String(row.storeId || '') !== String(query.storeId)) return false;
  return true;
}

const columns = [
  { key: 'name', title: '商品名称', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'price', title: '售价', render: (value, row) => money(value, row.currency) },
  { key: 'stock', title: '当前库存' },
  { key: 'inventoryStatus', title: '库存状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'suggestion', title: '库存不足处理建议' },
  { key: 'sourceLabel', title: '数据来源' },
  { key: 'updatedAt', title: '最近同步' },
];

export default function InventoryAlerts() {
  const {
    stores,
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', status: '', platform: '', storeId: '' });
  const [draft, setDraft] = useState(query);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (storeLoading) return;
      setLoading(true);
      setError('');
      try {
        const params = { page: 1, pageSize: 200 };
        if (isBackendSource && (query.storeId || selectedStoreId)) params.storeId = query.storeId || selectedStoreId;
        const result = await dataProvider.getProducts(params);
        const normalized = (result.data || result.items || []).map((item) => normalizeProduct(item, stores));
        if (!cancelled) setRows(normalized.filter((item) => matches(item, query)));
      } catch (requestError) {
        if (!cancelled) {
          setRows([]);
          setError(requestError.message || '库存数据加载失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading, stores]);

  const summary = useMemo(() => ({
    out: rows.filter((item) => item.inventoryStatus === '缺货').length,
    low: rows.filter((item) => item.inventoryStatus === '低库存').length,
    normal: rows.filter((item) => item.inventoryStatus === '库存正常').length,
    total: rows.length,
  }), [rows]);

  const search = () => setQuery({ ...draft });
  const reset = () => {
    const clean = { keyword: '', status: '', platform: '', storeId: '' };
    setDraft(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="库存预警"
        description="按本地库存判断缺货商品、低库存商品和库存正常商品，帮助运营决定补货、下架或人工确认。"
        actions={(
          <>
            <Link className="button ghost" to="/products">跳转商品管理</Link>
            <Link className="button primary" to="/shipping">跳转发货辅助</Link>
          </>
        )}
      />

      <div className="summary-grid">
        <SummaryCard title="缺货商品" value={summary.out} note="库存为 0" tone={summary.out ? 'danger' : 'success'} />
        <SummaryCard title="低库存商品" value={summary.low} note="库存 1-5 件" tone={summary.low ? 'warning' : 'success'} />
        <SummaryCard title="库存正常商品" value={summary.normal} note="库存高于预警线" tone="success" />
        <SummaryCard title="本地库存判断" value={summary.total} note="不修改平台库存" tone="info" />
      </div>

      <FilterPanel>
        <SearchBar
          value={draft.keyword}
          onChange={(keyword) => setDraft({ ...draft, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索商品、店铺、平台或库存状态"
        >
          <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
            {inventoryTabs.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
          <select value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })}>
            <option value="">全部平台</option>
            <option value="Naver">Naver</option>
            <option value="Coupang">Coupang</option>
            <option value="Gmarket">Gmarket/ESM</option>
          </select>
          <select value={draft.storeId} onChange={(event) => setDraft({ ...draft, storeId: event.target.value })}>
            <option value="">全部店铺</option>
            {stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {storeError ? <EmptyState title="店铺信息不可用" description={storeError} /> : null}
        {error ? <EmptyState title="库存数据加载失败" description={error} /> : null}
        {!error && !loading && !rows.length ? (
          <EmptyState
            title="暂无符合条件的库存记录"
            description="可以切换库存状态或返回商品管理查看系统已保存商品记录。"
            actions={<Link className="button primary" to="/products">查看商品管理</Link>}
          />
        ) : (
          <DataTable columns={columns} rows={rows} loading={loading || storeLoading} />
        )}
      </section>
    </>
  );
}
