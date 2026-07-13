import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FormField from '../components/common/FormField';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { buildApiAssetUrl } from '../services/http';

const PAGE_SIZE = 20;
const statuses = ['', 'new', 'pending', 'shipped', 'cancel', 'return', 'exchange', 'abnormal'];
const dateValue = (daysAgo) => { const date = new Date(Date.now() - daysAgo * 86400000); return date.toISOString().slice(0, 10); };

function normalizedOrder(row = {}) {
  const tracking = row.trackingNumber || row.tracking_number || row.trackingNo || '';
  return { ...row, orderNo: row.orderNo || row.external_order_id || row.order_id || row.id, product: row.product || row.productName || row.product_name || '-', option: row.option || row.optionName || row.option_name || '-', platformProductId: row.platformProductId || row.platform_product_id || row.product_id || '', productImageUrl: row.productImageUrl || row.product_image_url || '', productUrl: row.productUrl || row.product_url || '', quantity: row.quantity || 1, amount: row.amount ?? row.order_amount ?? 0, statusText: row.statusText || row.status || row.order_status || '-', shippingStatus: row.shippingStatus || row.delivery_status || '-', logisticsCompany: row.logisticsCompany || row.delivery_company || '-', trackingNo: tracking || '-', createdAt: row.createdAt || row.ordered_at || '', receiverName: row.receiverName || row.receiver_name || row.buyer_name || '', receiverPhone: row.receiverPhone || row.receiver_phone || row.buyer_phone || '', receiverAddress: row.receiverAddress || row.receiver_address || '', store: row.store || row.store_name || '-' };
}

function ProductCell({ order = {}, detail = false }) {
  const image = buildApiAssetUrl(order.productImageUrl);
  return <div className={`product-cell${detail ? ' product-cell-detail' : ''}`}><div className="product-thumb">{image ? <img src={image} alt="product" width={detail ? 72 : 48} height={detail ? 72 : 48} /> : <span>-</span>}</div><div className="product-cell-content"><strong className="product-cell-name" title={order.product}>{order.product}</strong><span className="product-cell-option">{order.option}</span>{order.platformProductId ? <span className="product-cell-id">Product ID {order.platformProductId}</span> : null}</div></div>;
}

const columns = [
  { key: 'orderNo', title: 'Order', render: (value) => <strong>{value}</strong> },
  { key: 'productCell', title: 'Product', render: (_, row) => <ProductCell order={row} /> },
  { key: 'quantity', title: 'Qty' },
  { key: 'amount', title: 'Amount', render: (value) => `${Number(value || 0).toLocaleString()} KRW` },
  { key: 'statusText', title: 'Status', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: 'Ordered at' },
  { key: 'shippingStatus', title: 'Shipping', render: (value) => <StatusBadge value={value} /> },
  { key: 'logisticsCompany', title: 'Logistics' },
  { key: 'trackingNo', title: 'Tracking' },
];

