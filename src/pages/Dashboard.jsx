import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import SummaryCard from '../components/common/SummaryCard';
import StatusBadge from '../components/common/StatusBadge';
import StoreSyncStatusPanel from '../components/common/StoreSyncStatusPanel';
import { useAuthContext } from '../context/AuthContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { metricDisplayValue } from '../services/adapters';

const WORKBENCH_SECTIONS = [
  ['urgent', '紧急处理', 'danger'],
  ['action_required', '现在处理', 'warning'],
  ['waiting', '等待中', 'info'],
  ['completed_today', '今日完成', 'success'],
];
const SOURCE_LABELS = {
  orders: '订单',
  shipping: '仓库发货',
  customer_inquiries: '客户咨询',
};

function rowsOf(result) { return result?.data || result?.items || []; }

async function loadOr(loader, fallback) {
  try { return await loader(); } catch { return fallback; }
}

function WorkbenchTask({ task, onOpen }) {
  return (
    <Link className={`workbench-task ${task.stale ? 'stale' : ''}`} to={task.actionPath} onClick={() => onOpen(task)}>
      <strong>{task.title}</strong>
      <small>{task.storeName} · {task.platform}</small>
      <p>{task.description}</p>
      <div className="workbench-task-action">
        {task.stale ? <span>数据可能已过期</span> : null}
        <b>{task.actionLabel}</b>
      </div>
    </Link>
  );
}

function Metric({ value }) {
  const display = metricDisplayValue(value);
  return <span className={`overview-metric ${display === '?' ? 'unknown' : ''}`}>{display}</span>;
}

const storeColumns = [
  { key: 'storeName', title: '店铺', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'connectionStatus', title: '连接状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'todayOrders', title: '今日订单', render: (_, row) => <Metric value={row.metrics.todayOrders} /> },
  { key: 'pendingShipments', title: '待发货', render: (_, row) => <Metric value={row.metrics.pendingShipments} /> },
  { key: 'abnormalOrders', title: '异常订单', render: (_, row) => <Metric value={row.metrics.abnormalOrders} /> },
  { key: 'inventoryAlerts', title: '库存预警', render: (_, row) => <Metric value={row.metrics.inventoryAlerts} /> },
  { key: 'lastSyncAt', title: '最近同步' },
];

const recentOrderColumns = [
  { key: 'orderNo', title: '订单号' },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'status', title: '订单状态' },
  { key: 'createdAt', title: '下单时间' },
];

const activityColumns = [
  { key: 'time', title: '时间' },
  { key: 'module', title: '模块' },
  { key: 'summary', title: '内容' },
  { key: 'status', title: '状态' },
];

