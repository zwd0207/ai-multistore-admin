import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { buildApiAssetUrl } from '../services/http';
import { classifyCoreDataSource } from '../utils/coreErpContract';

const PAGE_SIZE = 20;

function dateDaysAgo(days) {
  return new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
}

function initialHistoryFilters(storeId = '') {
  return {
    storeId,
    startAt: dateDaysAgo(31),
    endAt: dateDaysAgo(1),
    orderId: '',
    productOrderId: '',
    productId: '',
    productName: '',
    status: '',
    buyerName: '',
    buyerPhone: '',
  };
}

const statusTabs = [
  { key: '', label: '全部订单' },
  { key: 'new', label: '新订单' },
  { key: 'pending', label: '待发货' },
  { key: 'shipped', label: '已发货' },
  { key: 'cancel', label: '取消订单' },
  { key: 'return', label: '退货订单' },
  { key: 'exchange', label: '换货订单' },
  { key: 'abnormal', label: '异常订单' },
];

function textOf(...values) {
  return values.filter(Boolean).map((value) => String(value)).join(' ');
}

function normalizedOrder(row = {}) {
  const statusText = textOf(row.status, row.order_status, row.rawStatus, row.raw_status, row.delivery_status_label_zh, row.claim_status_label_zh);
  const product = row.product || row.productName || row.product_name || row.name || '-';
  const option = row.option || row.optionName || row.option_name || row.spec || '-';
  const shippingStatus = row.deliveryStatusLabelZh || row.delivery_status_label_zh || row.shippingStatus || row.delivery_status || '-';
  const deliveryCompany = row.deliveryCompany || row.delivery_company || row.logisticsCompany || row.courier || '';
  const trackingNumber = row.trackingNumber || row.tracking_number || row.trackingNo || row.invoiceNo || '';
  return {
    ...row,
    orderNo: row.orderNo || row.external_order_id || row.order_id || row.id,
    platform: row.platform || row.rawPlatform || '-',
    store: row.store || row.storeName || row.store_name || '-',
    product,
    option,
    platformProductId: row.platformProductId || '',
    productImageUrl: row.productImageUrl || '',
    productUrl: row.productUrl || '',
    quantity: row.quantity || row.qty || 1,
    amount: row.amount ?? row.order_amount ?? row.totalAmount ?? 0,
    statusText: statusText || '-',
    shippingStatus,
    deliveryCompany,
    deliveryCompanyCode: row.deliveryCompanyCode || row.delivery_company_code || '',
    trackingNumber,
    logisticsTraceStatus: row.logisticsTraceStatus || row.logistics_trace_status || (trackingNumber ? 'local_tracking_trace' : 'tracking_number_missing'),
    logisticsCompany: deliveryCompany || '-',
    trackingNo: trackingNumber || '-',
    createdAt: row.createdAt || row.ordered_at || row.orderDate || row.paid_at || '',
    receiverName: row.receiverName || row.receiver_name || row.customer || row.buyer_name || '',
    receiverPhone: row.receiverPhone || row.receiver_phone || row.phone || row.buyer_phone || '',
    receiverAddress: row.receiverAddress || row.receiver_address || row.address || '',
    sourceInfo: classifyCoreDataSource(row),
  };
}

function hasDisplayValue(value) {
  const text = String(value || '').trim();
  return Boolean(text && text !== '-');
}