export default function Orders() {
  const [searchParams] = useSearchParams();
  const { stores, selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [view, setView] = useState('current');
  const [draft, setDraft] = useState({ storeId: '', status: searchParams.get('status') || '', orderId: '', productOrderId: '', productId: '', productName: '', buyerName: '', buyerPhone: '', startAt: dateValue(30), endAt: dateValue(1) });
  const [query, setQuery] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeOrder, setActiveOrder] = useState(null);
  const [backfill, setBackfill] = useState('');
  const onboardingId = (() => { try { return sessionStorage.getItem('t13_store_onboarding_id') || ''; } catch { return ''; } })();

  const effectiveStoreId = draft.storeId || selectedStoreId;
  const load = async (nextPage = page, nextQuery = query || draft) => {
    if (storeLoading || !effectiveStoreId) return;
    setLoading(true); setError('');
    try {
      const result = await dataProvider.getOrders({ ...nextQuery, storeId: effectiveStoreId, view, page: nextPage, pageSize: PAGE_SIZE, platform: 'naver', startAt: view === 'historical' ? nextQuery.startAt : undefined, endAt: view === 'historical' ? nextQuery.endAt : undefined });
      setRows((result.data || result.items || []).map(normalizedOrder));
      setTotal(Number(result.total || 0)); setPage(Number(result.page || nextPage));
    } catch (loadError) { setRows([]); setTotal(0); setError(loadError.message || 'Orders could not be loaded.'); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (!query && !storeLoading) load(1, draft); }, [selectedStoreId, storeLoading, view]);
  const summary = useMemo(() => ({ total, visible: rows.length }), [rows.length, total]);
  const submit = (event) => { event.preventDefault(); setQuery({ ...draft }); load(1, draft); };
  const reset = () => { const next = { ...draft, status: '', orderId: '', productOrderId: '', productId: '', productName: '', buyerName: '', buyerPhone: '', startAt: dateValue(30), endAt: dateValue(1) }; setDraft(next); setQuery(next); load(1, next); };
  const switchView = (next) => { setView(next); setPage(1); setQuery(null); };
  const runBackfill = async () => {
    if (!onboardingId) { setBackfill('No onboarding record is available for this store.'); return; }
    setBackfill('Backfill is running locally...');
    try { const result = await dataProvider.historicalOrderBackfill(onboardingId, { start_at: `${draft.startAt}T00:00:00+09:00`, end_at: `${draft.endAt}T23:59:59+09:00` }); setBackfill(result.localOnly ? 'Backfill completed locally; no platform write was performed.' : 'Backfill completed.'); setQuery({ ...draft }); load(1, draft); }
    catch (backfillError) { setBackfill(backfillError.message || 'Backfill failed.'); }
  };

  const historical = view === 'historical';
  return <>
    <PageHeader title="Orders" description={historical ? 'Read-only historical order review.' : 'Current order operations and detail review.'} actions={!historical ? <><button className="button primary" type="button" onClick={() => load(1, query || draft)}>Refresh</button><Link className="button ghost" to="/shipping">Warehouse shipping</Link></> : null} />
    <div className="workbench-view-switch" role="tablist"><button type="button" className={view === 'current' ? 'active' : ''} onClick={() => switchView('current')}>Current</button><button type="button" className={historical ? 'active' : ''} onClick={() => switchView('historical')}>Historical</button></div>
    {historical ? <div className="form-info">Historical orders are for audit and lookup. Platform updates, warehouse shipping, recipient copy, notes, and AI actions are unavailable.</div> : null}
    <section className="content-card order-filter-card"><form onSubmit={submit} className="order-filters"><FormField label="Store"><select value={draft.storeId} onChange={(e) => setDraft({ ...draft, storeId: e.target.value })}><option value="">Selected store</option>{stores.map((store) => <option value={store.id} key={store.id}>{store.name}</option>)}</select></FormField><FormField label="Status"><select value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })}>{statuses.map((status) => <option value={status} key={status}>{status || 'All statuses'}</option>)}</select></FormField>{[['orderId', 'Order ID'], ['productOrderId', 'Product order ID'], ['productId', 'Product ID'], ['productName', 'Product name'], ['buyerName', 'Buyer name'], ['buyerPhone', 'Buyer phone']].map(([key, label]) => <FormField label={label} key={key}><input value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} /></FormField>)}{historical ? <><FormField label="Start date"><input type="date" value={draft.startAt} onChange={(e) => setDraft({ ...draft, startAt: e.target.value })} /></FormField><FormField label="End date"><input type="date" value={draft.endAt} onChange={(e) => setDraft({ ...draft, endAt: e.target.value })} /></FormField></> : null}<div className="inline-action-group"><button className="button primary" type="submit">Apply filters</button><button className="button ghost" type="button" onClick={reset}>Reset</button></div></form></section>
    {historical ? <section className="content-card"><div className="card-title"><div><h2>Bounded historical backfill</h2><p>Maximum window is controlled by the backend. Retrieved records remain local and read-only.</p></div><button className="button ghost" type="button" onClick={runBackfill} disabled={!onboardingId}>Run backfill</button></div>{backfill ? <div className="form-info">{backfill}</div> : null}</section> : null}
    <section className="content-card"><div className="card-title"><h2>{summary.total} orders ({summary.visible} on page)</h2></div>{storeError ? <EmptyState title="Store unavailable" description={storeError} /> : null}{error ? <EmptyState title="Orders unavailable" description={error} /> : null}<DataTable columns={columns} rows={rows} loading={loading || storeLoading} rowKey="id" renderActions={(row) => <><button type="button" onClick={() => setActiveOrder(row)}>Details</button>{!historical ? <><button type="button" onClick={() => setActiveOrder(row)}>Copy recipient</button><Link to="/shipping">Warehouse shipping</Link><button type="button" onClick={() => setActiveOrder(row)}>Internal note</button></> : null}</>} />{!error ? <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={(nextPage) => load(nextPage, query || draft)} /> : null}</section>
    <DetailModal open={Boolean(activeOrder)} title={activeOrder ? `Order details - ${activeOrder.orderNo}` : 'Order details'} onClose={() => setActiveOrder(null)} width="min(720px, calc(100vw - 24px))">{activeOrder ? <><ProductCell order={activeOrder} detail /><div className="detail-grid">{[['Status', activeOrder.statusText], ['Shipping', activeOrder.shippingStatus], ['Logistics', activeOrder.logisticsCompany], ['Tracking', activeOrder.trackingNo], ['Source', historical ? 'historical local backfill' : 'current local order']].map(([label, value]) => <div className="detail-item" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>{historical ? <p className="mock-sync-note">Historical mode is read-only. No platform or warehouse action is available.</p> : null}</> : null}</DetailModal>
  </>;
}
