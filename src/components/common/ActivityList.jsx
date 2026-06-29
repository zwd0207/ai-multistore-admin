import StatusBadge from './StatusBadge';

export default function ActivityList({ items = [] }) {
  return (
    <div className="activity-list">
      {items.map((item) => (
        <div key={item.id || item.title}>
          <span className="activity-icon">✓</span>
          <p><strong>{item.title}</strong><small>{item.description}</small></p>
          <StatusBadge value={item.status} />
          <time>{item.time}</time>
        </div>
      ))}
    </div>
  );
}