function ProductCell({ order = {}, detail = false }) {
  const [imageFailed, setImageFailed] = useState(false);
  const productName = order.product || order.productName || '-';
  const optionName = order.option || order.optionName || '-';
  const platformProductId = order.platformProductId || '';
  const productUrl = order.productUrl || '';
  const canOpenProduct = productUrl && platformProductId;
  const imageUrl = buildApiAssetUrl(order.productImageUrl);

  useEffect(() => setImageFailed(false), [imageUrl]);

  return (
    <div className={`product-cell${detail ? ' product-cell-detail' : ''}`}>
      <div className="product-thumb">
        {imageUrl && !imageFailed ? (
          <img
            src={imageUrl}
            alt={`${productName} 商品缩略图`}
            loading="lazy"
            width={detail ? 72 : 48}
            height={detail ? 72 : 48}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="product-thumb-placeholder" role="img" aria-label="暂无商品图片">-</span>
        )}
      </div>
      <div className="product-cell-content">
        <strong className="product-cell-name" title={productName}>{productName}</strong>
        <span className="product-cell-option" title={optionName}>{optionName}</span>
        {platformProductId ? (
          canOpenProduct ? (
            <a className="product-cell-id" href={productUrl} target="_blank" rel="noopener noreferrer">
              商品编号 {platformProductId} &#8599;
            </a>
          ) : (
            <span className="product-cell-id">商品编号 {platformProductId}</span>
          )
        ) : null}
      </div>
    </div>
  );
}

function matchesStatus(row, statusKey) {
  if (!statusKey) return true;
  const text = textOf(row.statusText, row.status, row.order_status, row.rawStatus, row.raw_status, row.delivery_status, row.claim_status).toLowerCase();
  const checks = {
    new: ['新订单', '已付款', 'payed', 'place_product_order'],
    pending: ['待发货', 'ready', 'delivery_ready'],
    shipped: ['已发货', '配送中', 'delivering', 'dispatched', 'shipped'],
    cancel: ['取消', 'cancel'],
    return: ['退货', 'return'],
    exchange: ['换货', 'exchange'],
    abnormal: ['异常', '取消', '退款', '退货', '换货', 'claim', 'refund', 'return', 'exchange', 'cancel'],
  };
  return (checks[statusKey] || []).some((flag) => text.includes(flag.toLowerCase()));
}

function copyReceiverText(order = {}) {
  return [
    `收件人：${order.receiverName || '-'}`,
    `电话：${order.receiverPhone || '-'}`,
    `地址：${order.receiverAddress || '-'}`,
  ].join('\n');
}

async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  return false;
}

