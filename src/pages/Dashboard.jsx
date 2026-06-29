import { useEffect, useState } from 'react';
import ActivityList from '../components/common/ActivityList';
import PageHeader from '../components/common/PageHeader';
import RiskPanel from '../components/common/RiskPanel';
import StatGrid from '../components/common/StatGrid';
import TodoList from '../components/common/TodoList';
import dataProvider from '../services/dataProvider';

const formatWon = (value) => `₩ ${Number(value || 0).toLocaleString()}`;

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [risks, setRisks] = useState([]);
  const [todos, setTodos] = useState([]);
  const [activities, setActivities] = useState({ logs: [], appeals: [], customers: [], emails: [] });
  const [trend, setTrend] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      dataProvider.getDashboardData(),
      dataProvider.getDashboardSalesTrend(),
    ])
      .then(([dashboardData, trendData]) => {
        setSummary(dashboardData.summary);
        setRisks(dashboardData.risks);
        setTodos(dashboardData.todos);
        setActivities(dashboardData.activities);
        setTrend(trendData);
      })
      .catch((requestError) => setError(requestError.message || '总览数据加载失败'));
  }, []);

  if (error) {
    return (
      <>
        <PageHeader title="运营总览" description="这里汇总了第一至第四阶段的核心运营、风险、待办和审计数据。" />
        <article className="content-card empty-state">
          <h2>总览数据加载失败</h2>
          <p>{error}</p>
        </article>
      </>
    );
  }

  if (!summary) return null;

  const stats = [
    { label: '店铺总数', value: summary.storeTotal, detail: '已接入多平台店铺', tone: 'positive' },
    { label: '商品总数', value: summary.productTotal, detail: '跨平台在售商品', tone: 'info' },
    { label: '今日订单数', value: summary.todayOrderCount, detail: '今日新增订单', tone: 'info' },
    { label: '今日销售额', value: formatWon(summary.todaySalesAmount), detail: '按 KRW 汇总', tone: 'positive' },
    { label: '待处理客服', value: summary.pendingCustomers, detail: '待回复客服咨询', tone: 'warning' },
    { label: '申诉中案件', value: summary.pendingAppeals, detail: '资料准备/审核中', tone: 'danger' },
    { label: '风险环境数量', value: summary.riskEnvironments, detail: '需要重点检查', tone: 'danger' },
    { label: '未读重要邮件', value: summary.unreadImportantEmails, detail: '优先跟进提醒', tone: 'warning' },
  ];

  const maxTrendSales = Math.max(...trend.map((item) => item.sales), 1);

  return (
    <>
      <PageHeader title="运营总览" description="这里汇总了第一至第四阶段的核心运营、风险、待办和审计数据。" actions={<button className="button primary">生成 AI 日报</button>} />
      <StatGrid items={stats} />

      <section className="panel-grid">
        <article className="content-card">
          <div className="card-title">
            <div><h2>简易销售趋势</h2><p>复用销售模块近 7 天趋势数据</p></div>
            <span className="period-chip">近 7 天</span>
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
            <div><h2>待办事项</h2><p>跨客服、申诉、订单、邮箱、环境的待处理事项</p></div>
          </div>
          <TodoList items={todos} />
        </article>
      </section>

      <section className="panel-grid">
        <RiskPanel title="风险提醒区域" items={risks} />

        <article className="content-card">
          <div className="card-title">
            <div><h2>最近动态区域</h2><p>最近操作日志、申诉更新、客服回复和邮件提醒</p></div>
          </div>
          <div className="settings-stack">
            <div>
              <h3>最近操作日志</h3>
              <ActivityList items={activities.logs.map((item) => ({ id: item.id, title: item.module, description: item.summary, status: item.status, time: item.time.slice(11, 16) }))} />
            </div>
            <div>
              <h3>最近申诉更新</h3>
              <ActivityList items={activities.appeals.map((item) => ({ ...item, time: item.time.slice(11, 16) }))} />
            </div>
            <div>
              <h3>最近客服回复</h3>
              <ActivityList items={activities.customers.map((item) => ({ ...item, time: item.time.slice(11, 16) }))} />
            </div>
            <div>
              <h3>最近邮件提醒</h3>
              <ActivityList items={activities.emails.map((item) => ({ ...item, time: item.time.slice(11, 16) }))} />
            </div>
          </div>
        </article>
      </section>
    </>
  );
}
