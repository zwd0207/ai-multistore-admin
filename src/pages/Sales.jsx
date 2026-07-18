import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SummaryCard from '../components/common/SummaryCard';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { buildNaverOrderSalesSummary } from '../utils/naverOrderSales';
import { formatKstDateTimeWithLabel, getKstDateOffsetString, getKstTodayString } from '../utils/time';

const platforms = ['Naver', 'Coupang', 'Gmarket', '11st', 'Auction'];
const stores = ['首尔美妆测试店', '韩国本土运动鞋店', 'Gmarket 精品店', '11st 韩系生活馆', 'K-Beauty 快闪店', 'Auction 折扣店', 'Coupang 联调店'];
const MAX_FINANCIAL_PREVIEW_DAYS = 7;

const formatWon = (value) => `₩${Number(value || 0).toLocaleString()}`;

const columns = [
  { key: 'date', title: '日期' },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'orderCount', title: '订单数' },
  { key: 'grossSales', title: '销售额', render: (value) => formatWon(value) },
  { key: 'couponAmount', title: '优惠券金额', render: (value) => formatWon(value) },
  { key: 'refundAmount', title: '退款金额', render: (value) => formatWon(value) },
  { key: 'netSales', title: '净销售额', render: (value) => formatWon(value) },
  { key: 'bestSeller', title: '热销商品' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
];

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function clampMaxPages(value) {
  const nextValue = Number(value || 1);
  if (Number.isNaN(nextValue)) return 1;
  return Math.min(3, Math.max(1, nextValue));
}

function daySpan(startDate, endDate) {
  const start = new Date(`${startDate}T00:00:00Z`);
  const end = new Date(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
  return Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
}

function validateDateWindow(startDate, endDate, { sales = false, maxPages } = {}) {
  if (!startDate || !endDate) return '请选择开始日期和结束日期。';
  if (startDate > endDate) return '开始日期不能晚于结束日期。';
  const span = daySpan(startDate, endDate);
  if (!span || span < 1) return '日期格式无效。';
  if (span > MAX_FINANCIAL_PREVIEW_DAYS) return `当前预览阶段最多查询 ${MAX_FINANCIAL_PREVIEW_DAYS} 天。`;
  if (sales && endDate >= getKstTodayString()) return '销售明细通常只能查询已确认的历史日期，请避开今天或未来日期。';
  if (maxPages !== undefined && (Number(maxPages) < 1 || Number(maxPages) > 3)) return '单次最多读取 3 页。';
  return '';
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '后端真实只读开关未开启，本次没有访问平台。',
    real_api_test_disabled: '后端真实只读开关未开启，本次没有访问平台。',
    ip_not_allowed: '服务器 IP 不在平台白名单内，请联系管理员处理。',
    auth_failed: '平台授权失败，请检查连接资料、权限或 IP 白名单。',
    CREDENTIAL_DECRYPT_FAILED: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
    decrypt_failed: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
    SALES_DATE_NOT_AVAILABLE: '销售确认日期可能只能查询历史日期，请避开今天或未来日期。',
    readonly_request_failed: '只读查询失败，请检查日期、权限或参数。',
  };
  return messages[code] || error?.message || '销售或结算预览失败，请检查后端服务状态。';
}

function safeEntries(object = {}) {
  return Object.entries(object || {}).filter(([key]) => {
    const normalized = String(key).replace(/[_-]/g, '').toLowerCase();
    return !['bankaccountholder', 'bankname', 'bankaccount', 'accesskey', 'secretkey', 'authorization', 'signature', 'token'].some((item) => normalized.includes(item));
  }).filter(([, value]) => !(Array.isArray(value) && value.length === 0));
}

