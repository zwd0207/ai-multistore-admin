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
import {
  buildPlatformBusinessStatus,
  buildTechnicalItemsFromCards,
  businessCapabilityTitle,
  getNaverOrderPreviewStatus,
  getNaverProductPreviewStatus,
} from '../utils/capabilityStatusMapper';
import { buildNaverInventorySummary } from '../utils/naverInventory';
import { buildNaverOrderFulfillmentSummary } from '../utils/naverOrderFulfillment';
import { buildNaverOrderSalesSummary } from '../utils/naverOrderSales';
import { buildNaverProductChangeHints } from '../utils/naverProductChangeHints';
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

function SellerTodoOverview({
  summary,
  todos = [],
  selectedStore,
  capabilities,
  results,
  inventorySummary,
  orderFulfillmentSummary,
  productChangeHints,
}) {
  const isNaverStore = String(selectedStore?.rawPlatform || selectedStore?.platform || '').toLowerCase() === 'naver';
  const naverProductStatus = isNaverStore ? getNaverProductPreviewStatus({ capabilities, results }) : null;
  const naverOrderStatus = isNaverStore ? getNaverOrderPreviewStatus({ capabilities, results }) : null;
  const naverConnectionTodo = !isNaverStore || !naverProductStatus?.activeIssue
    ? null
    : {
      id: 'naver-connection',
      title: '当前连接异常',
      description: 'Naver 当前连接异常，请检查平台连接资料或 API 设置。',
      status: naverProductStatus.activeIssue.tone,
    };
  const naverProductTodo = !isNaverStore
    ? null
    : {
      id: 'naver-products',
      title: '商品小批量写入测试',
      description: 'Naver 商品小批量写入测试已完成。当前本地已有 5 条商品，暂无新增或业务字段更新，仅同步时间需要刷新。正式批量同步仍未开放。',
      status: 'success',
    };
  const naverProductChangeTodo = !isNaverStore || !productChangeHints
    ? null
    : {
      id: 'naver-product-price-stock',
      title: '价格 / 库存变化提示',
      description: `${productChangeHints.businessMessage}${productChangeHints.nextAction}`,
      status: productChangeHints.businessChangeObserved ? 'warning' : 'success',
    };
  const naverOrderTodo = !isNaverStore
    ? null
    : {
      id: 'naver-orders',
      title: '订单单条写入测试',
      description: `${naverOrderStatus?.detail.reason || 'Naver 已完成 1 条订单本地写入测试。'}正式订单批量同步仍未开放。`,
      status: 'success',
    };
  const naverInventoryTodo = !isNaverStore || !inventorySummary
    ? null
    : {
      id: 'naver-inventory',
      title: '库存提醒',
      description: `${inventorySummary.businessMessage}${inventorySummary.nextAction}正式商品批量同步仍未开放。`,
      status: inventorySummary.attentionCount > 0 ? 'warning' : 'success',
    };
  const naverFulfillmentTodo = !isNaverStore || !orderFulfillmentSummary
    ? null
    : {
      id: 'naver-fulfillment',
      title: '订单履约 / 售后',
      description: `${orderFulfillmentSummary.businessMessage}发货、取消、退货、换货写操作仍未开放。`,
      status: orderFulfillmentSummary.actionNeededCount > 0 ? 'warning' : 'success',
    };
  const naverStatusTodos = [
    naverConnectionTodo,
    naverProductTodo,
    naverProductChangeTodo,
    naverOrderTodo,
    naverInventoryTodo,
    naverFulfillmentTodo,
  ].filter(Boolean);
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
    ...naverStatusTodos,
  ];
  const displayItems = todos.length
    ? [
      ...todos,
      ...naverStatusTodos.filter(
        (todo) => !todos.some((item) => String(item.id || item.title || '') === todo.id),
      ),
    ]
    : priorityItems;

  return (
    <article className="content-card">
      <div className="card-title">
        <div>
          <h2>今日待办</h2>
          <p>按卖家日常处理顺序展示订单、客服、邮件、申诉、设备和商品预览。</p>
        </div>
      </div>
      <TodoList items={displayItems} />
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
            <p>不等同于利润或账户可提取资金</p>
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

function NaverOrderSalesSummarySection({ selectedStore, orderSalesSummary }) {
  const isNaverStore = String(selectedStore?.rawPlatform || selectedStore?.platform || '').toLowerCase() === 'naver';
  if (!isNaverStore || !orderSalesSummary) return null;

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>Naver 订单金额摘要</h2>
          <p>只按本地已脱敏订单金额汇总，不接入 Naver 结算、利润或账户可提取资金。</p>
        </div>
        <span className="period-chip">KRW</span>
      </div>
      <div className="financial-summary-grid">
        <article className="financial-card">
          <div className="financial-card-head">
            <h3>本地订单金额</h3>
            <p>来自本地运营订单金额</p>
          </div>
          <strong>{formatWon(orderSalesSummary.totalOrderAmount)}</strong>
          <small>{orderSalesSummary.totalOrders} 条 Naver 运营订单</small>
        </article>
        <article className="financial-card">
          <div className="financial-card-head">
            <h3>今日订单金额</h3>
            <p>按本地订单日期汇总</p>
          </div>
          <strong>{formatWon(orderSalesSummary.todayOrderAmount)}</strong>
          <small>{orderSalesSummary.todayOrders} 条订单</small>
        </article>
        <article className="financial-card">
          <div className="financial-card-head">
            <h3>本周 / 本月</h3>
            <p>仅用于运营观察</p>
          </div>
          <strong>{formatWon(orderSalesSummary.weekOrderAmount)}</strong>
          <small>本月 {formatWon(orderSalesSummary.monthOrderAmount)}</small>
        </article>
      </div>
      <p className="mock-sync-note">该金额来自本地运营订单金额汇总，不等于平台结算金额，不等于利润，也不等于账户可提取资金。取消金额和退款金额待订单字段稳定后再拆分。</p>
      <TechnicalDetails
        description="技术口径仅供管理员排查，主页面用业务文案展示。"
        items={[
          { label: 'scope', value: orderSalesSummary.scope },
          { label: 'total_orders', value: orderSalesSummary.totalOrders },
          { label: 'total_order_amount', value: orderSalesSummary.totalOrderAmount },
          { label: 'today_orders', value: orderSalesSummary.todayOrders },
          { label: 'today_order_amount', value: orderSalesSummary.todayOrderAmount },
          { label: 'week_orders', value: orderSalesSummary.weekOrders },
          { label: 'week_order_amount', value: orderSalesSummary.weekOrderAmount },
          { label: 'month_orders', value: orderSalesSummary.monthOrders },
          { label: 'month_order_amount', value: orderSalesSummary.monthOrderAmount },
          { label: 'latest_ordered_at', value: formatKstDateTimeWithLabel(orderSalesSummary.latestOrderedAt) },
          { label: 'settlement_amount_available', value: orderSalesSummary.settlementAmountAvailable },
          { label: 'profit_available', value: orderSalesSummary.profitAvailable },
          { label: 'withdrawable_balance_available', value: orderSalesSummary.withdrawableBalanceAvailable },
        ]}
      />
    </section>
  );
}

