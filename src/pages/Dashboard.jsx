import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ActivityList from '../components/common/ActivityList';
import EmptyState from '../components/common/EmptyState';
import InfoGrid from '../components/common/InfoGrid';
import MockSyncPanel from '../components/common/MockSyncPanel';
import PageHeader from '../components/common/PageHeader';
import RiskPanel from '../components/common/RiskPanel';
import StatGrid from '../components/common/StatGrid';
import TodoList from '../components/common/TodoList';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { DATA_SOURCE, isBackendSource } from '../services/dataProvider';
import {
  buildPlatformBusinessStatus,
  businessCapabilityTitle,
} from '../utils/capabilityStatusMapper';
import {
  BUSINESS_TIME_LABEL,
  BUSINESS_TIME_ZONE,
  formatKstDate,
  formatKstDateTimeWithLabel,
} from '../utils/time';

const formatWon = (value) => `KRW ${Number(value || 0).toLocaleString()}`;
const formatStructured = (value) => (
  Object.keys(value || {}).length ? JSON.stringify(value, null, 2) : 'No structured data.'
);

const emptyApiCapabilitySummary = {
  semanticNotice: 'Mock mode does not maintain Codex1 API capability records.',
  platformSummary: [],
  storeResultSummary: [],
  attentionItems: [],
};

function createEmptyFinancialSummary() {
  return {
    available: false,
    orderSalesSummary: {
      scope: 'order_amount_from_orders',
      totalOrders: 0,
      totalOrderSalesAmount: 0,
      currency: 'KRW',
      latestOrderedAt: null,
    },
    platformSalesDetailSummary: {
      scope: 'platform_sales_details',
      salesDetailRows: 0,
      totalSaleAmount: 0,
      totalSettlementTargetAmount: 0,
      totalSettlementAmount: 0,
      latestRecognitionDate: null,
      currency: 'KRW',
      dataStatus: 'local_persisted_rows',
    },
    settlementSummary: {
      scope: 'platform_settlement_details',
      settlementRows: 0,
      totalSettlementAmount: 0,
      totalFinalAmount: 0,
      totalServiceFee: 0,
      latestRevenueRecognitionYearMonth: null,
      latestSettlementDate: null,
      currency: 'KRW',
      dataStatus: 'local_persisted_rows',
    },
    sourceBoundaries: {
      orderSalesScope: '订单金额口径来自 orders.order_amount。',
      platformSalesDetailScope: '销售确认口径来自 platform_sales_details。',
      settlementScope: '结算口径来自 platform_settlement_details。',
      settlementMonthGranularityNotice: 'Settlement uses revenueRecognitionYearMonth and is not day-precise.',
      finalAmountNotice: 'finalAmount is not profit and is not withdrawable balance.',
      zeroDataNotice: 'Zero rows only mean local persisted data is currently empty.',
    },
  };
}

function buildSummaryNotes(summary, kind) {
  if (!summary) return [];
  if (kind === 'sales') {
    return summary.salesDetailRows === 0 ? ['本地暂无持久化数据'] : [];
  }
  if (kind === 'settlement') {
    return summary.settlementRows === 0 ? ['本地暂无持久化数据'] : [];
  }
  if (kind === 'orders') {
    return summary.totalOrders === 0 ? ['当前订单金额口径为 0'] : [];
  }
  return [];
}

function FinancialScopeCard({ title, subtitle, items, notes = [] }) {
  return (
    <article className="financial-card">
      <div className="financial-card-head">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      <InfoGrid columns={2} items={items} />
      {notes.length ? (
        <div className="financial-card-note">
          {notes.map((note) => <span key={note}>{note}</span>)}
        </div>
      ) : null}
    </article>
  );
}