export default function Dashboard() {
  const { canAccessStore } = useAuthContext();
  const { selectedStoreId, setSelectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [view, setView] = useState('all');
  const [state, setState] = useState({ loading: true, error: '', overview: null, orders: [], activities: [] });

  useEffect(() => {
    let cancelled = false;
    if (storeLoading) return () => { cancelled = true; };
    if (storeError) {
      setState((current) => ({ ...current, loading: false, error: storeError }));
      return () => { cancelled = true; };
    }
    async function load() {
      const scope = isBackendSource && selectedStoreId ? { storeId: selectedStoreId } : {};
      try {
        const overview = await dataProvider.getStoreOverview({ includeInactive: false });
        const [orders, activities] = await Promise.all([
          loadOr(() => dataProvider.getOrders({ ...scope, page: 1, pageSize: 100 }), { data: [] }),
          loadOr(() => dataProvider.getOperationAuditLogs({ ...scope, page: 1, pageSize: 8 }), { data: [] }),
        ]);
        if (!cancelled) setState({ loading: false, error: '', overview, orders: rowsOf(orders), activities: rowsOf(activities) });
      } catch (requestError) {
        if (!cancelled) setState({
          loading: false,
          error: requestError.message || '今日工作台暂时无法加载',
          overview: null,
          orders: [],
          activities: [],
        });
      }
    }
    setState((current) => ({ ...current, loading: true, error: '' }));
    load();
    return () => { cancelled = true; };
  }, [selectedStoreId, storeError, storeLoading]);

  if (state.loading) return <div className="table-state"><span className="spinner" />正在加载首页工作台...</div>;

  const overviewRows = state.overview?.stores || [];
  const operatorWorkbench = state.overview?.operatorWorkbench || { summary: {}, sections: {}, sources: {} };
  const selectedStore = overviewRows.find((row) => String(row.storeId) === String(selectedStoreId));
  const selectedSummary = selectedStore?.workbenchSummary || {};
  const visibleWorkbench = view === 'single'
    ? { ...operatorWorkbench, summary: selectedSummary, sections: Object.fromEntries(Object.entries(operatorWorkbench.sections || {}).map(([key, tasks]) => [key, tasks.filter((task) => String(task.storeId) === String(selectedStoreId))])) }
    : operatorWorkbench;
  const sourceNotices = Object.entries(operatorWorkbench.sources || {}).filter(([, source]) => ['partial', 'blocked'].includes(source.sourceStatus));
  const openTask = (task) => { setSelectedStoreId(task.storeId); };

  return (
    <>
      <PageHeader title="今日工作台" description="先处理今天的发货、异常订单、客户咨询和库存问题。" />
      {state.error ? <EmptyState title="首页数据加载失败" description={state.error} /> : null}
      <div className="workbench-view-switch" role="group" aria-label="工作台视图">
        <button type="button" className={view === 'all' ? 'active' : ''} onClick={() => setView('all')}>全部授权店铺</button>
        <button type="button" className={view === 'single' ? 'active' : ''} onClick={() => setView('single')}>单店</button>
      </div>
      <div className="summary-grid workbench-summary">
        <SummaryCard title="紧急处理" value={visibleWorkbench.summary.urgent || 0} note="异常和阻断事项" tone={visibleWorkbench.summary.urgent ? 'danger' : 'success'} />
        <SummaryCard title="现在处理" value={visibleWorkbench.summary.actionRequired || 0} note="当前可以继续的工作" tone={visibleWorkbench.summary.actionRequired ? 'warning' : 'success'} />
        <SummaryCard title="等待中" value={visibleWorkbench.summary.waiting || 0} note="等待仓库或管理员" tone="info" />
        <SummaryCard title="今日完成" value={visibleWorkbench.summary.completedToday || 0} note="按业务日期统计" tone="success" />
      </div>
      <StoreSyncStatusPanel
        rows={overviewRows}
        attentionSummary={state.overview?.automaticReadAttentionSummary}
        canManageRecovery={(storeId) => (
          canAccessStore(storeId, 'credentials.manage')
          && canAccessStore(storeId, 'platform.sync')
        )}
      />
      <section className="content-card">
        <div className="card-title"><div><h2>今天先处理什么</h2><p>任务分类和优先级由后端工作台聚合提供。</p></div></div>
        {sourceNotices.length ? <div className="form-info source-notices">
          {sourceNotices.map(([key, source]) => (
            <span key={key}>
              {source.sourceStatus === 'blocked' ? '当前无法读取' : '部分店铺暂时无法读取'}{SOURCE_LABELS[key] || '业务数据'}
              {source.failedStoreCount ? `，涉及 ${source.failedStoreCount} 个店铺` : ''}
            </span>
          ))}
        </div> : null}
        <div className="workbench-grid">
          {WORKBENCH_SECTIONS.map(([key, label, tone]) => {
            const tasks = visibleWorkbench.sections?.[key] || [];
            return <section className={`workbench-section ${tone}`} key={key}>
              <div className="workbench-section-title"><h3>{label}</h3><span>{tasks.length}</span></div>
              {tasks.length ? tasks.map((task) => <WorkbenchTask key={task.taskId} task={task} onOpen={openTask} />) : <p className="workbench-empty">当前没有需要处理的事项</p>}
            </section>;
          })}
        </div>
      </section>
      <section className="content-card">
        <div className="card-title"><div><h2>按店铺查看</h2><p>选择店铺后查看该店铺的聚合任务和数据状态。</p></div></div>
        <div className="dashboard-store-table"><DataTable columns={storeColumns} rows={overviewRows} renderActions={(row) => <><button type="button" onClick={() => setSelectedStoreId(row.storeId)}>设为当前</button><Link to="/orders" onClick={() => setSelectedStoreId(row.storeId)}>订单</Link><Link to="/shipping" onClick={() => setSelectedStoreId(row.storeId)}>发货</Link></>} /></div>
      </section>
      <section className="content-card">
        <div className="card-title"><div><h2>核心快捷入口</h2><p>常用任务集中在这里。</p></div></div>
        <div className="business-capability-grid compact"><Link className="business-capability-card info" to="/orders">处理订单</Link><Link className="business-capability-card info" to="/shipping">仓库发货</Link><Link className="business-capability-card info" to="/customer-service">客户咨询</Link><Link className="business-capability-card info" to="/inventory">库存预警</Link></div>
      </section>
      <section className="panel-grid">
        <article className="content-card"><div className="card-title"><h2>最近订单</h2><Link className="button ghost" to="/orders">查看全部</Link></div><DataTable columns={recentOrderColumns} rows={state.orders.slice(0, 6)} /></article>
        <article className="content-card"><div className="card-title"><h2>最近操作</h2></div>{state.activities.length ? <DataTable columns={activityColumns} rows={state.activities.slice(0, 6)} /> : <EmptyState title="暂无最近操作" description="当前没有可展示的本地操作记录。" />}</article>
      </section>
    </>
  );
}
