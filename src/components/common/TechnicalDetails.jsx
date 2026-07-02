import { Fragment } from 'react';

function redactValue(value) {
  if (value === null || value === undefined) return '-';
  if (Array.isArray(value)) return value.length ? value.join(', ') : '-';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export default function TechnicalDetails({ title = '查看技术详情', description, items = [], children }) {
  const safeItems = items.filter((item) => item && item.label);

  return (
    <details className="developer-details technical-details">
      <summary>{title}</summary>
      {description ? <p>{description}</p> : null}
      {safeItems.length ? (
        <div className="sync-result-grid">
          {safeItems.map((item) => (
            <Fragment key={item.label}>
              <span>{item.label}</span>
              <strong>{redactValue(item.value)}</strong>
            </Fragment>
          ))}
        </div>
      ) : null}
      {children}
    </details>
  );
}
