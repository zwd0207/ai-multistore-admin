export default function Pagination({
  page, pageSize, total, onChange,
}) {
  const pages = Math.max(1, Math.ceil(Number(total || 0) / Number(pageSize || 1)));
  return (
    <div className="pagination">
      <span>共 {Number(total || 0).toLocaleString()} 条</span>
      <button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>上一页</button>
      <strong>{page} / {pages}</strong>
      <button type="button" disabled={page >= pages} onClick={() => onChange(page + 1)}>下一页</button>
    </div>
  );
}
