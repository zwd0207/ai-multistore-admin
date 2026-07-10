import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import { metricDisplayValue } from '../services/adapters';
import dataProvider, { DATA_SOURCE, isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource, getDangerousActionState } from '../utils/coreErpContract';
import { getKstTodayString } from '../utils/time';

const money = (value, currency = 'KRW') => `${Number(value || 0).toLocaleString()} ${currency}`;

function rowDate(value) {
  return String(value || '').slice(0, 10);
}

function orderStatusText(order = {}) {
  return String(order.status || order.order_status || order.delivery_status_label_zh || order.deliveryStatusLabelZh || '').trim();
}

function isPendingShipment(order = {}) {
  const text = `${orderStatusText(order)} ${order.delivery_status || order.deliveryStatus || ''}`.toLowerCase();
  return ['待发货', '新订单', '已付款', 'ready', 'payed', 'place_product_order', 'delivery_ready'].some((flag) => text.includes(flag.toLowerCase()));
}

function isAbnormalOrder(order = {}) {
  const text = `${orderStatusText(order)} ${order.claim_status || order.claimStatus || ''}`.toLowerCase();
  return ['取消', '退款', '退货', '换货', '异常', 'cancel', 'refund', 'return', 'exchange'].some((flag) => text.includes(flag.toLowerCase()));
}

function safeRows(result) {
  return result?.data || result?.items || [];
}

async function safeLoad(loader, fallback) {
  try {
    return await loader();
  } catch {
    return fallback;
  }
}

const recentOrderColumns = [
  { key: 'orderNo', title: '订单号', render: (value, row) => <strong>{value || row.external_order_id || row.id}</strong> },
  { key: 'platform', title: '平台', render: (value) => value || '-' },
  { key: 'store', title: '店铺', render: (value) => value || '-' },
  { key: 'product', title: '商品', render: (value, row) => value || row.productName || row.name || '-' },
  { key: 'amount', title: '金额', render: (value, row) => money(value || row.order_amount, row.currency || 'KRW') },
  { key: 'status', title: '订单状态', render: (value, row) => <StatusBadge value={value || row.order_status || row.delivery_status_label_zh} /> },
  { key: 'createdAt', title: '下单时间' },
];

function readableActivityText(value = '') {
  return String(value || '-')
    .replaceAll('Logistics mapping and stock', '物流库存编号和库存维护')
    .replaceAll('Naver product local sync batch', 'Naver 商品本地同步记录')
    .replaceAll('Naver selected existing order refresh', 'Naver 订单本地刷新记录')
    .replaceAll('local sync', '本地同步')
    .replaceAll('mapping', '映射')
    .replaceAll('stock', '库存');
}

const activityColumns = [
  { key: 'time', title: '时间' },
  { key: 'module', title: '模块', render: (value, row) => value || row.actionType || '-' },
  { key: 'objectName', title: '内容', render: (value, row) => readableActivityText(value || row.title || row.description) },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value || '本地记录'} /> },
];

function MetricCell({ metric }) {
  const display = metricDisplayValue(metric);
  const isUnknown = display === '?';
  return (
    <span className={`overview-metric ${isUnknown ? 'unknown' : ''}`} title={metric?.reason || ''}>
      {display}
    </span>
  );
}

function unknownNote(count, label) {
  return count ? `${count} 个店铺${label}最近一次同步无法确认` : '已确认店铺本地统计';
}

const storeOverviewColumns = [
  {
    key: 'storeName',
    title: '店铺',
    render: (value, row) => (
      <strong>
        {value}
        <span className="cell-subtitle">{row.ownerName || '未配置负责人'}</span>
      </strong>
    ),
  },
  { key: 'platform', title: '平台' },
  {
    key: 'connectionStatus',
    title: '连接状态',
    render: (value, row) => (
      <span title={row.connectionReason || ''}>
        <StatusBadge value={value} />
        {row.connectionReason ? <span className="cell-subtitle">{row.connectionReason}</span> : null}
      </span>
    ),
  },
  { key: 'todayOrders', title: '今日订单', render: (_, row) => <MetricCell metric={row.metrics.todayOrders} /> },
  { key: 'pendingShipments', title: '待发货', render: (_, row) => <MetricCell metric={row.metrics.pendingShipments} /> },
  { key: 'abnormalOrders', title: '异常订单', render: (_, row) => <MetricCell metric={row.metrics.abnormalOrders} /> },
  { key: 'inventoryAlerts', title: '库存预警', render: (_, row) => <MetricCell metric={row.metrics.inventoryAlerts} /> },
  { key: 'lastSyncAt', title: '最近同步' },
];

