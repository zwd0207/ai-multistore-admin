import { useEffect, useState } from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SummaryCard from '../components/common/SummaryCard';
import StatusBadge from '../components/common/StatusBadge';
import mockApi from '../services/mockApi';

const platforms = ['Naver', 'Coupang', 'Gmarket', '11街', '옥션'];
const stores = ['스마트스토어 뷰티샵', '韩国本土运动鞋店', 'Gmarket 럭셔리 골프관', '11街 韩系生活馆', 'K-Beauty 글로벌샵', '옥션 아웃도어 셀렉트', 'Coupang 키즈 패션랩'];

const formatWon = (value) => `${Number(value || 0).toLocaleString()}원`;

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

export default function Sales() {
  const [filters, setFilters] = useState({
    startDate: '2026-06-23',
    endDate: '2026-06-29',
    platform: '',
    store: '',
    page: 1,
    pageSize: 6,
  });
  const [draftFilters, setDraftFilters] = useState(filters);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [ranking, setRanking] = useState({ stores: [], platforms: [], products: [] });
  const [details, setDetails] = useState({ data: [], total: 0, page: 1, pageSize: 6 });
  const [trend, setTrend] = useState([]);

  const load = async (nextFilters = filters) => {
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
  };

  useEffect(() => {
    load();
  }, [filters]);

  const maxTrendSales = Math.max(...trend.map((item) => item.sales), 1);
  const platformTotal = ranking.platforms.reduce((sum, item) => sum + item.sales, 0);

  return (
    <>
      <PageHeader
        title="销售数据"
        description="按平台、店铺与时间范围观察销售表现、退款和净销售额。"
        actions={<button className="button ghost" onClick={() => load()}>刷新看板</button>}
      />

      <FilterPanel>
        <div className="filter-row">
          <label className="form-field"><span>开始日期</span><input type="date" value={draftFilters.startDate} onChange={(event) => setDraftFilters({ ...draftFilters, startDate: event.target.value })} /></label>
          <label className="form-field"><span>结束日期</span><input type="date" value={draftFilters.endDate} onChange={(event) => setDraftFilters({ ...draftFilters, endDate: event.target.value })} /></label>
          <label className="form-field"><span>平台</span><select value={draftFilters.platform} onChange={(event) => setDraftFilters({ ...draftFilters, platform: event.target.value })}><option value="">全部平台</option>{platforms.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="form-field"><span>店铺</span><select value={draftFilters.store} onChange={(event) => setDraftFilters({ ...draftFilters, store: event.target.value })}><option value="">全部店铺</option>{stores.map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
        <div className="filter-actions">
          <button className="button ghost" onClick={() => {
            const clean = { startDate: '2026-06-23', endDate: '2026-06-29', platform: '', store: '', page: 1, pageSize: 6 };
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
          <h3>简单趋势展示</h3>
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
