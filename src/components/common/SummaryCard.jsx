export default function SummaryCard({ title, value, note, tone = 'default' }) {
  return (
    <article className={`summary-card tone-${tone}`}>
      <span>{title}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </article>
  );
}
