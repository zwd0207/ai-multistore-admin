import { useEffect, useMemo, useState } from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider from '../services/dataProvider';
import { getInventoryStatusForStock } from '../utils/naverInventory';

function moneyLabel(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function sourceLabel(value) {
  const labels = {
    naver_real_sync: '正式同步',
    naver_product_preview: '商品预览',
    naver_product_preview_dry_run: '同步预检',
    coupang_real_sync: '正式同步',
    coupang_product_sync: '正式同步',
  };
  return labels[value] || value || '本地记录';
}

function displayStoreName(value, selectedStore) {
  const text = String(value || '').trim();
  if (!text || /^店铺\s*#/.test(text)) return selectedStore?.name || '当前店铺';
  return text;
}

const columns = [
  { key: 'name', title: '商品名称', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'price', title: '售价', render: (value, row) => moneyLabel(value, row.currency) },
  { key: 'stock', title: '当前库存', render: (value) => {
    const status = getInventoryStatusForStock(value);
    return (
      <div>
        <strong>{status.stockLabel}</strong>
        <small className="cell-subtitle">{status.label}</small>
      </div>
    );
  } },
  { key: 'statusLabel', title: '预警状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'sourceType', title: '数据来源', render: sourceLabel },
  { key: 'updatedAt', title: '最近同步' },
];

export default function InventoryAlerts() {
  const { selectedStore, selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const { versions } = useSyncRefresh();
  const [state, setState] = useState({ loading: true, rows: [], error: '' });

  useEffect(() => {
    let cancelled = false;
    if (storeLoading) return () => { cancelled = true; };
    if (storeError) {
      setState({ loading: false, rows: [], error: storeError });
      return () => { cancelled = true; };
    }
    if (!selectedStoreId) {
      setState({ loading: false, rows: [], error: '' });
      return () => { cancelled = true; };
    }

    setState((current) => ({ ...current, loading: true, error: '' }));
    dataProvider.getProducts({ storeId: selectedStoreId, page: 1, pageSize: 100 })
      .then((result) => {
        if (cancelled) return;
        const rows = (result.data || result.items || []).map((item) => {
          const stock = item.stock ?? item.stock_quantity ?? 0;
          const stockStatus = getInventoryStatusForStock(stock);
          return {
            ...item,
            store: displayStoreName(item.store || item.store_name, selectedStore),
            stock,
            statusLabel: stockStatus.label,
            sourceType: item.sourceType || item.source_type,
          };
        }).filter((item) => Number(item.stock || 0) <= 5);
        setState({ loading: false, rows, error: '' });
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, rows: [], error: error.message || '库存数据加载失败' });
      });

    return () => { cancelled = true; };
  }, [selectedStore, selectedStoreId, storeError, storeLoading, versions.products]);

  const summary = useMemo(() => {
    const outOfStock = state.rows.filter((item) => Number(item.stock || 0) <= 0).length;
    const lowStock = state.rows.length - outOfStock;
    return { outOfStock, lowStock, total: state.rows.length };
  }, [state.rows]);

  return (
    <>
      <PageHeader
        title="库存预警"
        description="查看当前店铺缺货和低库存商品，优先补货或调整销售状态。"
        actions={<button type="button" className="button ghost" onClick={() => window.location.reload()}>刷新库存</button>}
      />
      <section className="content-card">
        <div className="business-capability-grid compact">
          <article className={summary.total ? 'business-capability-card warning' : 'business-capability-card success'}>
            <div className="business-capability-head">
              <strong>需要关注</strong>
              <span>{summary.total} 个商品</span>
            </div>
            <p>包含缺货和低库存商品，建议先处理缺货商品。</p>
          </article>
          <article className={summary.outOfStock ? 'business-capability-card danger' : 'business-capability-card muted'}>
            <div className="business-capability-head">
              <strong>缺货</strong>
              <span>{summary.outOfStock} 个</span>
            </div>
            <p>库存为 0 的商品需要尽快补货或下架。</p>
          </article>
          <article className={summary.lowStock ? 'business-capability-card info' : 'business-capability-card muted'}>
            <div className="business-capability-head">
              <strong>低库存</strong>
              <span>{summary.lowStock} 个</span>
            </div>
            <p>库存偏低，建议核对物流商库存编号和实际库存。</p>
          </article>
        </div>
      </section>
      <section className="content-card">
        {state.error ? (
          <EmptyState title="库存数据加载失败" description={state.error} />
        ) : !state.loading && !state.rows.length ? (
          <EmptyState
            title="当前没有库存异常"
            description="当前店铺暂未发现缺货或低库存商品。你可以返回商品管理查看全部商品。"
            actions={<button type="button" className="button primary" onClick={() => { window.location.href = '/products'; }}>查看商品管理</button>}
          />
        ) : (
          <DataTable columns={columns} rows={state.rows} loading={state.loading || storeLoading} />
        )}
      </section>
    </>
  );
}
