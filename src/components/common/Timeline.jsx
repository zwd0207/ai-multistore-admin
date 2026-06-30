import StatusBadge from './StatusBadge';
import { formatKstDateTimeWithLabel } from '../../utils/time';

export default function Timeline({ items = [] }) {
  if (!items.length) {
    return <div className="empty-state compact">暂无时间线记录</div>;
  }

  return (
    <div className="timeline">
      {items.map((item) => (
        <div key={item.id} className="timeline-item">
          <span className="timeline-dot" />
          <div className="timeline-content">
            <div className="timeline-head">
              <strong>{item.title}</strong>
              {item.status && <StatusBadge value={item.status} />}
            </div>
            <p>{item.description}</p>
            <time>{formatKstDateTimeWithLabel(item.time)}</time>
          </div>
        </div>
      ))}
    </div>
  );
}
