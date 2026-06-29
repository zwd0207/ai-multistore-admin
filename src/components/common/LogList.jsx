import StatusBadge from './StatusBadge';

export default function LogList({ items = [], emptyText = '暂无记录' }) {
  if (!items.length) {
    return <div className="empty-state compact">{emptyText}</div>;
  }

  return (
    <div className="log-list">
      {items.map((item) => (
        <article key={item.id} className="log-item">
          <div className="log-item-head">
            <div>
              <strong>{item.title || item.action}</strong>
              {(item.account || item.location || item.sender) && (
                <div className="ranking-meta">
                  {[item.account, item.location, item.sender].filter(Boolean).join(' · ')}
                </div>
              )}
            </div>
            {item.status && <StatusBadge value={item.status} />}
          </div>
          <p>{item.description || item.summary || '—'}</p>
          <time>{item.time || item.receivedAt}</time>
        </article>
      ))}
    </div>
  );
}