function FinancialPreviewResult({ result, type }) {
  if (!result) return null;
  const isSales = type === 'sales';
  const totalRows = Number(result.totalRows || 0);
  const title = isSales ? '销售明细预览' : '结算明细预览';
  const emptyMessage = isSales ? '查询成功，当前没有销售明细。' : '查询成功，当前没有结算明细。';

  return (
    <div className="coupang-sync-result">
      <div className="sync-result-banner">
        {totalRows === 0 ? emptyMessage : `${title}完成：共观察到 ${totalRows} 条明细。`}
      </div>
      <div className="business-capability-grid compact">
        <article className="business-capability-card info">
          <div className="business-capability-head"><strong>明细数量</strong><span>{totalRows} 条</span></div>
          <p>用于判断当前日期范围内是否有平台明细。</p>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head"><strong>查询范围</strong><span>{result.startDate} ~ {result.endDate}</span></div>
          <p>只读查询，不写入销售或结算表。</p>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head"><strong>原始响应</strong><span>未展示</span></div>
          <p>样本行、字段映射和分页信息默认折叠。</p>
        </article>
      </div>
      <TechnicalDetails
        items={[
          { label: 'total_rows', value: result.totalRows },
          { label: 'page_count', value: result.pageCount },
          { label: 'next_cursor_exists', value: result.nextCursorExists },
          { label: 'date_window', value: `${result.startDate} ~ ${result.endDate}` },
          { label: 'KST_window', value: result.windowStartAt || result.windowEndAt ? `${formatKstDateTimeWithLabel(result.windowStartAt)} / ${formatKstDateTimeWithLabel(result.windowEndAt)}` : '-' },
          { label: 'sample_ids', value: result.sampleIds?.length ? result.sampleIds.join(', ') : '[]' },
          { label: 'months', value: result.months?.length ? result.months.join(', ') : '-' },
        ]}
      >
        {safeEntries(result.summaryTotals).length ? (
          <div className="financial-preview-block">
            <h3>summary_totals</h3>
            <div className="sync-result-grid">
              {safeEntries(result.summaryTotals).map(([key, value]) => (
                <>
                  <span key={`${key}-label`}>{key}</span>
                  <strong key={`${key}-value`}>{String(value ?? '-')}</strong>
                </>
              ))}
            </div>
          </div>
        ) : null}
      </TechnicalDetails>
    </div>
  );
}

function CoupangFinancialPreviewPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [salesForm, setSalesForm] = useState({
    startDate: getKstDateOffsetString(-7),
    endDate: getKstDateOffsetString(-1),
    maxPages: 1,
  });
  const [settlementForm, setSettlementForm] = useState({
    startDate: getKstDateOffsetString(-2),
    endDate: getKstTodayString(),
  });
  const [salesResult, setSalesResult] = useState(null);
  const [settlementResult, setSettlementResult] = useState(null);
  const [salesMessage, setSalesMessage] = useState('');
  const [settlementMessage, setSettlementMessage] = useState('');
  const [salesError, setSalesError] = useState('');
  const [settlementError, setSettlementError] = useState('');
  const [loadingAction, setLoadingAction] = useState('');

  const isCoupangStore = normalizePlatform(selectedStore?.platform) === 'coupang';
  const salesValidation = useMemo(
    () => validateDateWindow(salesForm.startDate, salesForm.endDate, { sales: true, maxPages: salesForm.maxPages }),
    [salesForm.endDate, salesForm.maxPages, salesForm.startDate],
  );
  const settlementValidation = useMemo(
    () => validateDateWindow(settlementForm.startDate, settlementForm.endDate),
    [settlementForm.endDate, settlementForm.startDate],
  );

  if (!isCoupangStore) return null;

  const runSalesPreview = async () => {
    setSalesMessage('');
    setSalesError('');
    setSalesResult(null);
    if (salesValidation) {
      setSalesError(salesValidation);
      return;
    }
    setLoadingAction('sales');
    try {
      const result = await dataProvider.previewCoupangSales({
        storeId: selectedStoreId,
        startDate: salesForm.startDate,
        endDate: salesForm.endDate,
        maxPages: Number(salesForm.maxPages),
      });
      setSalesResult(result);
      setSalesMessage(isBackendSource ? '销售明细预览完成，本次只读查询，不写入销售表。' : 'mock 模式只展示页面效果，不执行真实平台查询。');
    } catch (requestError) {
      setSalesError(formatError(requestError));
    } finally {
      setLoadingAction('');
    }
  };

  const runSettlementPreview = async () => {
    setSettlementMessage('');
    setSettlementError('');
    setSettlementResult(null);
    if (settlementValidation) {
      setSettlementError(settlementValidation);
      return;
    }
    setLoadingAction('settlement');
    try {
      const result = await dataProvider.previewCoupangSettlements({
        storeId: selectedStoreId,
        startDate: settlementForm.startDate,
        endDate: settlementForm.endDate,
      });
      setSettlementResult(result);
      setSettlementMessage(isBackendSource ? '结算明细预览完成，本次只读查询，不写入结算表。' : 'mock 模式只展示页面效果，不执行真实平台查询。');
    } catch (requestError) {
      setSettlementError(formatError(requestError));
    } finally {
      setLoadingAction('');
    }
  };

  return (
    <section className="content-card coupang-financial-preview-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Coupang 销售与结算预览</h2>
          <p>用于确认销售明细和结算明细是否可读。当前不提供正式入库按钮，也不会修改平台数据。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>

      <div className="financial-preview-grid">
        <article className="financial-preview-card">
          <h3>销售明细</h3>
          <p className="mock-sync-note">预览阶段最多查询 7 天，结束日期请避开今天和未来日期。</p>
          <div className="sync-control-grid financial-control-grid">
            <label>
              <span>开始日期</span>
              <input type="date" value={salesForm.startDate} onChange={(event) => setSalesForm({ ...salesForm, startDate: event.target.value })} />
            </label>
            <label>
              <span>结束日期</span>
              <input type="date" value={salesForm.endDate} onChange={(event) => setSalesForm({ ...salesForm, endDate: event.target.value })} />
            </label>
            <label>
              <span>最多读取页数</span>
              <input type="number" min="1" max="3" value={salesForm.maxPages} onChange={(event) => setSalesForm({ ...salesForm, maxPages: clampMaxPages(event.target.value) })} />
            </label>
            <button className="button primary" onClick={runSalesPreview} disabled={Boolean(loadingAction)}>预览销售明细</button>
          </div>
          {salesValidation && <div className="sync-inline-warning">{salesValidation}</div>}
          {loadingAction === 'sales' && <div className="sync-inline-warning">正在预览销售明细...</div>}
          {salesMessage && <div className="mock-sync-success">{salesMessage}</div>}
          {salesError && <div className="mock-sync-error">{salesError}</div>}
          <FinancialPreviewResult result={salesResult} type="sales" />
        </article>

        <article className="financial-preview-card">
          <h3>结算明细</h3>
          <p className="mock-sync-note">结算查询按平台结算口径展示，不等同于利润或账户可提取资金。</p>
          <div className="sync-control-grid financial-control-grid">
            <label>
              <span>开始日期</span>
              <input type="date" value={settlementForm.startDate} onChange={(event) => setSettlementForm({ ...settlementForm, startDate: event.target.value })} />
            </label>
            <label>
              <span>结束日期</span>
              <input type="date" value={settlementForm.endDate} onChange={(event) => setSettlementForm({ ...settlementForm, endDate: event.target.value })} />
            </label>
            <button className="button primary" onClick={runSettlementPreview} disabled={Boolean(loadingAction)}>预览结算明细</button>
          </div>
          {settlementValidation && <div className="sync-inline-warning">{settlementValidation}</div>}
          {loadingAction === 'settlement' && <div className="sync-inline-warning">正在预览结算明细...</div>}
          {settlementMessage && <div className="mock-sync-success">{settlementMessage}</div>}
          {settlementError && <div className="mock-sync-error">{settlementError}</div>}
          <FinancialPreviewResult result={settlementResult} type="settlement" />
        </article>
      </div>
    </section>
  );
}

function NaverOrderSalesSummaryPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [summary, setSummary] = useState(null);
  const [loadError, setLoadError] = useState('');
  const isNaverStore = normalizePlatform(selectedStore?.rawPlatform || selectedStore?.platform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setSummary(null);
      setLoadError('');
      return undefined;
    }
    let cancelled = false;
    setLoadError('');
    dataProvider.getOrders({
      storeId: selectedStoreId,
      platform: 'naver',
      page: 1,
      pageSize: 100,
    })
      .then((orderResponse) => {
        if (cancelled) return;
        setSummary(buildNaverOrderSalesSummary(
          orderResponse.data || orderResponse.items || [],
          { selectedStore, selectedStoreId },
        ));
      })
      .catch((error) => {
        if (cancelled) return;
        setSummary(null);
        setLoadError(error.message || 'Naver 本地订单金额加载失败。');
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStore, selectedStoreId]);

  if (!isNaverStore) return null;
  const topStore = summary?.storeBreakdown?.[0];
  const topProduct = summary?.productBreakdown?.[0];

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>Naver 订单金额统计</h2>
          <p>按当前店铺本地已脱敏订单的 order_amount 汇总，不查询 Naver 销售、统计或结算接口。</p>
        </div>
        <span className="period-chip">{selectedStore?.name || 'Naver 店铺'}</span>
      </div>
      {loadError ? (
        <EmptyState title="Naver 订单金额加载失败" description={loadError} />
      ) : summary ? (
        <>
          <div className="financial-summary-grid">
            <article className="financial-card">
              <div className="financial-card-head">
                <h3>本地订单金额</h3>
                <p>订单金额汇总</p>
              </div>
              <strong>{formatWon(summary.totalOrderAmount)}</strong>
              <small>{summary.totalOrders} 条本地 Naver 订单</small>
            </article>
            <article className="financial-card">
              <div className="financial-card-head">
                <h3>今日订单金额</h3>
                <p>按本地订单日期</p>
              </div>
              <strong>{formatWon(summary.todayOrderAmount)}</strong>
              <small>{summary.todayOrders} 条订单</small>
            </article>
            <article className="financial-card">
              <div className="financial-card-head">
                <h3>本周订单金额</h3>
                <p>本地订单金额口径</p>
              </div>
              <strong>{formatWon(summary.weekOrderAmount)}</strong>
              <small>本月 {formatWon(summary.monthOrderAmount)}</small>
            </article>
          </div>
          <div className="business-capability-grid compact">
            <article className="business-capability-card info">
              <div className="business-capability-head"><strong>统计口径</strong><span>本地订单</span></div>
              <p>该金额来自本地 orders 的订单金额汇总。</p>
              <small>不会展示完整订单号或买家隐私。</small>
            </article>
            <article className="business-capability-card info">
              <div className="business-capability-head"><strong>店铺汇总</strong><span>{topStore ? formatWon(topStore.amount) : '暂无金额'}</span></div>
              <p>{topStore ? `${topStore.name}：${topStore.orders} 条订单。` : '当前店铺暂无可汇总订单。'}</p>
              <small>只统计当前 Naver 店铺本地运营订单。</small>
            </article>
            <article className="business-capability-card info">
              <div className="business-capability-head"><strong>商品汇总</strong><span>{topProduct ? formatWon(topProduct.amount) : '暂无金额'}</span></div>
              <p>{topProduct ? `${topProduct.name}：${topProduct.quantity || topProduct.orders} 件 / ${topProduct.orders} 条订单。` : '当前暂无商品金额排行。'}</p>
              <small>不展示完整商品编号。</small>
            </article>
            <article className="business-capability-card muted">
              <div className="business-capability-head"><strong>结算 / 利润</strong><span>待接入</span></div>
              <p>当前不等于平台结算金额，不等于利润，也不等于账户可提取资金。</p>
              <small>Naver 结算、利润和提现余额需要后续单独阶段确认。</small>
            </article>
            <article className="business-capability-card muted">
              <div className="business-capability-head"><strong>取消 / 退款金额</strong><span>待接入</span></div>
              <p>{summary.refundBusinessMessage}</p>
              <small>当前不把订单金额自动扣减为净销售额。</small>
            </article>
          </div>
          <p className="mock-sync-note">{summary.boundaryMessage}</p>
          <TechnicalDetails
            description="技术口径仅供管理员排查，主页面不展示完整订单标识或买家隐私。"
            items={[
              { label: 'scope', value: summary.scope },
              { label: 'source', value: summary.source },
              { label: 'store_id', value: selectedStoreId },
              { label: 'total_orders', value: summary.totalOrders },
              { label: 'total_order_amount', value: summary.totalOrderAmount },
              { label: 'today_order_amount', value: summary.todayOrderAmount },
              { label: 'week_order_amount', value: summary.weekOrderAmount },
              { label: 'month_order_amount', value: summary.monthOrderAmount },
              { label: 'store_breakdown_count', value: summary.storeBreakdown?.length || 0 },
              { label: 'product_breakdown_count', value: summary.productBreakdown?.length || 0 },
              { label: 'canceled_orders', value: summary.canceledOrders },
              { label: 'canceled_order_amount_observed', value: summary.canceledOrderAmountObserved },
              { label: 'refund_amount_available', value: summary.refundAmountAvailable },
              { label: 'net_sales_available', value: summary.netSalesAvailable },
              { label: 'latest_ordered_at', value: formatKstDateTimeWithLabel(summary.latestOrderedAt) },
              { label: 'platform_sales_api_called', value: summary.platformSalesApiCalled },
              { label: 'platform_settlement_api_called', value: summary.platformSettlementApiCalled },
              { label: 'settlement_amount_available', value: summary.settlementAmountAvailable },
              { label: 'profit_available', value: summary.profitAvailable },
              { label: 'withdrawable_balance_available', value: summary.withdrawableBalanceAvailable },
              { label: 'formal_order_sync_open', value: summary.formalOrderSyncOpen },
            ]}
          />
        </>
      ) : (
        <EmptyState title="正在读取 Naver 本地订单金额" description="只读取本地订单列表，不请求 Naver 平台。" />
      )}
    </section>
  );
}

