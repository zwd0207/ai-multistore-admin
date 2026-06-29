export default function DataTable({ columns, rows, loading, rowKey = 'id', onEdit, onDelete, renderActions }) {
  if (loading) return <div className="table-state"><span className="spinner" />正在加载数据…</div>;
  return (
    <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column.key}>{column.title}</th>)}{(onEdit || onDelete || renderActions) && <th>操作</th>}</tr></thead>
      <tbody>{rows.length ? rows.map((row) => <tr key={row[rowKey]}>{columns.map((column) => <td key={column.key}>{column.render ? column.render(row[column.key], row) : row[column.key]}</td>)}{(onEdit || onDelete || renderActions) && <td className="table-actions">{renderActions ? renderActions(row) : <>{onEdit && <button onClick={() => onEdit(row)}>编辑</button>}{onDelete && <button className="danger-text" onClick={() => onDelete(row)}>删除</button>}</>}</td>}</tr>) : <tr><td colSpan={columns.length + 1}><div className="empty-state">暂无符合条件的数据</div></td></tr>}</tbody>
    </table></div>
  );
}
