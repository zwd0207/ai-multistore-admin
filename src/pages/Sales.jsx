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
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
import { formatKstDateTimeWithLabel, getKstDateOffsetString, getKstTodayString } from '../utils/time';

const platforms = ['Naver', 'Coupang', 'Gmarket', '11st', 'Auction'];
const stores = ['首尔美妆测试店', '韩国本土运动鞋店', 'Gmarket 精品店', '11st 韩系生活馆', 'K-Beauty 快闪店', 'Auction 折扣店', 'Coupang 联调店'];
const MAX_FINANCIAL_PREVIEW_DAYS = 7;

const formatWon = (value) => `${Number(value || 0).toLocaleString()} KRW`;

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
  if (!startDate || !endDate) return '请选择 start_date 和 end_date。';
  if (startDate > endDate) return 'start_date 不能晚于 end_date。';
  const span = daySpan(startDate, endDate);
  if (!span || span < 1) return '日期格式无效。';
  if (span > MAX_FINANCIAL_PREVIEW_DAYS) return `当前系统预览阶段最多 ${MAX_FINANCIAL_PREVIEW_DAYS} 天。`;
  if (sales && endDate >= getKstTodayString()) return 'Sales Preview 的 end_date 不能是今天或未来日期。';
  if (maxPages !== undefined && (Number(maxPages) < 1 || Number(maxPages) > 3)) return 'max_pages 必须在 1 到 3 之间。';
  return '';
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '真实只读检测开关未启用，后端已拒绝发起外部请求。',
    real_api_test_disabled: '真实只读检测开关未启用，后端已拒绝发起外部请求。',
    ip_not_allowed: '当前服务器公网 IP 不在 Coupang OpenAPI allowlist 中。',
    auth_failed: 'Coupang 认证失败，请检查凭证、vendorId、权限或 IP allowlist。',
    CREDENTIAL_DECRYPT_FAILED: '本地凭证解密失败，请在当前加密 key 环境下重新保存凭证。',
    decrypt_failed: '本地凭证解密失败，请在当前加密 key 环境下重新保存凭证。',
    SALES_DATE_NOT_AVAILABLE: '销售确认日期可能只能查询已完成确认的历史日期，请避开今天或未来日期。',
    readonly_request_failed: 'Coupang 只读请求失败，请检查日期、权限或接口参数。',
  };
  return messages[code] || error?.message || 'Coupang 财务 preview 请求失败，请检查 Codex1 后端状态。';
}

function safeEntries(object = {}) {
  return Object.entries(object || {}).filter(([key]) => {
    const normalized = String(key).replace(/[_-]/g, '').toLowerCase();
    return !['bankaccountholder', 'bankname', 'bankaccount', 'accesskey', 'secretkey', 'authorization', 'signature', 'token'].some((item) => normalized.includes(item));
  }).filter(([, value]) => !(Array.isArray(value) && value.length === 0));
}

function KeyValueGrid({ title, data }) {
  const entries = safeEntries(data);
  if (!entries.length) return null;
  return (
    <div className="financial-preview-block">
      <h3>{title}</h3>
      <div className="sync-result-grid">
        {entries.map(([key, value]) => (
          <span key={key}>{key}</span>
        )).flatMap((label, index) => {
          const [key, value] = entries[index];
          return [label, <strong key={`${key}-value`}>{Array.isArray(value) ? value.join(', ') : String(value ?? '-')}</strong>];
        })}
      </div>
    </div>
  );
}

