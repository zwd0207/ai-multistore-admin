import PageHeader from './PageHeader';

export default function PlaceholderPage({ title, description, icon, features }) {
  return <><PageHeader title={title} description={description} actions={<button className="button ghost">↻ 刷新</button>} /><section className="content-card placeholder-card"><div className="placeholder-icon">{icon}</div><h2>{title}基础页面已就绪</h2><p>路由、布局和模块入口已完成，详细业务能力将在下一阶段接入。</p><div className="feature-chips">{features.map((feature) => <span key={feature}>✓ {feature}</span>)}</div></section></>;
}
