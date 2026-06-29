import StatusBadge from './StatusBadge';

export default function RiskPanel({ title = '风险提示', items = [] }) {
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      {items.length ? (
        <div className="risk-panel">
          {items.map((item, index) => (
            <article key={item.id || index} className="risk-item">
              <div className="risk-item-head">
                <strong>{item.title || `提示 ${index + 1}`}</strong>
                {item.status && <StatusBadge value={item.status} />}
              </div>
              <p>{item.description || item}</p>
              {item.time && <time>{item.time}</time>}
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state compact">暂无风险记录</div>
      )}
    </section>
  );
}