function QuickLink({ to, title, note }) {
  return (
    <Link className="business-capability-card info quick-entry-card" to={to}>
      <div className="business-capability-head">
        <strong>{title}</strong>
        <span>进入</span>
      </div>
      <p>{note}</p>
    </Link>
  );
}

function PriorityCard({
  title, count, note, to, tone = 'info',
}) {
  return (
    <Link className={`business-capability-card ${tone}`} to={to}>
      <div className="business-capability-head">
        <strong>{title}</strong>
        <span>{count}</span>
      </div>
      <p>{note}</p>
      <small>进入处理</small>
    </Link>
  );
}

export default function Dashboard() {
  const {
    selectedStore,
    selectedStoreId,
    setSelectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [state, setState] = useState({
    loading: true,
    error: '',
    summary: {},
    overview: null,
    orders: [],
    products: [],
    activities: [],
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [overviewAction, setOverviewAction] = useState({ running: false, message: '' });

  useEffect(() => {
    let cancelled = false;
    if (storeLoading) return () => { cancelled = true; };
    if (storeError) {
      setState((current) => ({ ...current, loading: false, error: storeError }));
      return () => { cancelled = true; };
    }

    async function load() {
      setState((current) => ({ ...current, loading: true, error: '' }));
      const commonParams = isBackendSource && selectedStoreId ? { storeId: selectedStoreId } : {};
      const [
        summary,
        overview,
        orders,
        products,
        activities,
      ] = await Promise.all([
        safeLoad(() => dataProvider.getDashboardSummary(commonParams), {}),
        safeLoad(() => dataProvider.getStoreOverview({ includeInactive: false }), null),
        safeLoad(() => dataProvider.getOrders({ ...commonParams, page: 1, pageSize: 100 }), { data: [] }),
        safeLoad(() => dataProvider.getProducts({ ...commonParams, page: 1, pageSize: 100 }), { data: [] }),
        safeLoad(() => dataProvider.getOperationAuditLogs({ ...commonParams, page: 1, pageSize: 8 }), { data: [] }),
      ]);
      if (!cancelled) {
        setState({
          loading: false,
          error: '',
          summary,
          overview,
          orders: safeRows(orders),
          products: safeRows(products),
          activities: safeRows(activities),
        });
      }
    }

    load();
    return () => { cancelled = true; };
  }, [selectedStoreId, storeError, storeLoading, refreshKey]);

  const metrics = useMemo(() => {
    const today = getKstTodayString();
    const todayOrders = state.orders.filter((item) => rowDate(item.createdAt || item.ordered_at) === today);
    const pendingShipment = state.orders.filter(isPendingShipment);
    const abnormalOrders = state.orders.filter(isAbnormalOrder);
    const inventoryAlerts = state.products.filter((item) => Number(item.stock ?? item.stock_quantity ?? 0) <= 5);
    const outOfStock = state.products.filter((item) => Number(item.stock ?? item.stock_quantity ?? 0) <= 0);
    const lowStock = state.products.filter((item) => {
      const stock = Number(item.stock ?? item.stock_quantity ?? 0);
      return stock > 0 && stock <= 5;
    });
    return {
      todayOrders,
      pendingShipment,
      abnormalOrders,
      inventoryAlerts,
      outOfStock,
      lowStock,
    };
  }, [state]);

  const sourceInfo = classifyCoreDataSource({ source_type: DATA_SOURCE === 'backend' ? 'local_saved' : 'mock' });
  const dangerousState = getDangerousActionState('shipment_writeback');
  const overviewSummary = state.overview?.summary || {};
  const overviewRows = state.overview?.stores || [];
  const hasOverview = overviewRows.length > 0;
  const todayOrderValue = hasOverview
    ? `${overviewSummary.todayOrderCount}${overviewSummary.ordersUnknownStoreCount ? ' + ?' : ''}`
    : metrics.todayOrders.length;
  const pendingShipmentValue = hasOverview
    ? `${overviewSummary.pendingShipmentCount}${overviewSummary.ordersUnknownStoreCount ? ' + ?' : ''}`
    : metrics.pendingShipment.length;
  const abnormalOrderValue = hasOverview
    ? `${overviewSummary.abnormalOrderCount}${overviewSummary.ordersUnknownStoreCount ? ' + ?' : ''}`
    : metrics.abnormalOrders.length;
  const inventoryAlertValue = hasOverview
    ? `${overviewSummary.inventoryAlertCount}${overviewSummary.inventoryUnknownStoreCount ? ' + ?' : ''}`
    : metrics.inventoryAlerts.length;

  const runAllStoreSync = async () => {
    if (overviewAction.running) return;
    setOverviewAction({ running: true, message: '全店铺同步中...' });
    try {
      const result = await dataProvider.runManualAllStoresSync({
        includeProducts: true,
        includeOrders: true,
        includeCustomerInquiries: true,
        includeInactive: false,
      });
      const failed = result.summary?.failedCount || 0;
      const skipped = result.summary?.skippedCount || 0;
      setOverviewAction({
        running: false,
        message: failed
          ? `全店铺同步完成，${failed} 个店铺需要处理连接状态`
          : `全店铺同步完成，跳过 ${skipped} 个暂未开放项`,
      });
      setRefreshKey((current) => current + 1);
    } catch (error) {
      setOverviewAction({ running: false, message: error.message || '全店铺同步失败' });
    }
  };

  const runSingleStoreSync = async (row) => {
    if (overviewAction.running) return;
    setOverviewAction({ running: true, message: `${row.storeName} 同步中...` });
    try {
      const result = await dataProvider.runManualStoreSync({
        storeId: row.storeId,
        platforms: [row.rawPlatform],
        includeProducts: true,
        includeOrders: true,
        includeCustomerInquiries: true,
      });
      setOverviewAction({ running: false, message: `${row.storeName}：${result.statusLabel || '同步完成'}` });
      setRefreshKey((current) => current + 1);
    } catch (error) {
      setOverviewAction({ running: false, message: `${row.storeName}：${error.message || '同步失败'}` });
    }
  };

  if (state.loading) return <div className="table-state"><span className="spinner" />正在加载首页工作台...</div>;

  return (
    <>
      <PageHeader
        title="核心运营工作台"
        description="全店铺先看连接与数据可信状态，再进入当前店铺处理订单、发货、商品和库存。"
        actions={(
          <>
            <span className="period-chip">{sourceInfo.label}</span>
            <span className="period-chip">KST / KRW</span>
          </>
        )}
      />

      {state.error ? <EmptyState title="首页数据加载失败" description={state.error} /> : null}

      <div className="summary-grid">
        <SummaryCard title="今日订单" value={todayOrderValue} note={hasOverview ? unknownNote(overviewSummary.ordersUnknownStoreCount, '订单') : '按韩国业务日期统计'} tone="info" />
        <SummaryCard title="待发货" value={pendingShipmentValue} note={hasOverview ? unknownNote(overviewSummary.ordersUnknownStoreCount, '待发货') : '建议先进入发货辅助核对'} tone={String(pendingShipmentValue).includes('?') || metrics.pendingShipment.length ? 'warning' : 'success'} />
        <SummaryCard title="异常订单" value={abnormalOrderValue} note={hasOverview ? unknownNote(overviewSummary.ordersUnknownStoreCount, '异常订单') : '取消/退货/换货/退款仅提醒'} tone={String(abnormalOrderValue).includes('?') || metrics.abnormalOrders.length ? 'danger' : 'success'} />
        <SummaryCard title="库存预警" value={inventoryAlertValue} note={hasOverview ? unknownNote(overviewSummary.inventoryUnknownStoreCount, '库存') : '缺货和低库存商品'} tone={String(inventoryAlertValue).includes('?') || metrics.inventoryAlerts.length ? 'warning' : 'success'} />
        <SummaryCard title="缺货商品" value={metrics.outOfStock.length} note="先确认补货或人工下架" tone={metrics.outOfStock.length ? 'danger' : 'success'} />
        <SummaryCard title="低库存商品" value={metrics.lowStock.length} note="再确认补货计划" tone={metrics.lowStock.length ? 'warning' : 'success'} />
      </div>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>全店铺运营总览</h2>
            <p>连接状态和核心指标放在同一张表；无法确认时显示“?”，原因标注“最近一次同步无法确认”，避免把 IP 白名单、权限或未接入造成的未知误判为 0。</p>
          </div>
          <div className="overview-actions">
            <button type="button" className="button primary" onClick={runAllStoreSync} disabled={overviewAction.running}>
              {overviewAction.running ? '同步中...' : '同步全部可用店铺'}
            </button>
            {overviewAction.message ? <span>{overviewAction.message}</span> : null}
          </div>
        </div>
        <DataTable
          columns={storeOverviewColumns}
          rows={overviewRows}
          renderActions={(row) => (
            <>
              <button type="button" onClick={() => setSelectedStoreId(row.storeId)}>设为当前</button>
              <button type="button" onClick={() => runSingleStoreSync(row)}>同步</button>
              <Link to="/orders" onClick={() => setSelectedStoreId(row.storeId)}>订单</Link>
              <Link to="/shipping" onClick={() => setSelectedStoreId(row.storeId)}>发货</Link>
            </>
          )}
        />
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>今天先处理什么</h2>
            <p>按订单履约优先级排序，帮助普通运营从首页直接进入当天工作。</p>
          </div>
        </div>
        <div className="business-capability-grid compact">
          <PriorityCard
            title="1. 处理待发货"
            count={`${metrics.pendingShipment.length} 单`}
            note="先核对商品规格、库存编号和物流单号，避免漏发或错发。"
            to="/shipping"
            tone={metrics.pendingShipment.length ? 'warning' : 'success'}
          />
          <PriorityCard
            title="2. 查看异常订单"
            count={`${metrics.abnormalOrders.length} 单`}
            note="取消、退货、换货和退款只做提醒，正式处理需人工确认。"
            to="/orders"
            tone={metrics.abnormalOrders.length ? 'danger' : 'success'}
          />
          <PriorityCard
            title="3. 补库存缺口"
            count={`${metrics.inventoryAlerts.length} 个`}
            note="先处理缺货，再处理低库存，最后回到商品管理复核状态。"
            to="/inventory"
            tone={metrics.inventoryAlerts.length ? 'warning' : 'success'}
          />
          <article className="business-capability-card muted">
            <div className="business-capability-head">
              <strong>平台写入边界</strong>
              <span>{dangerousState.label}</span>
            </div>
            <p>{dangerousState.note}</p>
            <small>{selectedStore?.name || '当前店铺'} · {sourceInfo.label}</small>
          </article>
        </div>
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>核心快捷入口</h2>
            <p>只打磨核心运营链路，其他模块先保持入口状态。</p>
          </div>
        </div>
        <div className="business-capability-grid compact">
          <QuickLink to="/orders" title="处理订单" note="搜索订单、查看详情、复制收件信息。" />
          <QuickLink to="/shipping" title="准备发货" note="核对规格、匹配库存编号、生成发货表格。" />
          <QuickLink to="/products" title="查看商品" note="检查售价、库存、平台状态和数据来源。" />
          <QuickLink to="/inventory" title="库存预警" note="确认缺货、低库存和补货建议。" />
        </div>
      </section>

      <section className="panel-grid">
        <article className="content-card">
          <div className="card-title">
            <div>
              <h2>最近订单</h2>
              <p>只展示系统当前可见订单，发货和售后写入未开放。</p>
            </div>
            <Link className="button ghost" to="/orders">查看全部</Link>
          </div>
          <DataTable columns={recentOrderColumns} rows={state.orders.slice(0, 6)} />
        </article>
        <article className="content-card">
          <div className="card-title">
            <div>
              <h2>最近操作</h2>
              <p>优先显示本地操作记录和审计摘要。</p>
            </div>
          </div>
          {state.activities.length ? (
            <DataTable columns={activityColumns} rows={state.activities.slice(0, 6)} />
          ) : (
            <EmptyState title="暂无最近操作" description="当前还没有可展示的本地操作记录。" />
          )}
        </article>
      </section>
    </>
  );
}
