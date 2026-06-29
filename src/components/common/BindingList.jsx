export default function BindingList({ title, items = [], fields = [] }) {
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      {items.length ? (
        <div className="binding-list">
          {items.map((item, index) => (
            <article key={item.id || index} className="binding-item">
              {fields.map((field) => (
                <div key={field.key} className="binding-cell">
                  <span>{field.label}</span>
                  <strong>{item[field.key] ?? '—'}</strong>
                </div>
              ))}
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state compact">暂无绑定记录</div>
      )}
    </section>
  );
}
