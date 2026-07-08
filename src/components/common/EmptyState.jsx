export default function EmptyState({
  title = '暂无数据',
  description = '当前筛选条件下没有可展示的内容。',
  actions = null,
}) {
  return (
    <div className="empty-panel">
      <strong>{title}</strong>
      <p>{description}</p>
      {actions ? <div className="empty-actions">{actions}</div> : null}
    </div>
  );
}
