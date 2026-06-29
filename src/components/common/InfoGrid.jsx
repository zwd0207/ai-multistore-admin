export default function InfoGrid({ items = [], columns = 2 }) {
  return (
    <div className="info-grid" style={{ '--info-columns': columns }}>
      {items.map((item) => (
        <div key={item.label} className="info-grid-item">
          <span>{item.label}</span>
          <div>{item.value ?? '—'}</div>
        </div>
      ))}
    </div>
  );
}
