export default function EmptyState({ title = '暂无数据', description = '当前筛选条件下没有可展示的内容。' }) {
  return (
    <div className="empty-panel">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}
