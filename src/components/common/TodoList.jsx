import StatusBadge from './StatusBadge';

export default function TodoList({ items = [] }) {
  return (
    <div className="todo-panel-list">
      {items.map((item) => (
        <article key={item.id} className="todo-panel-item">
          <div>
            <strong>{item.title}</strong>
            <p>{item.description}</p>
          </div>
          <StatusBadge value={item.status} />
        </article>
      ))}
    </div>
  );
}
