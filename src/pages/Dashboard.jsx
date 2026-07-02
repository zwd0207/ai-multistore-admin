import { useEffect, useMemo, useState } from 'react';
import ActivityList from '../components/common/ActivityList';
import EmptyState from '../components/common/EmptyState';
import MockSyncPanel from '../components/common/MockSyncPanel';
import PageHeader from '../components/common/PageHeader';
import RiskPanel from '../components/common/RiskPanel';
import StatGrid from '../components/common/StatGrid';
import TodoList from '../components/common/TodoList';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { DATA_SOURCE, isBackendSource } from '../services/dataProvider';
import { buildPlatformBusinessStatus, businessCapabilityTitle } from '../utils/capabilityStatusMapper';
import {
  BUSINESS_TIME_LABEL,
  BUSINESS_TIME_ZONE,
  formatKstDate,
  formatKstDateTimeWithLabel,
} from '../utils/time';

const formatWon = (value) => `₩${Number(value || 0).toLocaleString()}`;

const emptyApiCapabilitySummary = {
  semanticNotice: 'mock 模式不维护后端连接检查记录。',
  platformSummary: [],
  storeResultSummary: [],
  attentionItems: [],
};

function createEmptyFinancialSummary() {
  return {
    available: false,
    orderSalesSummary: {
      totalOrders: 0,
      totalOrderSalesAmount: 0,
      currency: 'KRW',
      latestOrderedAt: null,
    },
    platformSalesDetailSummary: {
      salesDetailRows: 0,
      totalSaleAmount: 0,
      totalSettlementTargetAmount: 0,
      totalSettlementAmount: 0,
      latestRecognitionDate: null,
      currency: 'KRW',
    },
    settlementSummary: {
      settlementRows: 0,
      totalSettlementAmount: 0,
      totalFinalAmount: 0,
      totalServiceFee: 0,
      latestRevenueRecognitionYearMonth: null,
      latestSettlementDate: null,
      currency: 'KRW',
    },
    sourceBoundaries: {},
  };
}

function SellerTodoOverview({ summary, todos = [] }) {
  const priorityItems = [
    {
      id: 'orders',
      title: '待发货订单',
      description: `${summary.scopeOrderCount ?? summary.todayOrderCount ?? 0} 条订单需要持续关注发货和异常状态。`,
      status: 'info',
    },
    {
      id: 'customers',
      title: '待回复客服',
      description: summary.pendingCustomers > 0 ? `${summary.pendingCustomers} 条客户咨询需要处理。` : '暂无待回复客户咨询。',
      status: summary.pendingCustomers > 0 ? 'warning' : 'success',
    },
    {
      id: 'emails',
      title: '平台重要邮件',
      description: summary.unreadImportantEmails > 0 ? `${summary.unreadImportantEmails} 封重要邮件待查看。` : '暂无未读重要邮件。',
      status: summary.unreadImportantEmails > 0 ? 'warning' : 'success',
    },
    {
      id: 'appeals',
      title: '申诉资料',
      description: summary.pendingAppeals > 0 ? `${summary.pendingAppeals} 个申诉事项需要跟进。` : '暂无待处理申诉资料。',
      status: summary.pendingAppeals > 0 ? 'danger' : 'success',
    },
    {
      id: 'devices',
      title: '设备与账号',
      description: summary.riskEnvironments > 0 ? `${summary.riskEnvironments} 个设备或账号环境需要检查。` : '设备环境暂无明显风险。',
      status: summary.riskEnvironments > 0 ? 'danger' : 'success',
    },
    {
      id: 'naver-products',
      title: '商品预览结果',
      description: 'Naver 商品小批量预览已完成，预计新增 4 条、更新 1 条。正式批量同步未开放。',
      status: 'warning',
    },
  ];

  return (
    <article className="content-card">
      <div className="card-title">
        <div>
          <h2>今日待办</h2>
          <p>按卖家日常处理顺序展示订单、客服、邮件、申诉、设备和商品预览。</p>
        </div>
      </div>
      <TodoList items={todos.length ? todos : priorityItems} />
    </article>
  );
}