function FinancialSummarySection({ financialSummary, title = '财务摘要 / Financial Summary', framed = true }) {
  const summary = financialSummary || createEmptyFinancialSummary();
  const boundaries = summary.sourceBoundaries || {};
  const Wrapper = framed ? 'section' : 'div';
  const wrapperClassName = framed ? 'content-card' : 'detail-section financial-summary-embedded';

  return (
    <Wrapper className={wrapperClassName}>
      <div className="card-title">
        <div>
          <h2>{title}</h2>
          <p>订单金额、销售确认金额、结算金额分区展示，不做混算。</p>
        </div>
        <span className="period-chip">KRW scoped</span>
      </div>

      {!summary.available ? (
        <EmptyState
          title="暂无财务摘要"
          description="当前响应未提供 financial_summary / financial_context，页面已做兼容降级。"
        />
      ) : (
        <>
          <div className="financial-summary-grid">
            <FinancialScopeCard
              title="订单金额口径"
              subtitle="基于 orders.order_amount"
              items={[
                { label: '订单金额', value: formatWon(summary.orderSalesSummary.totalOrderSalesAmount) },
                { label: '订单数', value: summary.orderSalesSummary.totalOrders },
                { label: '最近订单时间', value: formatKstDateTimeWithLabel(summary.orderSalesSummary.latestOrderedAt) },
                { label: '币种', value: summary.orderSalesSummary.currency || 'KRW' },
              ]}
              notes={buildSummaryNotes(summary.orderSalesSummary, 'orders')}
            />
            <FinancialScopeCard
              title="销售确认口径"
              subtitle="基于 platform_sales_details"
              items={[
                { label: '明细行数', value: summary.platformSalesDetailSummary.salesDetailRows },
                { label: '销售确认金额', value: formatWon(summary.platformSalesDetailSummary.totalSaleAmount) },
                { label: '待结算目标金额', value: formatWon(summary.platformSalesDetailSummary.totalSettlementTargetAmount) },
                { label: '已映射结算金额', value: formatWon(summary.platformSalesDetailSummary.totalSettlementAmount) },
                { label: '最近确认日期', value: formatKstDate(summary.platformSalesDetailSummary.latestRecognitionDate) },
                { label: '数据状态', value: summary.platformSalesDetailSummary.dataStatus || 'local_persisted_rows' },
              ]}
              notes={buildSummaryNotes(summary.platformSalesDetailSummary, 'sales')}
            />
            <FinancialScopeCard
              title="结算口径"
              subtitle="基于 platform_settlement_details"
              items={[
                { label: '结算行数', value: summary.settlementSummary.settlementRows },
                { label: '结算金额', value: formatWon(summary.settlementSummary.totalSettlementAmount) },
                { label: 'finalAmount', value: formatWon(summary.settlementSummary.totalFinalAmount) },
                { label: 'serviceFee', value: formatWon(summary.settlementSummary.totalServiceFee) },
                { label: '最近 revenueRecognitionYearMonth', value: summary.settlementSummary.latestRevenueRecognitionYearMonth || '-' },
                { label: '最近结算日期', value: formatKstDate(summary.settlementSummary.latestSettlementDate) },
              ]}
              notes={buildSummaryNotes(summary.settlementSummary, 'settlement')}
            />
          </div>

          <div className="financial-boundary-list">
            <div className="financial-boundary-item">
              <strong>口径边界</strong>
              <p>{boundaries.orderSalesScope}</p>
              <p>{boundaries.platformSalesDetailScope}</p>
              <p>{boundaries.settlementScope}</p>
            </div>
            <div className="financial-boundary-item">
              <strong>结算说明</strong>
              <p>{boundaries.settlementMonthGranularityNotice}</p>
            </div>
            <div className="financial-boundary-item">
              <strong>金额解释</strong>
              <p>{boundaries.finalAmountNotice}</p>
            </div>
            <div className="financial-boundary-item">
              <strong>0 数据说明</strong>
              <p>{boundaries.zeroDataNotice}</p>
            </div>
          </div>
        </>
      )}
    </Wrapper>
  );
}