function NaverErpWorkbenchSection({
  selectedStore,
  capabilities,
  results,
  inventorySummary,
  orderFulfillmentSummary,
  orderSalesSummary,
  productChangeHints,
}) {
  const isNaverStore = String(selectedStore?.rawPlatform || selectedStore?.platform || '').toLowerCase() === 'naver';
  if (!isNaverStore) return null;

  const productStatus = getNaverProductPreviewStatus({ capabilities, results });
  const orderStatus = getNaverOrderPreviewStatus({ capabilities, results });
  const activeIssue = productStatus?.activeIssue || orderStatus?.activeIssue;
  const hasConnectionEvidence = Boolean(capabilities.length || results.length);
  const claimRequestCount = orderFulfillmentSummary?.claimRequestCount ?? 0;
  const orderActionCount = orderFulfillmentSummary?.actionNeededCount ?? 0;
  const inventoryAttentionCount = inventorySummary?.attentionCount ?? 0;
  const totalOrderAmount = orderSalesSummary?.totalOrderAmount ?? 0;

  const cards = [
    {
      key: 'connection',
      title: '店铺连接',
      statusLabel: activeIssue ? '需要检查' : hasConnectionEvidence ? '只读检测无阻断' : '等待检测结果',
      tone: activeIssue ? activeIssue.tone || 'warning' : hasConnectionEvidence ? 'success' : 'muted',
      reason: activeIssue
        ? 'Naver 当前连接异常，请检查平台连接资料或 API 设置。'
        : hasConnectionEvidence
          ? '当前没有检测到阻断 Naver 基础 ERP 只读展示的连接异常。'
          : '正在读取本地连接检测结果，暂不判断平台授权是否正常。',
      nextAction: activeIssue?.description || '继续保持只读预览优先，正式同步仍需单独批准。',
    },
    {
      key: 'products',
      title: '商品管理',
      statusLabel: '5 条小批量完成',
      tone: 'success',
      reason: 'Naver 商品小批量写入测试已完成。当前本地已有 5 条商品，暂无新增或业务字段更新，仅同步时间需要刷新。',
      nextAction: '正式商品批量同步仍未开放。',
    },
    {
      key: 'product_changes',
      title: '价格 / 库存变化',
      statusLabel: productChangeHints?.statusLabel || '读取本地商品',
      tone: productChangeHints?.tone || 'muted',
      reason: productChangeHints?.businessMessage || '等待本地商品和 dry-run 摘要支撑价格 / 库存变化提示。',
      nextAction: productChangeHints?.nextAction || '不执行平台商品写入，正式商品批量同步仍未开放。',
    },
    {
      key: 'orders',
      title: '订单管理',
      statusLabel: orderFulfillmentSummary?.total ? `${orderFulfillmentSummary.total} 条运营订单` : '单条测试完成',
      tone: orderActionCount > 0 ? 'info' : 'success',
      reason: orderFulfillmentSummary?.businessMessage || 'Naver 单条订单本地写入测试已完成。',
      nextAction: '正式订单批量同步仍未开放。',
    },
    {
      key: 'inventory',
      title: '库存提醒',
      statusLabel: inventorySummary ? inventorySummary.statusLabel : '读取本地商品',
      tone: inventoryAttentionCount > 0 ? 'warning' : inventorySummary?.tone || 'muted',
      reason: inventorySummary?.businessMessage || '库存提醒只基于本地 Naver 商品记录。',
      nextAction: inventorySummary?.nextAction || '低库存和缺货只做提醒，不执行平台库存写入。',
    },
    {
      key: 'fulfillment',
      title: '配送 / 售后',
      statusLabel: claimRequestCount > 0 ? `${claimRequestCount} 条售后请求` : '只读识别',
      tone: claimRequestCount > 0 ? 'warning' : orderFulfillmentSummary?.tone || 'muted',
      reason: orderFulfillmentSummary
        ? `新订单 ${orderFulfillmentSummary.newOrders} 条，待发货 ${orderFulfillmentSummary.pendingDispatch} 条，配送中 ${orderFulfillmentSummary.inDelivery} 条，售后请求 ${claimRequestCount} 条。`
        : '配送和售后状态等待本地订单数据支撑。',
      nextAction: '发货、取消、退货、换货写操作仍未开放。',
    },
    {
      key: 'sales',
      title: '订单金额',
      statusLabel: `${formatWon(totalOrderAmount)}`,
      tone: orderSalesSummary?.totalOrders ? 'info' : 'muted',
      reason: orderSalesSummary?.businessMessage || '当前没有可用于金额统计的 Naver 运营订单。',
      nextAction: '该金额只来自本地订单，不是平台结算金额、利润或账户可提取资金。',
    },
  ];

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>Naver ERP 工作台摘要</h2>
          <p>围绕商品、订单、库存、配送 / 售后和订单金额展示当前店铺要处理的事项。</p>
        </div>
        <span className="period-chip">{selectedStore?.name || 'Naver 店铺'}</span>
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
        description="技术字段继续折叠展示，主工作台只呈现卖家能直接理解的业务摘要。"
        items={[
          { label: 'naver_connection_issue', value: Boolean(activeIssue) },
          { label: 'product_small_batch_completed', value: true },
          { label: 'product_formal_batch_sync_open', value: false },
          { label: 'product_change_hints_status', value: productChangeHints?.statusLabel || '-' },
          { label: 'product_change_hints_would_update', value: productChangeHints?.wouldUpdate ?? 0 },
          { label: 'product_change_hints_changed_fields', value: productChangeHints?.changedFields?.length ? productChangeHints.changedFields.join(', ') : '[]' },
          { label: 'product_change_hints_price_change_observed', value: productChangeHints?.priceChangeObserved ?? false },
          { label: 'product_change_hints_stock_change_observed', value: productChangeHints?.stockChangeObserved ?? false },
          { label: 'product_change_hints_platform_read_performed_this_phase', value: productChangeHints?.platformReadPerformedThisPhase ?? false },
          { label: 'product_change_hints_platform_write_enabled', value: productChangeHints?.platformWriteEnabled ?? false },
          { label: 'order_single_write_completed', value: true },
          { label: 'order_formal_batch_sync_open', value: false },
          { label: 'inventory_attention_count', value: inventoryAttentionCount },
          { label: 'inventory_threshold_rule', value: inventorySummary?.thresholdRule || '-' },
          { label: 'inventory_platform_read_performed', value: inventorySummary?.platformReadPerformed ?? false },
          { label: 'inventory_platform_write_enabled', value: inventorySummary?.platformWriteEnabled ?? false },
          { label: 'inventory_platform_comparison_available', value: inventorySummary?.platformComparisonAvailable ?? false },
          { label: 'inventory_history_available', value: inventorySummary?.inventoryHistoryAvailable ?? false },
          { label: 'inventory_raw_response_saved', value: inventorySummary?.rawResponseSaved ?? false },
          { label: 'order_action_needed_count', value: orderActionCount },
          { label: 'mock_sync_orders_isolated', value: orderFulfillmentSummary?.excludedMockSyncCount ?? 0 },
          { label: 'claim_request_count', value: claimRequestCount },
          { label: 'local_order_amount', value: totalOrderAmount },
          { label: 'order_amount_scope', value: orderSalesSummary?.scope || 'local_orders_only' },
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
  const technicalItems = buildTechnicalItemsFromCards(cards, [
    { label: 'capability_count', value: capabilities.length },
    { label: 'result_count', value: results.length },
    { label: 'readiness_available', value: Boolean(readiness) },
    { label: 'data_source', value: DATA_SOURCE },
  ]);
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
        items={technicalItems}
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
  const [naverProductRows, setNaverProductRows] = useState([]);
  const [naverInventorySummary, setNaverInventorySummary] = useState(null);
  const [naverOrderFulfillmentSummary, setNaverOrderFulfillmentSummary] = useState(null);
  const [naverOrderSalesSummary, setNaverOrderSalesSummary] = useState(null);
  const isSelectedNaverStore = String(selectedStore?.rawPlatform || selectedStore?.platform || '').toLowerCase() === 'naver';

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
    let cancelled = false;
    dataProvider.getDashboardData(params)
      .then((dashboardData) => {
        if (cancelled) return;
        setSummary(dashboardData.summary);
        setRisks(dashboardData.risks);
        setTodos(dashboardData.todos);
        setActivities(dashboardData.activities);
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message || '工作台数据加载失败。');
      });

    dataProvider.getDashboardSalesTrend()
      .then((trendData) => {
        if (!cancelled) setTrend(trendData);
      })
      .catch(() => {
        if (!cancelled) setTrend([]);
      });

    return () => { cancelled = true; };
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
    const isNaverStore = String(selectedStore?.rawPlatform || selectedStore?.platform || '').toLowerCase() === 'naver';
    if (storeLoading || storeError || !selectedStoreId || !isNaverStore) {
      setNaverProductRows([]);
      setNaverInventorySummary(null);
      return undefined;
    }
    let cancelled = false;
    dataProvider.getProducts({
      storeId: selectedStoreId,
      platform: 'Naver',
      page: 1,
      pageSize: 100,
    })
      .then((productResponse) => {
        if (cancelled) return;
        const productRows = productResponse.data || productResponse.items || [];
        setNaverProductRows(productRows);
        setNaverInventorySummary(buildNaverInventorySummary(
          productRows,
          { selectedStore, selectedStoreId },
        ));
      })
      .catch(() => {
        if (!cancelled) {
          setNaverProductRows([]);
          setNaverInventorySummary(null);
        }
      });
    return () => { cancelled = true; };
  }, [selectedStore, selectedStoreId, storeError, storeLoading, versions.products]);

  useEffect(() => {
    const isNaverStore = String(selectedStore?.rawPlatform || selectedStore?.platform || '').toLowerCase() === 'naver';
    if (storeLoading || storeError || !selectedStoreId || !isNaverStore) {
      setNaverOrderFulfillmentSummary(null);
      setNaverOrderSalesSummary(null);
      return undefined;
    }
    let cancelled = false;
    dataProvider.getOrders({
      storeId: selectedStoreId,
      platform: 'naver',
      page: 1,
      pageSize: 100,
    })
      .then((orderResponse) => {
        if (cancelled) return;
        const orderRows = orderResponse.data || orderResponse.items || [];
        setNaverOrderFulfillmentSummary(buildNaverOrderFulfillmentSummary(orderRows, { selectedStore, selectedStoreId }));
        setNaverOrderSalesSummary(buildNaverOrderSalesSummary(orderRows, { selectedStore, selectedStoreId }));
      })
      .catch(() => {
        if (!cancelled) {
          setNaverOrderFulfillmentSummary(null);
          setNaverOrderSalesSummary(null);
        }
      });
    return () => { cancelled = true; };
  }, [selectedStore, selectedStoreId, storeError, storeLoading, versions.orders]);

  const sellerDisplaySummary = useMemo(() => {
    if (!summary) return null;
    if (!isSelectedNaverStore || !naverOrderSalesSummary) return summary;
    return {
      ...summary,
      todayOrderCount: naverOrderSalesSummary.todayOrders,
      todaySalesAmount: naverOrderSalesSummary.todayOrderAmount,
      scopeOrderCount: naverOrderSalesSummary.totalOrders,
      scopeSalesAmount: naverOrderSalesSummary.totalOrderAmount,
      financialSummary: {
        ...summary.financialSummary,
        orderSalesSummary: {
          ...summary.financialSummary?.orderSalesSummary,
          scope: naverOrderSalesSummary.scope,
          totalOrders: naverOrderSalesSummary.totalOrders,
          totalOrderSalesAmount: naverOrderSalesSummary.totalOrderAmount,
          latestOrderedAt: naverOrderSalesSummary.latestOrderedAt,
        },
      },
    };
  }, [isSelectedNaverStore, naverOrderSalesSummary, summary]);

  const naverProductChangeHints = useMemo(() => {
    if (!isSelectedNaverStore) return null;
    return buildNaverProductChangeHints(naverProductRows, {
      selectedStore,
      selectedStoreId,
      productStatus: getNaverProductPreviewStatus({
        capabilities: platformStatusData.capabilities,
        results: platformStatusData.results,
      }),
      results: platformStatusData.results,
    });
  }, [
    isSelectedNaverStore,
    naverProductRows,
    platformStatusData.capabilities,
    platformStatusData.results,
    selectedStore,
    selectedStoreId,
  ]);

  const stats = useMemo(() => {
    if (!sellerDisplaySummary) return [];
    const orderDetail = isSelectedNaverStore ? 'Naver 运营订单' : '当前范围内订单';
    const amountDetail = isSelectedNaverStore ? '来自运营订单金额' : '来自订单金额';
    return [
      { label: '店铺数量', value: sellerDisplaySummary.storeTotal, detail: '已接入店铺', tone: 'info' },
      { label: '本地商品', value: sellerDisplaySummary.productTotal, detail: '当前店铺商品记录', tone: 'info' },
      { label: '订单数', value: sellerDisplaySummary.scopeOrderCount ?? sellerDisplaySummary.todayOrderCount, detail: orderDetail, tone: 'positive' },
      { label: '订单金额', value: formatWon(sellerDisplaySummary.scopeSalesAmount ?? sellerDisplaySummary.todaySalesAmount), detail: amountDetail, tone: 'positive' },
      { label: '待回复客服', value: sellerDisplaySummary.pendingCustomers, detail: '客户咨询', tone: sellerDisplaySummary.pendingCustomers > 0 ? 'warning' : 'positive' },
      { label: '申诉事项', value: sellerDisplaySummary.pendingAppeals, detail: '需要补充资料或跟进', tone: sellerDisplaySummary.pendingAppeals > 0 ? 'danger' : 'positive' },
      { label: '设备风险', value: sellerDisplaySummary.riskEnvironments, detail: '账号或登录环境', tone: sellerDisplaySummary.riskEnvironments > 0 ? 'danger' : 'positive' },
      { label: '重要邮件', value: sellerDisplaySummary.unreadImportantEmails, detail: '平台通知', tone: sellerDisplaySummary.unreadImportantEmails > 0 ? 'warning' : 'positive' },
    ];
  }, [isSelectedNaverStore, sellerDisplaySummary]);

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
            {!isBackendSource && <MockSyncPanel />}
            <span className="period-chip">数据源 {DATA_SOURCE}</span>
            <span className="period-chip">业务日期 {businessDate ? formatKstDate(businessDate) : BUSINESS_TIME_LABEL}</span>
          </>
        )}
      />
      <StatGrid items={stats} />

      <NaverErpWorkbenchSection
        selectedStore={selectedStore}
        capabilities={platformStatusData.capabilities}
        results={platformStatusData.results}
        inventorySummary={naverInventorySummary}
        orderFulfillmentSummary={naverOrderFulfillmentSummary}
        orderSalesSummary={naverOrderSalesSummary}
        productChangeHints={naverProductChangeHints}
      />

      <section className="panel-grid">
        <SellerTodoOverview
          summary={sellerDisplaySummary}
          todos={todos}
          selectedStore={selectedStore}
          capabilities={platformStatusData.capabilities}
          results={platformStatusData.results}
          inventorySummary={naverInventorySummary}
          orderFulfillmentSummary={naverOrderFulfillmentSummary}
          productChangeHints={naverProductChangeHints}
        />
        <RiskPanel title="风险提醒" items={risks} />
      </section>

      <PlatformBusinessStatusSection
        selectedStore={selectedStore}
        capabilities={platformStatusData.capabilities}
        results={platformStatusData.results}
        readiness={platformStatusData.readiness}
        financialSummary={sellerDisplaySummary.financialSummary}
      />

      <NaverOrderSalesSummarySection
        selectedStore={selectedStore}
        orderSalesSummary={naverOrderSalesSummary}
      />

      <FinancialSummarySection financialSummary={sellerDisplaySummary.financialSummary} />

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