function FinancialSummarySection({ financialSummary }) {
  const summary = financialSummary || createEmptyFinancialSummary();
  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>销售与结算概览</h2>
          <p>销售额、平台销售明细和结算金额分开展示，避免把不同口径混在一起。</p>
        </div>
        <span className="period-chip">KRW</span>
      </div>
      <div className="financial-summary-grid">
        <article className="financial-card">
          <div className="financial-card-head">
            <h3>订单销售额</h3>
            <p>来自本地订单金额</p>
          </div>
          <strong>{formatWon(summary.orderSalesSummary.totalOrderSalesAmount)}</strong>
          <small>{summary.orderSalesSummary.totalOrders || 0} 条订单</small>
        </article>
        <article className="financial-card">
          <div className="financial-card-head">
            <h3>平台销售明细</h3>
            <p>用于核对平台确认金额</p>
          </div>
          <strong>{formatWon(summary.platformSalesDetailSummary.totalSaleAmount)}</strong>
          <small>{summary.platformSalesDetailSummary.salesDetailRows || 0} 条本地明细</small>
        </article>
        <article className="financial-card">
          <div className="financial-card-head">
            <h3>结算金额</h3>
            <p>不等同于利润或可提现余额</p>
          </div>
          <strong>{formatWon(summary.settlementSummary.totalSettlementAmount)}</strong>
          <small>{summary.settlementSummary.settlementRows || 0} 条结算明细</small>
        </article>
      </div>
      <TechnicalDetails
        description="这里保留销售和结算口径说明，默认不占用卖家工作台。"
        items={[
          { label: 'business_timezone', value: BUSINESS_TIME_ZONE },
          { label: 'sales_detail_rows', value: summary.platformSalesDetailSummary.salesDetailRows },
          { label: 'settlement_rows', value: summary.settlementSummary.settlementRows },
          { label: 'latest_ordered_at', value: formatKstDateTimeWithLabel(summary.orderSalesSummary.latestOrderedAt) },
          { label: 'latest_settlement_date', value: summary.settlementSummary.latestSettlementDate || '-' },
        ]}
      />
    </section>
  );
}

function PlatformBusinessStatusSection({
  selectedStore,
  capabilities,
  results,
  readiness,
  financialSummary,
}) {
  const platform = String(selectedStore?.rawPlatform || selectedStore?.platform || '').toLowerCase();
  const cards = buildPlatformBusinessStatus({
    platform,
    capabilities,
    results,
    readiness,
    financialSummary,
  });
  if (!cards.length) return null;

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>{businessCapabilityTitle(platform)}</h2>
          <p>默认只显示卖家需要知道的连接状态和下一步动作。</p>
        </div>
        <span className="period-chip">{selectedStore?.name || '当前店铺'}</span>
      </div>
      <div className="business-capability-grid">
        {cards.map((card) => (
          <article className={`business-capability-card ${card.tone || 'info'}`} key={card.key}>
            <div className="business-capability-head">
              <strong>{card.title}</strong>
              <span>{card.statusLabel}</span>
            </div>
            <p>{card.reason}</p>
            <small>{card.nextAction}</small>
          </article>
        ))}
      </div>
      <TechnicalDetails
        description="连接检查记录仍保留给管理员排查，普通工作台不直接展示技术字段。"
        items={[
          { label: 'capability_count', value: capabilities.length },
          { label: 'result_count', value: results.length },
          { label: 'readiness_available', value: Boolean(readiness) },
          { label: 'data_source', value: DATA_SOURCE },
        ]}
      />
    </section>
  );
}