function ApiCapabilitySummarySection({ summary, source = 'dashboard', onOpenMatrix }) {
  const data = summary || emptyApiCapabilitySummary;
  const platformRows = data.platformSummary || [];
  const storeRows = data.storeResultSummary || [];
  const attentionItems = data.attentionItems || [];
  const isEmpty = !platformRows.length && !storeRows.length && !attentionItems.length;

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>{source === 'ai' ? 'AI API Capability Context' : 'API Capability Summary'}</h2>
          <p>docs-only / manual / mock / sandbox are record states only and do not mean real platform connectivity.</p>
        </div>
        <button className="button ghost" onClick={onOpenMatrix}>Open Matrix</button>
      </div>
      <div className="form-info">
        `tested_success_count` means recorded success only. `real_readonly_count` is reserved for future explicit real readonly verification.
      </div>
      {isEmpty ? (
        <EmptyState
          title={source === 'mock' ? 'Mock mode has no backend capability summary' : 'No API capability summary'}
          description={data.semanticNotice || 'There are no platform-level or store-level API capability records yet.'}
        />
      ) : (
        <>
          <div className="panel-grid">
            <div className="detail-section">
              <h3>Platform Summary</h3>
              {platformRows.length ? (
                <div className="detail-list">
                  {platformRows.map((item) => (
                    <div className="log-item" key={item.rawPlatform || item.platform}>
                      <div className="log-item-head">
                        <strong>{item.platform}</strong>
                        <span className="period-chip">Capabilities {item.totalCapabilities}</span>
                      </div>
                      <InfoGrid
                        columns={3}
                        items={[
                          { label: 'docs-only', value: item.docsOnlyCount },
                          { label: 'manual', value: item.manualCount },
                          { label: 'tested success', value: item.testedSuccessCount },
                          { label: 'not tested', value: item.notTestedCount },
                          { label: 'permission required', value: item.permissionRequiredCount },
                          { label: 'unavailable', value: item.unavailableCount },
                          { label: 'phase-1 candidate', value: item.firstPhaseCandidateCount },
                          { label: 'real readonly', value: item.realReadonlyCount },
                          { label: 'last checked', value: formatKstDateTimeWithLabel(item.lastCheckedAt) },
                        ]}
                      />
                    </div>
                  ))}
                </div>
              ) : <EmptyState title="No platform records" description="Codex1 has not returned any platform-level capability summary." />}
            </div>
            <div className="detail-section">
              <h3>Store Summary</h3>
              {storeRows.length ? (
                <div className="detail-list">
                  {storeRows.map((item) => (
                    <div className="log-item" key={`${item.storeId}-${item.rawPlatform || item.platform}`}>
                      <div className="log-item-head">
                        <strong>{item.platform}</strong>
                        <span className="period-chip">Results {item.totalResults}</span>
                      </div>
                      <InfoGrid
                        columns={2}
                        items={[
                          { label: 'credential bound', value: item.credentialBoundResults },
                          { label: 'manual', value: item.manualCount },
                          { label: 'docs-only', value: item.docsOnlyCount },
                          { label: 'mock/sandbox', value: `${item.mockCount}/${item.sandboxCount}` },
                          { label: 'tested success', value: item.testedSuccessCount },
                          { label: 'tested failed', value: item.testedFailedCount },
                          { label: 'permission required', value: item.permissionRequiredCount },
                          { label: 'missing phase-1', value: item.missingFirstPhaseCandidates.length },
                          { label: 'latest record', value: formatKstDateTimeWithLabel(item.latestTestedAt) },
                        ]}
                      />
                    </div>
                  ))}
                </div>
              ) : <EmptyState title="No store records" description="Select a store to view store-level capability results." />}
            </div>
          </div>
          <div className="detail-section">
            <h3>Attention Items</h3>
            {attentionItems.length ? (
              <div className="risk-panel">
                {attentionItems.map((item) => (
                  <div className="risk-item" key={item.id}>
                    <div className="risk-item-head">
                      <strong>{item.platform || 'All platforms'}</strong>
                      <span className="period-chip">{item.level} / {item.count}</span>
                    </div>
                    <p>{item.message}</p>
                  </div>
                ))}
              </div>
            ) : <p>No current attention items.</p>}
          </div>
        </>
      )}
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
          <p>把后端检测记录转成卖家能直接判断的运营状态。</p>
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
    </section>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
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
  const [dailyContext, setDailyContext] = useState(null);
  const [contextError, setContextError] = useState('');
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
      .catch((requestError) => setError(requestError.message || 'Failed to load dashboard data.'));
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

  useEffect(() => {
    if (!isBackendSource || storeLoading) return;
    if (!selectedStoreId) {
      setDailyContext(null);
      return;
    }
    setContextError('');
    dataProvider.getAiDailyContext({ storeId: selectedStoreId })
      .then(setDailyContext)
      .catch((requestError) => setContextError(requestError.message || 'Failed to load daily context.'));
  }, [selectedStoreId, storeLoading, versions.aiDailyContext]);

  if (error) {
    return (
      <>
        <PageHeader title="运营总览" description="汇总核心运营、风险、待办和审计数据。" />
        <article className="content-card empty-state">
          <h2>Dashboard load failed</h2>
          <p>{error}</p>
        </article>
      </>
    );
  }

  if (!summary) return <div className="table-state"><span className="spinner" />Loading dashboard data...</div>;

  const businessDate = summary.businessDate || dailyContext?.date;
  const orderMetricLabel = isBackendSource ? '当前范围订单数' : 'KST 今日订单数';
  const salesMetricLabel = isBackendSource ? '当前范围订单金额' : 'KST 今日订单金额';
  const stats = [
    { label: '店铺总数', value: summary.storeTotal, detail: '已接入多平台店铺', tone: 'positive' },
    { label: '商品总数', value: summary.productTotal, detail: '当前店铺本地商品', tone: 'info' },
    { label: orderMetricLabel, value: summary.scopeOrderCount ?? summary.todayOrderCount, detail: 'orders scope', tone: 'info' },
    { label: salesMetricLabel, value: formatWon(summary.scopeSalesAmount ?? summary.todaySalesAmount), detail: 'orders.order_amount only', tone: 'positive' },
    { label: '待处理客服', value: summary.pendingCustomers, detail: '待回复客户咨询', tone: 'warning' },
    { label: '申诉中案件', value: summary.pendingAppeals, detail: '资料准备或审核中', tone: 'danger' },
    { label: '风险环境数量', value: summary.riskEnvironments, detail: '需要重点检查', tone: 'danger' },
    { label: '未读重要邮件', value: summary.unreadImportantEmails, detail: '优先跟进提醒', tone: 'warning' },
  ];
  const maxTrendSales = Math.max(...trend.map((item) => item.sales), 1);
  const dashboardCapabilitySummary = isBackendSource ? summary.apiCapabilitySummary : emptyApiCapabilitySummary;
  const aiCapabilityContext = dailyContext?.apiCapabilityContext;
  const openApiCapabilities = () => navigate('/api-capabilities');

  return (
    <>
      <PageHeader
        title="运营总览"
        description="汇总核心运营、风险、待办和审计数据。"
        actions={(
          <>
            {isBackendSource && <MockSyncPanel />}
            <span className="period-chip">数据源: {DATA_SOURCE}</span>
            <span className="period-chip">韩国业务日: {businessDate ? formatKstDate(businessDate) : BUSINESS_TIME_LABEL}</span>
          </>
        )}
      />
      <StatGrid items={stats} />

      <FinancialSummarySection financialSummary={summary.financialSummary} />

      <PlatformBusinessStatusSection
        selectedStore={selectedStore}
        capabilities={platformStatusData.capabilities}
        results={platformStatusData.results}
        readiness={platformStatusData.readiness}
        financialSummary={summary.financialSummary}
      />

      <ApiCapabilitySummarySection
        summary={dashboardCapabilitySummary}
        source={isBackendSource ? 'dashboard' : 'mock'}
        onOpenMatrix={openApiCapabilities}
      />

      <section className="panel-grid">
        <article className="content-card">
          <div className="card-title">
            <div>
              <h2>销售趋势</h2>
              <p>复用销售模块近 7 天趋势数据。</p>
            </div>
            <span className="period-chip">KST last 7 days</span>
          </div>
          <div className="trend-bars">
            {trend.map((item) => (
              <div key={item.date} className="trend-col">
                <div className="trend-bar-wrap">
                  <div className="trend-bar" style={{ height: `${Math.max((item.sales / maxTrendSales) * 100, 12)}%` }} />
                </div>
                <strong>{item.date.slice(5)}</strong>
                <span>{formatWon(item.sales)}</span>
                <small>{item.orders} orders</small>
              </div>
            ))}
          </div>
        </article>
        <article className="content-card">
          <div className="card-title">
            <div>
              <h2>待办事项</h2>
              <p>跨客服、申诉、订单、邮箱、环境的待处理项。</p>
            </div>
          </div>
          <TodoList items={todos} />
        </article>
      </section>

      <section className="panel-grid">
        <RiskPanel title="风险提醒区域" items={risks} />
        <article className="content-card">
          <div className="card-title">
            <div>
              <h2>最近动态区域</h2>
              <p>最近操作日志、申诉更新、客户回复和邮箱提醒。</p>
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

      {isBackendSource && (
        <section className="content-card">
          <div className="card-title">
            <div>
              <h2>AI Daily Context</h2>
              <p>只展示 Codex1 聚合结果，不调用模型，也不生成日报文案。</p>
            </div>
          </div>
          {contextError ? <EmptyState title="Daily Context load failed" description={contextError} /> : dailyContext ? (
            <>
              <InfoGrid items={[
                { label: '统计日期', value: formatKstDate(dailyContext.date) },
                { label: '业务时区', value: dailyContext.businessTimezone || BUSINESS_TIME_ZONE },
                { label: '店铺范围', value: dailyContext.scope.storeId || '全部店铺' },
                { label: '平台范围', value: dailyContext.scope.platform || '全部平台' },
                { label: '建议关注项', value: dailyContext.recommendedFocus.length },
              ]}
              />
              <div className="panel-grid">
                <div className="detail-section">
                  <h3>销售与订单摘要</h3>
                  <pre>{formatStructured({ sales: dailyContext.salesSummary, orders: dailyContext.orderSummary })}</pre>
                </div>
                <div className="detail-section">
                  <h3>客服与同步摘要</h3>
                  <pre>{formatStructured({ inquiries: dailyContext.customerInquirySummary, sync: dailyContext.syncSummary })}</pre>
                </div>
              </div>
              <FinancialSummarySection
                financialSummary={dailyContext.financialContext}
                title="AI 财务上下文 / Financial Context"
                framed={false}
              />
              <ApiCapabilitySummarySection
                summary={aiCapabilityContext}
                source="ai"
                onOpenMatrix={openApiCapabilities}
              />
              <div className="detail-section">
                <h3>风险与建议关注</h3>
                <pre>{JSON.stringify({ riskFlags: dailyContext.riskFlags, recommendedFocus: dailyContext.recommendedFocus }, null, 2)}</pre>
              </div>
            </>
          ) : <div className="table-state"><span className="spinner" />Loading daily context...</div>}
        </section>
      )}
    </>
  );
}