const columns = [
  { key: 'orderNo', title: '订单号', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'productCell', title: '商品和选项', render: (_, row) => <ProductCell order={row} /> },
  { key: 'quantity', title: '数量' },
  { key: 'amount', title: '订单金额', render: (value, row) => `${Number(value || 0).toLocaleString()} ${row.currency || 'KRW'}` },
  { key: 'statusText', title: '订单状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '下单时间' },
  { key: 'shippingStatus', title: '发货状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'logisticsCompany', title: '快递公司' },
  { key: 'trackingNo', title: '运单号' },
];

export default function Orders() {
  const [searchParams] = useSearchParams();
  const deepLinkOrderId = searchParams.get('orderId');
  const deepLinkStatus = searchParams.get('status') || '';
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
    status: deepLinkStatus,
    page: 1,
  });
  const [draft, setDraft] = useState(query);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeOrder, setActiveOrder] = useState(null);
  const [noteModal, setNoteModal] = useState({ open: false, order: null });
  const [notes, setNotes] = useState({});
  const [copyMessage, setCopyMessage] = useState('');
  const [refreshingOrders, setRefreshingOrders] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState('');
  const [detailRefreshing, setDetailRefreshing] = useState(false);
  const [detailRefreshNotice, setDetailRefreshNotice] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const [traceModal, setTraceModal] = useState({ open: false, order: null, trace: null });
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState('');
  const [viewMode, setViewMode] = useState('current');
  const [historyDraft, setHistoryDraft] = useState(() => initialHistoryFilters());
  const [historyQuery, setHistoryQuery] = useState(() => initialHistoryFilters());
  const [historyRows, setHistoryRows] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyBackfillNotice, setHistoryBackfillNotice] = useState('');
  const [historyBackfilling, setHistoryBackfilling] = useState(false);
  const [historyOnboarding, setHistoryOnboarding] = useState(null);
  const [historyOnboardingReason, setHistoryOnboardingReason] = useState('后端暂未提供按店铺查询连接任务的接口，当前店铺无法确认回填任务。');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (viewMode !== 'current') return;
      if (storeLoading) return;
      setLoading(true);
      setError('');
      try {
        const params = {
          page: 1,
          pageSize: 100,
          keyword: query.keyword,
          platform: query.platform,
        };
        if (isBackendSource && (query.storeId || selectedStoreId)) params.storeId = query.storeId || selectedStoreId;
        const result = await dataProvider.getOrders(params);
        let nextRows = (result.data || result.items || []).map(normalizedOrder);
        if (!isBackendSource && query.storeId) {
          const store = stores.find((item) => String(item.id) === String(query.storeId));
          nextRows = nextRows.filter((item) => item.store === store?.name || String(item.storeId || item.store_id) === String(query.storeId));
        }
        if (query.keyword) {
          const keyword = String(query.keyword).trim().toLowerCase();
          nextRows = nextRows.filter((item) => Object.values(item).some((value) => String(value ?? '').toLowerCase().includes(keyword)));
        }
        nextRows = nextRows.filter((item) => matchesStatus(item, query.status));
        if (!cancelled) {
          setRows(nextRows);
          if (deepLinkOrderId) {
            setActiveOrder(nextRows.find((item) => String(item.orderId ?? item.id) === deepLinkOrderId) || null);
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setRows([]);
          setError(loadError.message || '订单数据加载失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading, stores, refreshKey, deepLinkOrderId, viewMode]);

  useEffect(() => {
    if (viewMode !== 'historical' || !isBackendSource) return undefined;
    const storeId = historyQuery.storeId || selectedStoreId;
    setHistoryOnboarding(null);
    if (!storeId) {
      setHistoryOnboardingReason('请先选择店铺，再确认历史回填任务。');
      return undefined;
    }
    let cancelled = false;
    dataProvider.getStoreOnboardings({ storeId })
      .then((items) => {
        if (cancelled) return;
        const result = items.find((item) => String(item?.storeId || '') === String(storeId));
        if (!result) {
          setHistoryOnboardingReason('当前店铺没有已完成的 Naver 添加任务；历史回填暂不可用。');
          return;
        }
        setHistoryOnboarding(result);
        setHistoryOnboardingReason('');
      })
      .catch(() => {
        if (!cancelled) setHistoryOnboardingReason('无法确认当前店铺的添加任务；为避免串店，历史回填已禁用。');
      });
    return () => { cancelled = true; };
  }, [viewMode, historyQuery.storeId, selectedStoreId]);

  useEffect(() => {
    if (viewMode !== 'historical' || storeLoading) return undefined;
    const storeId = historyQuery.storeId || selectedStoreId;
    if (!storeId) {
      setHistoryRows([]);
      setHistoryTotal(0);
      setHistoryError('请先选择店铺。');
      return undefined;
    }
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError('');
    dataProvider.getOrders({
      storeId,
      platform: 'naver',
      view: 'historical',
      page: historyPage,
      pageSize: PAGE_SIZE,
      startAt: `${historyQuery.startAt}T00:00:00+09:00`,
      endAt: `${historyQuery.endAt}T23:59:59+09:00`,
      orderId: historyQuery.orderId,
      productOrderId: historyQuery.productOrderId,
      productId: historyQuery.productId,
      productName: historyQuery.productName,
      status: historyQuery.status,
      buyerName: historyQuery.buyerName,
      buyerPhone: historyQuery.buyerPhone,
    }).then((result) => {
      if (cancelled) return;
      setHistoryRows((result.data || result.items || []).map(normalizedOrder));
      setHistoryTotal(Number(result.total || 0));
    }).catch((loadError) => {
      if (!cancelled) {
        setHistoryRows([]);
        setHistoryTotal(0);
        setHistoryError(loadError.message || '历史订单加载失败。');
      }
    }).finally(() => {
      if (!cancelled) setHistoryLoading(false);
    });
    return () => { cancelled = true; };
  }, [viewMode, historyQuery, historyPage, selectedStoreId, storeLoading]);

  const summary = useMemo(() => ({
    total: rows.length,
    pending: rows.filter((item) => matchesStatus(item, 'pending')).length,
    shipped: rows.filter((item) => matchesStatus(item, 'shipped')).length,
    abnormal: rows.filter((item) => matchesStatus(item, 'abnormal')).length,
  }), [rows]);

  const search = () => setQuery({ ...draft, page: 1 });
  const reset = () => {
    const next = { keyword: '', platform: '', storeId: '', status: '', page: 1 };
    setDraft(next);
    setQuery(next);
  };

  const openNote = (order) => {
    setNoteModal({ open: true, order });
  };

  const saveNote = () => {
    const orderNo = noteModal.order?.orderNo;
    if (orderNo) setNotes((current) => ({ ...current, [orderNo]: noteModal.note || '' }));
    setNoteModal({ open: false, order: null, note: '' });
  };

  const handleCopy = async (order) => {
    const ok = await copyToClipboard(copyReceiverText(order));
    setCopyMessage(ok ? `已复制 ${order.orderNo} 的收件信息` : '当前浏览器不支持自动复制，请在详情中手动复制。');
    setTimeout(() => setCopyMessage(''), 2400);
  };

  const closeTraceModal = () => {
    setTraceModal({ open: false, order: null, trace: null });
    setTraceError('');
    setTraceLoading(false);
  };

  const openLogisticsTrace = async (order) => {
    setTraceModal({ open: true, order, trace: null });
    setTraceLoading(true);
    setTraceError('');
    try {
      const trace = await dataProvider.getOrderLogisticsTrace(order);
      setTraceModal({ open: true, order, trace });
    } catch (traceLoadError) {
      setTraceError(traceLoadError.message || '物流轨迹查询失败，请稍后重试。');
    } finally {
      setTraceLoading(false);
    }
  };

  const handleManualOrderRefresh = async () => {
    const storeId = query.storeId || selectedStoreId;
    if (!storeId) {
      setRefreshNotice('请先选择当前店铺，再更新 Naver 订单。');
      return;
    }
    setRefreshingOrders(true);
    setRefreshNotice('正在更新 Naver 订单...');
    try {
      const result = await dataProvider.manualRefreshNaverOrders({
        storeId,
        maxCount: 20,
        hours: 24,
      });
      const fallback = `订单更新完成：新增 ${result.createdCount}，更新 ${result.updatedCount}，跳过 ${result.skippedCount}。不会修改平台订单。`;
      setRefreshNotice(result.message || fallback);
      setRefreshKey((current) => current + 1);
    } catch (refreshError) {
      setRefreshNotice(refreshError.message || 'Naver 订单更新失败，请联系管理员检查店铺连接。');
    } finally {
      setRefreshingOrders(false);
    }
  };

  const handleSingleOrderDetailRefresh = async (order) => {
    if (!order) return;
    const platform = String(order.rawPlatform || order.platform || '').toLowerCase();
    if (platform !== 'naver') {
      setDetailRefreshNotice('当前只支持 Naver 订单读取官方详情刷新。');
      return;
    }
    setDetailRefreshing(true);
    setDetailRefreshNotice('正在读取 Naver 官方订单详情...');
    try {
      const result = await dataProvider.refreshSingleNaverOrderDetail(order);
      const refreshedOrder = result.order ? normalizedOrder(result.order) : null;
      if (refreshedOrder) {
        setRows((current) => current.map((item) => (String(item.id) === String(refreshedOrder.id) ? refreshedOrder : item)));
        setActiveOrder(refreshedOrder);
      } else {
        setRefreshKey((current) => current + 1);
      }
      setDetailRefreshNotice(result.message || '订单详情已更新；不会修改平台订单。');
    } catch (singleRefreshError) {
      setDetailRefreshNotice(singleRefreshError.message || '订单详情更新失败，请联系管理员检查店铺连接。');
    } finally {
      setDetailRefreshing(false);
    }
  };

  const switchViewMode = (nextMode) => {
    setViewMode(nextMode);
    setActiveOrder(null);
    setDetailRefreshNotice('');
    if (nextMode === 'historical') setHistoryPage(1);
  };

  const applyHistoryFilters = () => {
    const start = new Date(`${historyDraft.startAt}T00:00:00`);
    const end = new Date(`${historyDraft.endAt}T00:00:00`);
    if (!historyDraft.startAt || !historyDraft.endAt || end < start) {
      setHistoryError('请选择有效的历史订单开始和结束日期。');
      return;
    }
    if ((end.getTime() - start.getTime()) / 86400000 > 31) {
      setHistoryError('单次历史订单查询和回填最多支持 31 天。');
      return;
    }
    setHistoryError('');
    setHistoryPage(1);
    setHistoryQuery({ ...historyDraft });
  };

  const resetHistoryFilters = () => {
    const next = initialHistoryFilters(historyDraft.storeId);
    setHistoryDraft(next);
    setHistoryPage(1);
    setHistoryQuery(next);
  };

  const runHistoricalBackfill = async () => {
    const storeId = historyQuery.storeId || selectedStoreId;
    if (!historyOnboarding || String(historyOnboarding.storeId) !== String(storeId)) {
      setHistoryBackfillNotice(historyOnboardingReason || '当前店铺无法确认安全的历史回填任务。');
      return;
    }
    setHistoryBackfilling(true);
    setHistoryBackfillNotice('正在读取历史订单并写入本地记录，不会修改 Naver 平台订单...');
    try {
      const result = await dataProvider.historicalOrderBackfill(historyOnboarding.id, {
        start_at: `${historyQuery.startAt}T00:00:00+09:00`,
        end_at: `${historyQuery.endAt}T23:59:59+09:00`,
      });
      const count = Number(result.backfill?.created || 0) + Number(result.backfill?.updated || 0);
      setHistoryBackfillNotice(`历史订单本地回填完成，共处理 ${count} 条；未执行平台写入。`);
      setHistoryQuery({ ...historyQuery });
    } catch (backfillError) {
      setHistoryBackfillNotice(backfillError.message || '历史订单回填失败，请稍后重试。');
    } finally {
      setHistoryBackfilling(false);
    }
  };

  const pageRows = rows.slice((query.page - 1) * PAGE_SIZE, query.page * PAGE_SIZE);
  const renderTrackingDetail = (order) => {
    if (!hasDisplayValue(order?.trackingNo)) return <span>-</span>;
    return (
      <span className="inline-action-group">
        <span>{order.trackingNo}</span>
        <button className="button ghost compact" type="button" onClick={() => openLogisticsTrace(order)}>
          查询物流轨迹
        </button>
      </span>
    );
  };

  return (
    <>
      <div className="workbench-view-switch" role="tablist" aria-label="订单视图">
        <button type="button" className={viewMode === 'current' ? 'active' : ''} onClick={() => switchViewMode('current')}>当前订单</button>
        <button type="button" className={viewMode === 'historical' ? 'active' : ''} onClick={() => switchViewMode('historical')}>历史订单</button>
      </div>
      {viewMode === 'current' ? (
        <>
          <PageHeader
        title="订单管理"
        description="搜索、筛选和查看订单详情。需要发货时，请进入仓库发货核对并提交物流信息。"
        actions={(
          <>
            <button className="button primary" type="button" onClick={handleManualOrderRefresh} disabled={refreshingOrders}>
              {refreshingOrders ? '正在更新' : '更新平台订单'}
            </button>
            <Link className="button ghost" to="/shipping">进入仓库发货</Link>
          </>
        )}
      />

      {refreshNotice ? <div className="form-info">{refreshNotice}</div> : null}

      <div className="summary-grid">
        <SummaryCard title="订单列表" value={summary.total} note="当前筛选结果" tone="info" />
        <SummaryCard title="待发货" value={summary.pending} note="进入仓库发货处理" tone={summary.pending ? 'warning' : 'success'} />
        <SummaryCard title="已发货" value={summary.shipped} note="系统已保存发货记录" tone="success" />
        <SummaryCard title="异常订单" value={summary.abnormal} note="取消/退货/换货只做提醒" tone={summary.abnormal ? 'danger' : 'success'} />
      </div>

      <FilterPanel>
        <div className="card-title">
          <div>
            <h2>订单状态分组</h2>
            <p>共 {rows.length} 条订单，先处理新订单和待发货，再查看取消、退货、换货和异常订单。</p>
          </div>
        </div>
        <div className="tab-row">
          {statusTabs.map((item) => (
            <button
              type="button"
              key={item.key || 'all'}
              className={draft.status === item.key ? 'active' : ''}
              onClick={() => {
                const next = { ...draft, status: item.key, page: 1 };
                setDraft(next);
                setQuery(next);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        <SearchBar
          value={draft.keyword}
          onChange={(keyword) => setDraft({ ...draft, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索订单号、商品、收件人、运单号"
        >
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
          <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
            {statusTabs.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {storeError ? <EmptyState title="店铺信息不可用" description={storeError} /> : null}
        {error ? <EmptyState title="订单数据加载失败" description={error} /> : null}
        {copyMessage ? <div className="form-info">{copyMessage}</div> : null}
        <DataTable
          columns={columns}
          rows={pageRows}
          loading={loading || storeLoading}
          rowKey="id"
          renderActions={(row) => (
            <>
              <button type="button" onClick={() => setActiveOrder(row)}>详情</button>
              <button type="button" onClick={() => handleCopy(row)}>复制收件信息</button>
              <Link to="/shipping">仓库发货</Link>
              <button type="button" onClick={() => openNote(row)}>内部备注</button>
              <button type="button" disabled title="暂未开放">平台处理暂未开放</button>
            </>
          )}
        />
        {!error ? (
          <Pagination
            page={query.page}
            pageSize={PAGE_SIZE}
            total={rows.length}
            onChange={(page) => setQuery({ ...query, page })}
          />
        ) : null}
          </section>
        </>
      ) : (
        <>
          <PageHeader
            title="历史订单"
            description="用于审计和查询已经回填到本地的历史订单。此视图不提供平台更新、发货、复制收件信息、内部备注或智能写作操作。"
          />
          <FilterPanel>
            <div className="card-title">
              <div>
                <h2>历史订单筛选</h2>
                <p>日期范围为必填项，单次最多 31 天；筛选和分页均由服务端执行。</p>
              </div>
            </div>
            <div className="order-filters">
              <FormField label="店铺">
                <select value={historyDraft.storeId} onChange={(event) => setHistoryDraft({ ...historyDraft, storeId: event.target.value })}>
                  <option value="">当前选中店铺</option>
                  {stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}
                </select>
              </FormField>
              <FormField label="开始日期" required>
                <input type="date" value={historyDraft.startAt} onChange={(event) => setHistoryDraft({ ...historyDraft, startAt: event.target.value })} />
              </FormField>
              <FormField label="结束日期" required>
                <input type="date" value={historyDraft.endAt} onChange={(event) => setHistoryDraft({ ...historyDraft, endAt: event.target.value })} />
              </FormField>
              <FormField label="订单号">
                <input value={historyDraft.orderId} onChange={(event) => setHistoryDraft({ ...historyDraft, orderId: event.target.value })} />
              </FormField>
              <FormField label="商品订单号">
                <input value={historyDraft.productOrderId} onChange={(event) => setHistoryDraft({ ...historyDraft, productOrderId: event.target.value })} />
              </FormField>
              <FormField label="商品编号">
                <input value={historyDraft.productId} onChange={(event) => setHistoryDraft({ ...historyDraft, productId: event.target.value })} />
              </FormField>
              <FormField label="商品名称">
                <input value={historyDraft.productName} onChange={(event) => setHistoryDraft({ ...historyDraft, productName: event.target.value })} />
              </FormField>
              <FormField label="订单状态">
                <input value={historyDraft.status} placeholder="例如 PAID" onChange={(event) => setHistoryDraft({ ...historyDraft, status: event.target.value })} />
              </FormField>
              <FormField label="买家姓名（需权限）">
                <input value={historyDraft.buyerName} onChange={(event) => setHistoryDraft({ ...historyDraft, buyerName: event.target.value })} />
              </FormField>
              <FormField label="买家电话（需权限）">
                <input value={historyDraft.buyerPhone} onChange={(event) => setHistoryDraft({ ...historyDraft, buyerPhone: event.target.value })} />
              </FormField>
              <div className="inline-action-group">
                <button className="button primary" type="button" onClick={applyHistoryFilters}>查询</button>
                <button className="button ghost" type="button" onClick={resetHistoryFilters}>重置</button>
              </div>
            </div>
          </FilterPanel>
          <section className="content-card historical-backfill-panel">
            <div className="card-title">
              <div>
                <h2>历史订单本地回填</h2>
                <p>{historyOnboardingReason || '已确认当前店铺的 Naver 添加任务，可按当前日期范围执行本地回填。'}</p>
              </div>
              <button
                className="button ghost"
                type="button"
                onClick={runHistoricalBackfill}
                disabled={historyBackfilling || !historyOnboarding}
              >
                {historyBackfilling ? '正在回填...' : '回填历史订单'}
              </button>
            </div>
            {historyBackfillNotice ? <div className="form-info">{historyBackfillNotice}</div> : null}
          </section>
          <section className="content-card history-orders-table">
            {storeError ? <EmptyState title="店铺信息不可用" description={storeError} /> : null}
            {historyError ? <EmptyState title="历史订单加载失败" description={historyError} /> : null}
            <DataTable
              columns={columns}
              rows={historyRows}
              loading={historyLoading || storeLoading}
              rowKey="id"
              renderActions={(row) => <button type="button" onClick={() => setActiveOrder(row)}>详情</button>}
            />
            {!historyError ? (
              <Pagination
                page={historyPage}
                pageSize={PAGE_SIZE}
                total={historyTotal}
                onChange={setHistoryPage}
              />
            ) : null}
          </section>
        </>
      )}

      <DetailModal
        open={Boolean(activeOrder)}
        title={activeOrder ? `订单详情 · ${activeOrder.orderNo}` : '订单详情'}
        onClose={() => {
          setActiveOrder(null);
          setDetailRefreshNotice('');
        }}
        width="min(980px, 94vw)"
      >
        {activeOrder ? (
          <>
            <div className="detail-product">
              <ProductCell order={activeOrder} detail />
            </div>
            <div className="detail-grid">
              {[
                ['平台', activeOrder.platform],
                ['店铺', activeOrder.store],
                ['数量', activeOrder.quantity],
                ['订单金额', `${Number(activeOrder.amount || 0).toLocaleString()} ${activeOrder.currency || 'KRW'}`],
                ['订单状态', <StatusBadge value={activeOrder.statusText} />],
                ['发货状态', <StatusBadge value={activeOrder.shippingStatus} />],
                ['快递公司', activeOrder.logisticsCompany],
                ['运单号', renderTrackingDetail(activeOrder)],
                ['记录状态', activeOrder.sourceInfo.label],
                ['内部备注', notes[activeOrder.orderNo] || '暂无'],
              ].filter((_, index) => viewMode === 'current' || index < 9).map(([label, value]) => (
                <div className="detail-item" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            {viewMode === 'current' ? (
              <>
                <section className="content-card">
              <h3>收件信息</h3>
              <p className="mock-sync-note">复制收件信息仅用于发货准备；更新订单详情不会修改平台订单。</p>
              <pre className="readonly-code">{copyReceiverText(activeOrder)}</pre>
              {detailRefreshNotice ? <div className="form-info">{detailRefreshNotice}</div> : null}
              <div className="inline-action-group">
                <button className="button ghost" type="button" onClick={() => handleCopy(activeOrder)}>复制收件信息</button>
                <button
                  className="button ghost"
                  type="button"
                  onClick={() => handleSingleOrderDetailRefresh(activeOrder)}
                  disabled={detailRefreshing}
                >
                  {detailRefreshing ? '正在刷新详情' : '刷新订单详情'}
                </button>
              </div>
                </section>
                <section className="content-card">
              <h3>暂未开放操作</h3>
              <p>取消、退货和换货需要在平台后台处理；发货请进入仓库发货，核对物流信息后人工确认提交。</p>
                </section>
              </>
            ) : (
              <section className="content-card">
                <h3>历史记录用途</h3>
                <p className="mock-sync-note">此订单仅用于历史审计和查询，不提供平台更新、仓库发货、收件信息复制、内部备注或智能操作。</p>
              </section>
            )}
          </>
        ) : (
          <EmptyState title="暂无订单详情" description="请选择一条订单查看详情。" />
        )}
      </DetailModal>

      <Modal
        open={traceModal.open}
        title={traceModal.order ? `物流轨迹 · ${traceModal.order.trackingNo || traceModal.order.orderNo}` : '物流轨迹'}
        onClose={closeTraceModal}
        showFooter={false}
        width="min(720px, 92vw)"
      >
        {traceLoading ? <div className="table-state"><span className="spinner" />正在查询物流轨迹...</div> : null}
        {!traceLoading && traceError ? <EmptyState title="物流轨迹查询失败" description={traceError} /> : null}
        {!traceLoading && !traceError && traceModal.trace ? (
          <div className="trace-panel">
            <div className="detail-grid">
              {[
                ['快递公司', traceModal.trace.deliveryCompany || traceModal.order?.logisticsCompany || '-'],
                ['运单号', traceModal.trace.trackingNumber || traceModal.order?.trackingNo || '-'],
                ['记录状态', traceModal.trace.trackingSource === 'shipping_tracking_import_rows' ? '仓库回传的物流信息' : '订单物流信息'],
                ['实时轨迹', traceModal.trace.realtimeTrackingOpen ? '可查询' : '暂未提供实时轨迹'],
              ].map(([label, value]) => (
                <div className="detail-item" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <p className="mock-sync-note">{traceModal.trace.message || '暂未提供实时快递轨迹，当前显示已保存的物流信息。'}</p>
            <div className="timeline">
              {(traceModal.trace.events || []).map((event) => (
                <div className="timeline-item" key={event.id || `${event.time}-${event.label}`}>
                  <span className="timeline-dot" />
                  <div className="timeline-content">
                    <div className="timeline-head">
                      <strong>{event.label}</strong>
                      {event.time ? <time>{event.time}</time> : null}
                    </div>
                    <p>{event.description}</p>
                    {event.source ? <span className="period-chip">{event.source}</span> : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={noteModal.open}
        title={noteModal.order ? `内部备注 · ${noteModal.order.orderNo}` : '内部备注'}
        onClose={() => setNoteModal({ open: false, order: null, note: '' })}
        onConfirm={saveNote}
        confirmText="保存内部备注"
      >
        <FormField label="备注内容">
          <input
            value={noteModal.note ?? notes[noteModal.order?.orderNo] ?? ''}
            onChange={(event) => setNoteModal({ ...noteModal, note: event.target.value })}
            placeholder="仅供内部查看，不会修改平台订单"
          />
        </FormField>
        <p className="mock-sync-note">内部备注仅供团队查看，不会修改平台订单。</p>
      </Modal>
    </>
  );
}
