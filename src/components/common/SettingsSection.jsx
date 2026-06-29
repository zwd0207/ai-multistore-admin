export default function SettingsSection({ title, description, children, actions }) {
  return (
    <section className="content-card settings-section">
      <div className="card-title">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