export default function Dashboard() {
  const {
    selectedStoreId,
    selectedStore,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const { versions } = useSyncRefresh();
  const [summary, setSummary] = useState(null);
  const [risks, setRisks] = useState([]);
  const [todos, setTodos] = useState([]);
  const [activities, setActivities] = useState({ logs: [], appeals: [], customers: [], emails: [] });
  const [trend, setTrend] = useState([]);
  const [error, setError] = useState('');
  const [platformStatusData, setPlatformStatusData] = useState({ capabilities: [], results: [], readiness: null });

  useEffect(() => {
    if (isBackendSource && storeLoading) return;
    if (isBackendSource && storeError) {
      setError(storeError);
      return;
    }
    if (isBackendSource && !selectedStoreId) {
      setSummary({
        storeTotal: 0,
        productTotal: 0,
        todayOrderCount: 0,
        todaySalesAmount: 0,
        scopeOrderCount: 0,
        scopeSalesAmount: 0,
        pendingCustomers: 0,
        pendingAppeals: 0,
        riskEnvironments: 0,
        unreadImportantEmails: 0,
        businessTimezone: BUSINESS_TIME_ZONE,
        apiCapabilitySummary: emptyApiCapabilitySummary,
        financialSummary: createEmptyFinancialSummary(),
      });
      setRisks([]);
      setTodos([]);
      setActivities({ logs: [], appeals: [], customers: [], emails: [] });
      setTrend([]);
      setError('');
      return;
    }

    const params = isBackendSource ? { storeId: selectedStoreId } : {};
    setSummary(null);
    setError('');
    Promise.all([
      dataProvider.getDashboardData(params),
      dataProvider.getDashboardSalesTrend(),
    ])
      .then(([dashboardData, trendData]) => {
        setSummary(dashboardData.summary);
        setRisks(dashboardData.risks);
        setTodos(dashboardData.todos);
        setActivities(dashboardData.activities);
        setTrend(trendData);
      })
      .catch((requestError) => setError(requestError.message || '工作台数据加载失败。'));
  }, [selectedStoreId, storeError, storeLoading, versions.dashboard]);

  useEffect(() => {
    if (storeLoading || storeError || !selectedStoreId) {
      setPlatformStatusData({ capabilities: [], results: [], readiness: null });
      return;
    }
    let cancelled = false;
    Promise.all([
      dataProvider.getApiCapabilities({ page: 1, pageSize: 100 }),
      dataProvider.getApiCapabilityResults({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
      dataProvider.getApiCredentialReadiness({ storeId: selectedStoreId }),
    ])
      .then(([capabilityResponse, resultResponse, readiness]) => {
        if (cancelled) return;
        const capabilities = capabilityResponse.data || capabilityResponse.items || [];
        const capabilityMap = new Map(capabilities.map((item) => [String(item.id), item]));
        const results = (resultResponse.data || resultResponse.items || []).map((item) => ({
          ...item,
          capabilityKey: capabilityMap.get(String(item.capabilityId))?.capabilityKey,
        }));
        setPlatformStatusData({ capabilities, results, readiness });
      })
      .catch(() => {
        if (!cancelled) setPlatformStatusData({ capabilities: [], results: [], readiness: null });
      });
    return () => { cancelled = true; };
  }, [selectedStoreId, storeError, storeLoading, versions.dashboard]);

  const stats = useMemo(() => {
    if (!summary) return [];
    return [
      { label: '店铺数量', value: summary.storeTotal, detail: '已接入店铺', tone: 'info' },
      { label: '本地商品', value: summary.productTotal, detail: '当前店铺商品记录', tone: 'info' },
      { label: '订单数', value: summary.scopeOrderCount ?? summary.todayOrderCount, detail: '当前范围内订单', tone: 'positive' },
      { label: '订单金额', value: formatWon(summary.scopeSalesAmount ?? summary.todaySalesAmount), detail: '来自订单金额', tone: 'positive' },
      { label: '待回复客服', value: summary.pendingCustomers, detail: '客户咨询', tone: summary.pendingCustomers > 0 ? 'warning' : 'positive' },
      { label: '申诉事项', value: summary.pendingAppeals, detail: '需要补充资料或跟进', tone: summary.pendingAppeals > 0 ? 'danger' : 'positive' },
      { label: '设备风险', value: summary.riskEnvironments, detail: '账号或登录环境', tone: summary.riskEnvironments > 0 ? 'danger' : 'positive' },
      { label: '重要邮件', value: summary.unreadImportantEmails, detail: '平台通知', tone: summary.unreadImportantEmails > 0 ? 'warning' : 'positive' },
    ];
  }, [summary]);

  if (error) {
    return (
      <>
        <PageHeader title="运营工作台" description="查看店铺状态、待办事项和业务提醒。" />
        <article className="content-card empty-state">
          <h2>工作台加载失败</h2>
          <p>{error}</p>
        </article>
      </>
    );
  }

  if (!summary) return <div className="table-state"><span className="spinner" />正在加载工作台...</div>;

  const businessDate = summary.businessDate;
  const maxTrendSales = Math.max(...trend.map((item) => item.sales), 1);

  return (
    <>
      <PageHeader
        title="运营工作台"
        description="用卖家能看懂的方式汇总订单、客服、商品、库存、销售额、设备和平台连接状态。"
        actions={(
          <>
            {isBackendSource && <MockSyncPanel />}
            <span className="period-chip">数据源 {DATA_SOURCE}</span>
            <span className="period-chip">业务日期 {businessDate ? formatKstDate(businessDate) : BUSINESS_TIME_LABEL}</span>
          </>
        )}
      />
      <StatGrid items={stats} />

      <section className="panel-grid">
        <SellerTodoOverview summary={summary} todos={todos} />
        <RiskPanel title="风险提醒" items={risks} />
      </section>

      <PlatformBusinessStatusSection
        selectedStore={selectedStore}
        capabilities={platformStatusData.capabilities}
        results={platformStatusData.results}
        readiness={platformStatusData.readiness}
        financialSummary={summary.financialSummary}
      />

      <FinancialSummarySection financialSummary={summary.financialSummary} />

      <section className="panel-grid">
        <article className="content-card">
          <div className="card-title">
            <div>
              <h2>销售趋势</h2>
              <p>近 7 天订单金额趋势，用于观察店铺销售波动。</p>
            </div>
            <span className="period-chip">KST</span>
          </div>
          <div className="trend-bars">
            {trend.map((item) => (
              <div key={item.date} className="trend-col">
                <div className="trend-bar-wrap">
                  <div className="trend-bar" style={{ height: `${Math.max((item.sales / maxTrendSales) * 100, 12)}%` }} />
                </div>
                <strong>{item.date.slice(5)}</strong>
                <span>{formatWon(item.sales)}</span>
                <small>{item.orders} 单</small>
              </div>
            ))}
          </div>
        </article>
        <article className="content-card">
          <div className="card-title">
            <div>
              <h2>最近动态</h2>
              <p>展示最近订单、同步任务和运营事项摘要。</p>
            </div>
          </div>
          <ActivityList items={(activities.logs || []).map((item) => ({
            id: item.id,
            title: item.module,
            description: item.summary,
            status: item.status,
            time: formatKstDateTimeWithLabel(item.time),
          }))}
          />
        </article>
      </section>
    </>
  );
}
