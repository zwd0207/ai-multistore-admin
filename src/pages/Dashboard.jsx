import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import { metricDisplayValue } from '../services/adapters';
import dataProvider, { isBackendSource } from '../services/dataProvider';

const money = (value, currency = 'KRW') => `${Number(value || 0).toLocaleString()} ${currency}`;

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

function WorkbenchTask({ task }) {
  return (
    <Link className={`workbench-task ${task.stale ? 'stale' : ''}`} to={task.actionPath}>
      <div>
        <strong>{task.title}</strong>
        <p>{task.description}</p>
      </div>
      <div className="workbench-task-action">
        {task.stale ? <span>数据可能已过期</span> : null}
        <b>{task.actionLabel}</b>
      </div>
    </Link>
  );
}

const WORKBENCH_SECTIONS = [
  ['urgent', '紧急处理', 'danger'],
  ['action_required', '现在处理', 'warning'],
  ['waiting', '等待中', 'info'],
  ['completed_today', '今日完成', 'success'],
];

export default function Dashboard() {
  const {
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
        activities,
      ] = await Promise.all([
        safeLoad(() => dataProvider.getDashboardSummary(commonParams), {}),
        safeLoad(() => dataProvider.getStoreOverview({ includeInactive: false }), null),
        safeLoad(() => dataProvider.getOrders({ ...commonParams, page: 1, pageSize: 100 }), { data: [] }),
        safeLoad(() => dataProvider.getOperationAuditLogs({ ...commonParams, page: 1, pageSize: 8 }), { data: [] }),
      ]);
      if (!cancelled) {
        setState({
          loading: false,
          error: '',
          summary,
          overview,
          orders: safeRows(orders),
          activities: safeRows(activities),
        });
      }
    }

    load();
    return () => { cancelled = true; };
  }, [selectedStoreId, storeError, storeLoading, refreshKey]);

  const overviewRows = state.overview?.stores || [];
  const operatorWorkbench = state.summary.operatorWorkbench || { summary: {}, sections: {}, sources: {} };
  const blockedSources = [
    ['orders', '订单'],
    ['shipping', '仓库发货'],
    ['customer_inquiries', '客户咨询'],
  ].filter(([key]) => operatorWorkbench.sources[key]?.sourceStatus === 'blocked').map(([, label]) => label);

  const runAllStoreSync = async () => {
    if (overviewAction.running) return;
    setOverviewAction({ running: true, message: '正在更新全部店铺数据...' });
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
          ? `店铺数据更新完成，${failed} 个店铺需要管理员检查连接`
          : `店铺数据更新完成，${skipped} 个店铺暂时无法更新`,
      });
      setRefreshKey((current) => current + 1);
    } catch (error) {
      setOverviewAction({ running: false, message: error.message || '店铺数据更新失败，请联系管理员检查连接。' });
    }
  };

  const runSingleStoreSync = async (row) => {
    if (overviewAction.running) return;
    setOverviewAction({ running: true, message: `${row.storeName} 正在更新...` });
    try {
      const result = await dataProvider.runManualStoreSync({
        storeId: row.storeId,
        platforms: [row.rawPlatform],
        includeProducts: true,
        includeOrders: true,
        includeCustomerInquiries: true,
      });
      setOverviewAction({ running: false, message: `${row.storeName}：${result.statusLabel || '更新完成'}` });
      setRefreshKey((current) => current + 1);
    } catch (error) {
      setOverviewAction({ running: false, message: `${row.storeName}：${error.message || '更新失败，请联系管理员检查连接。'}` });
    }
  };

  if (state.loading) return <div className="table-state"><span className="spinner" />正在加载首页工作台...</div>;

  return (
    <>
      <PageHeader
        title="今日工作台"
        description="先处理今天的发货、异常订单、客户咨询和库存问题。"
      />

      {state.error ? <EmptyState title="首页数据加载失败" description={state.error} /> : null}

      <div className="summary-grid workbench-summary">
        <SummaryCard title="紧急处理" value={operatorWorkbench.summary.urgent || 0} note="异常和阻断事项" tone={operatorWorkbench.summary.urgent ? 'danger' : 'success'} />
        <SummaryCard title="现在处理" value={operatorWorkbench.summary.actionRequired || 0} note="当前可以继续的工作" tone={operatorWorkbench.summary.actionRequired ? 'warning' : 'success'} />
        <SummaryCard title="等待中" value={operatorWorkbench.summary.waiting || 0} note="等待仓库或管理员" tone="info" />
        <SummaryCard title="今日完成" value={operatorWorkbench.summary.completedToday || 0} note="按韩国业务日期统计" tone="success" />
      </div>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>今天先处理什么</h2>
            <p>按订单履约优先级排序，帮助普通运营从首页直接进入当天工作。</p>
          </div>
        </div>
        {blockedSources.length ? (
          <div className="form-info">{blockedSources.join('、')}暂时不可用，其他来源的待办仍可正常处理。</div>
        ) : null}
        <div className="workbench-grid">
          {WORKBENCH_SECTIONS.map(([key, label, tone]) => {
            const tasks = operatorWorkbench.sections[key] || [];
            return (
              <section className={`workbench-section ${tone}`} key={key}>
                <div className="workbench-section-title"><h3>{label}</h3><span>{tasks.length}</span></div>
                {tasks.length ? tasks.map((task) => <WorkbenchTask key={task.taskId} task={task} />) : (
                  <p className="workbench-empty">当前没有需要处理的事项</p>
                )}
              </section>
            );
          })}
        </div>
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>按店铺查看</h2>
            <p>选择店铺后，可继续处理该店铺的订单、仓库发货和客户咨询。“待更新”表示需要管理员检查店铺连接；最近一次同步无法确认时也会明确提示。</p>
          </div>
          <div className="overview-actions">
            <button type="button" className="button primary" onClick={runAllStoreSync} disabled={overviewAction.running}>
              {overviewAction.running ? '更新中...' : '更新全部店铺数据'}
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
              <button type="button" onClick={() => runSingleStoreSync(row)}>更新数据</button>
              <Link to="/orders" onClick={() => setSelectedStoreId(row.storeId)}>订单</Link>
              <Link to="/shipping" onClick={() => setSelectedStoreId(row.storeId)}>发货</Link>
            </>
          )}
        />
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>核心快捷入口</h2>
            <p>常用任务集中在这里，方便快速开始当天工作。</p>
          </div>
        </div>
        <div className="business-capability-grid compact">
          <QuickLink to="/orders" title="处理订单" note="搜索订单、查看详情、复制收件信息。" />
          <QuickLink to="/shipping" title="仓库发货" note="核对规格、仓库货号和物流信息。" />
          <QuickLink to="/customer-service" title="客户咨询" note="查看客户问题并准备回复。" />
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
