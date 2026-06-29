export default function StatGrid({ items = [] }) {
  return (
    <div className="stat-grid">
      {items.map((item) => (
        <article className="stat-card" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
          <small className={item.tone}>{item.detail}</small>
        </article>
      ))}
    </div>
  );
}