export default function Sales() {
  const { selectedStoreId } = useStoreContext();
  const defaultFilters = useMemo(() => ({
    startDate: getKstDateOffsetString(-7),
    endDate: getKstTodayString(),
    platform: '',
    store: '',
    page: 1,
    pageSize: 6,
  }), []);
  const [filters, setFilters] = useState(defaultFilters);
  const [draftFilters, setDraftFilters] = useState(defaultFilters);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [ranking, setRanking] = useState({ stores: [], platforms: [], products: [] });
  const [details, setDetails] = useState({ data: [], total: 0, page: 1, pageSize: 6 });
  const [trend, setTrend] = useState([]);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(async (nextFilters = filters) => {
    setLoading(true);
    setLoadError('');
    try {
      const report = await dataProvider.getSalesReport({ ...nextFilters, storeId: selectedStoreId });

      setSummary(report.summary);
      setRanking(report.ranking);
      setDetails(report.details);
      setTrend(report.trend);
    } catch (error) {
      setLoadError(error.message || '销售数据加载失败');
      setSummary(null);
      setRanking({ stores: [], platforms: [], products: [] });
      setDetails({ data: [], total: 0, page: 1, pageSize: nextFilters.pageSize || 6 });
      setTrend([]);
    } finally {
      setLoading(false);
    }
  }, [filters, selectedStoreId]);

  useEffect(() => {
    load();
  }, [load]);

  const maxTrendSales = Math.max(...trend.map((item) => item.sales), 1);
  const platformTotal = ranking.platforms.reduce((sum, item) => sum + item.sales, 0);

  return (
    <>
      <PageHeader
        title="销售额统计"
        description="查看销售额、订单数、退款、净销售额和结算预览。技术明细默认折叠。"
        actions={<button className="button ghost" onClick={() => load()}>刷新看板</button>}
      />

      <NaverOrderSalesSummaryPanel />
      <CoupangFinancialPreviewPanel />
      {loadError ? <EmptyState title="销售数据加载失败" description={loadError} /> : null}

      <FilterPanel>
        <div className="filter-row">
          <label className="form-field"><span>开始日期</span><input type="date" value={draftFilters.startDate} onChange={(event) => setDraftFilters({ ...draftFilters, startDate: event.target.value })} /></label>
          <label className="form-field"><span>结束日期</span><input type="date" value={draftFilters.endDate} onChange={(event) => setDraftFilters({ ...draftFilters, endDate: event.target.value })} /></label>
          <label className="form-field"><span>平台</span><select value={draftFilters.platform} onChange={(event) => setDraftFilters({ ...draftFilters, platform: event.target.value })}><option value="">全部平台</option>{platforms.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="form-field"><span>店铺</span><select value={draftFilters.store} onChange={(event) => setDraftFilters({ ...draftFilters, store: event.target.value })}><option value="">全部店铺</option>{stores.map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
        <div className="filter-actions">
          <button className="button ghost" onClick={() => {
            const clean = { ...defaultFilters };
            setDraftFilters(clean);
            setFilters(clean);
          }}>重置</button>
          <button className="button primary" onClick={() => setFilters({ ...draftFilters, page: 1 })}>应用筛选</button>
        </div>
      </FilterPanel>

      {summary && (
        <section className="summary-grid">
          <SummaryCard title="总销售额" value={formatWon(summary.totalSales)} note="统一按 KRW 展示" tone="success" />
          <SummaryCard title="总订单数" value={summary.totalOrders.toLocaleString()} note="筛选范围内订单" tone="info" />
          <SummaryCard title="退款金额" value={formatWon(summary.refundAmount)} note="含已登记退款" tone="danger" />
          <SummaryCard title="净销售额" value={formatWon(summary.totalNetSales)} note="销售额减优惠和退款" tone="success" />
          <SummaryCard title="客单价" value={formatWon(summary.averageOrderValue)} note="总销售额 / 总订单数" tone="warning" />
          <SummaryCard title="待处理订单" value={summary.pendingOrders.toLocaleString()} note="待发货与异常订单" tone="info" />
        </section>
      )}

      <section className="panel-grid">
        <article className="visual-card">
          <h3>店铺销售排行</h3>
          <p>按筛选范围内累计销售额排序。</p>
          <div className="ranking-list">
            {ranking.stores.length ? ranking.stores.map((item, index) => {
              const width = ranking.stores[0] ? Math.max((item.sales / ranking.stores[0].sales) * 100, 10) : 0;
              return (
                <div key={item.name} className="ranking-row">
                  <div>
                    <strong>{index + 1}. {item.name}</strong>
                    <div className="ranking-meta">{item.platform} · {item.orders} 单</div>
                  </div>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${width}%` }} /></div>
                  <span className="bar-text">{formatWon(item.sales)}</span>
                </div>
              );
            }) : <EmptyState title="暂无排行数据" description="当前筛选范围没有店铺销售记录。" />}
          </div>
        </article>

        <article className="visual-card">
          <h3>平台销售占比</h3>
          <p>按平台统计销售额占比。</p>
          <div className="ratio-list">
            {ranking.platforms.length ? ranking.platforms.map((item) => {
              const ratio = platformTotal ? (item.sales / platformTotal) * 100 : 0;
              return (
                <div key={item.name} className="ratio-row">
                  <strong>{item.name}</strong>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.max(ratio, 8)}%` }} /></div>
                  <span className="bar-text">{ratio.toFixed(1)}%</span>
                </div>
              );
            }) : <EmptyState title="暂无占比数据" description="当前没有平台销售额可统计。" />}
          </div>
        </article>
      </section>

      <section className="panel-grid">
        <article className="visual-card">
          <h3>商品销售排行</h3>
          <p>按热销商品累计销售额与订单量排序。</p>
          <div className="ranking-list">
            {ranking.products.length ? ranking.products.map((item, index) => {
              const width = ranking.products[0] ? Math.max((item.sales / ranking.products[0].sales) * 100, 10) : 0;
              return (
                <div key={item.name} className="ranking-row">
                  <div>
                    <strong>{index + 1}. {item.name}</strong>
                    <div className="ranking-meta">{item.store} · {item.orders} 单</div>
                  </div>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${width}%` }} /></div>
                  <span className="bar-text">{formatWon(item.sales)}</span>
                </div>
              );
            }) : <EmptyState title="暂无商品排行" description="当前筛选范围没有热销商品数据。" />}
          </div>
        </article>

        <article className="visual-card">
          <h3>销售趋势</h3>
          <p>按每日销售额观察波动。</p>
          {trend.length ? (
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
          ) : <EmptyState title="暂无趋势数据" description="请调整筛选范围后重试。" />}
        </article>
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>销售明细</h2>
            <p>展示销售额、优惠券、退款和净销售额明细。</p>
          </div>
        </div>
        <DataTable columns={columns} rows={details.data} loading={loading} />
        <Pagination page={filters.page} pageSize={filters.pageSize} total={details.total} onChange={(page) => setFilters({ ...filters, page })} />
      </section>
    </>
  );
}