function SampleRowsTable({ rows = [] }) {
  if (!rows.length) return <div className="empty-state compact">暂无 sample_rows。</div>;
  const keys = Array.from(new Set(rows.flatMap((row) => safeEntries(row).map(([key]) => key)))).slice(0, 12);
  if (!keys.length) return <div className="empty-state compact">sample_rows 中没有可展示字段。</div>;
  return (
    <div className="financial-preview-block">
      <h3>sample_rows</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{keys.map((key) => <th key={key}>{key}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`sample-row-${rowIndex + 1}`}>
                {keys.map((key) => <td key={key}>{String(row[key] ?? '-')}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PerMonthTable({ rows = [] }) {
  if (!rows.length) return null;
  return (
    <div className="financial-preview-block">
      <h3>per_month</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>revenueRecognitionYearMonth</th>
              <th>item_count</th>
              <th>sample_ids</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.revenueRecognitionYearMonth}>
                <td><strong>{item.revenueRecognitionYearMonth}</strong></td>
                <td>{item.itemCount}</td>
                <td>{item.sampleIds?.length ? item.sampleIds.join(', ') : '[]'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FinancialPreviewResult({ result, type }) {
  if (!result) return null;
  const isSales = type === 'sales';
  const emptyMessage = isSales ? '查询成功，无销售明细数据。' : '查询成功，无结算明细数据。';

  return (
    <div className="coupang-sync-result">
      <div className="sync-result-banner">{result.totalRows === 0 ? emptyMessage : '查询完成，结果如下。'}</div>
      <div className="sync-result-grid">
        <span>total_rows</span><strong>{result.totalRows}</strong>
        <span>page_count</span><strong>{result.pageCount}</strong>
        <span>next_cursor_exists</span><strong>{result.nextCursorExists ? 'true' : 'false'}</strong>
        <span>date window</span><strong>{result.startDate} ~ {result.endDate}</strong>
        {result.windowStartAt || result.windowEndAt ? <><span>KST window</span><strong>{formatKstDateTimeWithLabel(result.windowStartAt)} / {formatKstDateTimeWithLabel(result.windowEndAt)}</strong></> : null}
        <span>sample_ids</span><strong>{result.sampleIds?.length ? result.sampleIds.join(', ') : '[]'}</strong>
        {result.months?.length ? <><span>months</span><strong>{result.months.join(', ')}</strong></> : null}
      </div>
      <KeyValueGrid title="summary_totals" data={result.summaryTotals} />
      <PerMonthTable rows={result.perMonth} />
      <SampleRowsTable rows={result.sampleRows} />
      <KeyValueGrid title="field_mapping_suggestion" data={result.fieldMappingSuggestion} />
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
      setSalesMessage(isBackendSource ? 'Sales Preview 完成：只读查询，不写入销售表。' : 'mock 模式仅显示空态，不伪造 Coupang 销售明细。');
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
      setSettlementMessage(isBackendSource ? 'Settlement Preview 完成：按月份只读查询，不写入结算表。' : 'mock 模式仅显示空态，不伪造 Coupang 结算明细。');
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
          <h2>Coupang 财务只读 Preview</h2>
          <p>只调用 Coupang 只读接口；本页面不提供正式入库按钮，不会对 Coupang 平台做写操作。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>

      <div className="financial-preview-grid">
        <article className="financial-preview-card">
          <h3>Coupang 销售明细 Preview</h3>
          <p className="mock-sync-note">当前系统预览阶段最多 7 天；end_date 不能是今天或未来日期。0 数据表示查询成功但没有销售明细。</p>
          <div className="sync-control-grid financial-control-grid">
            <label>
              <span>start_date</span>
              <input type="date" value={salesForm.startDate} onChange={(event) => setSalesForm({ ...salesForm, startDate: event.target.value })} />
            </label>
            <label>
              <span>end_date</span>
              <input type="date" value={salesForm.endDate} onChange={(event) => setSalesForm({ ...salesForm, endDate: event.target.value })} />
            </label>
            <label>
              <span>max_pages</span>
              <input type="number" min="1" max="3" value={salesForm.maxPages} onChange={(event) => setSalesForm({ ...salesForm, maxPages: clampMaxPages(event.target.value) })} />
            </label>
            <button className="button primary" onClick={runSalesPreview} disabled={Boolean(loadingAction)}>查询销售明细 Preview</button>
          </div>
          {salesValidation && <div className="sync-inline-warning">{salesValidation}</div>}
          {loadingAction === 'sales' && <div className="sync-inline-warning">Sales Preview 请求中...</div>}
          {salesMessage && <div className="mock-sync-success">{salesMessage}</div>}
          {salesError && <div className="mock-sync-error">{salesError}</div>}
          <FinancialPreviewResult result={salesResult} type="sales" />
        </article>

        <article className="financial-preview-card">
          <h3>Coupang 结算明细 Preview</h3>
          <p className="mock-sync-note">结算接口按 revenueRecognitionYearMonth=YYYY-MM 查询；start_date/end_date 只用于派生月份，不是按日精确截断。</p>
          <div className="sync-control-grid financial-control-grid">
            <label>
              <span>start_date</span>
              <input type="date" value={settlementForm.startDate} onChange={(event) => setSettlementForm({ ...settlementForm, startDate: event.target.value })} />
            </label>
            <label>
              <span>end_date</span>
              <input type="date" value={settlementForm.endDate} onChange={(event) => setSettlementForm({ ...settlementForm, endDate: event.target.value })} />
            </label>
            <button className="button primary" onClick={runSettlementPreview} disabled={Boolean(loadingAction)}>查询结算明细 Preview</button>
          </div>
          {settlementValidation && <div className="sync-inline-warning">{settlementValidation}</div>}
          {loadingAction === 'settlement' && <div className="sync-inline-warning">Settlement Preview 请求中...</div>}
          {settlementMessage && <div className="mock-sync-success">{settlementMessage}</div>}
          {settlementError && <div className="mock-sync-error">{settlementError}</div>}
          <FinancialPreviewResult result={settlementResult} type="settlement" />
        </article>
      </div>
    </section>
  );
}

export default function Sales() {
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

  const load = useCallback(async (nextFilters = filters) => {
    setLoading(true);
    try {
      const [summaryData, rankingData, detailData, trendData] = await Promise.all([
        mockApi.getSalesSummary(nextFilters),
        mockApi.getSalesRanking(nextFilters),
        mockApi.getSalesDetails(nextFilters),
        mockApi.getSalesTrend(nextFilters),
      ]);

      setSummary(summaryData);
      setRanking(rankingData);
      setDetails(detailData);
      setTrend(trendData);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const maxTrendSales = Math.max(...trend.map((item) => item.sales), 1);
  const platformTotal = ranking.platforms.reduce((sum, item) => sum + item.sales, 0);

  return (
    <>
      <PageHeader
        title="销售数据"
        description="按平台、店铺与时间范围观察销售表现、退款和净销售额。"
        actions={<button className="button ghost" onClick={() => load()}>刷新看板</button>}
      />

      <CoupangFinancialPreviewPanel />

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
          <SummaryCard title="总订单数" value={summary.totalOrders.toLocaleString()} note="筛选范围内已支付订单" tone="info" />
          <SummaryCard title="退款金额" value={formatWon(summary.refundAmount)} note="含已登记退款工单" tone="danger" />
          <SummaryCard title="净销售额" value={formatWon(summary.totalNetSales)} note="销售额 - 优惠券 - 退款" tone="success" />
          <SummaryCard title="客单价" value={formatWon(summary.averageOrderValue)} note="总销售额 / 总订单数" tone="warning" />
          <SummaryCard title="待处理订单数" value={summary.pendingOrders.toLocaleString()} note="待发货与异常订单" tone="info" />
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
            }) : <EmptyState title="暂无占比数据" description="当前没有平台销售额可供统计。" />}
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
          <p>以每日销售额趋势快速观察波动。</p>
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
            <h2>销售明细表格</h2>
            <p>展示销售额、优惠券金额、退款金额与净销售额明细。</p>
          </div>
        </div>
        <DataTable columns={columns} rows={details.data} loading={loading} />
        <Pagination page={filters.page} pageSize={filters.pageSize} total={details.total} onChange={(page) => setFilters({ ...filters, page })} />
      </section>
    </>
  );
}
