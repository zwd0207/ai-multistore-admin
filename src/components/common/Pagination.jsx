export default function Pagination({ page, pageSize, total, onChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination">
      <span>共 {total} 条</span>
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>上一页</button>
      <strong>{page} / {pages}</strong>
      <button disabled={page >= pages} onClick={() => onChange(page + 1)}>下一页</button>
    </div>
  );
}
