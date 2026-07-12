import { formatKstDateTimeWithLabel, toKstDisplayDate } from '../../utils/time';

const TIME_COLUMN_KEYS = new Set([
  'time',
  'createdAt',
  'updatedAt',
  'startedAt',
  'finishedAt',
  'lastCheckedAt',
  'lastTestedAt',
  'lastLoginCheckAt',
  'tokenExpiresAt',
  'deadlineAt',
  'submittedAt',
  'resolvedAt',
  'receivedAt',
  'lastReceivedAt',
  'lastReplyAt',
  'lastUsedAt',
  'lastLoginAt',
  'docCheckedAt',
  'testedAt',
  'deadline',
]);

function renderCell(column, row) {
  const value = row[column.key];
  if (column.render) return column.render(value, row);
  if (column.key === 'date') return toKstDisplayDate(value);
  if (TIME_COLUMN_KEYS.has(column.key)) return formatKstDateTimeWithLabel(value);
  return value ?? '-';
}

export default function DataTable({
  columns,
  rows = [],
  loading,
  rowKey = 'id',
  onEdit,
  onDelete,
  renderActions,
  renderExtraActions,
}) {
  if (loading) return <div className="table-state"><span className="spinner" />正在加载数据...</div>;

  const hasActions = onEdit || onDelete || renderActions || renderExtraActions;
  const actionColSpan = columns.length + (hasActions ? 1 : 0);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => <th key={column.key}>{column.title}</th>)}
            {hasActions && <th>操作</th>}
          </tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((row, index) => (
            <tr key={row[rowKey] ?? `${rowKey}-${index}`}>
              {columns.map((column) => <td key={column.key} data-label={column.title}>{renderCell(column, row)}</td>)}
              {hasActions && (
                <td className="table-actions" data-label="操作">
                  {renderActions ? renderActions(row) : (
                    <>
                      {onEdit && <button type="button" onClick={() => onEdit(row)}>编辑</button>}
                      {onDelete && <button type="button" className="danger-text" onClick={() => onDelete(row)}>删除</button>}
                    </>
                  )}
                  {renderExtraActions ? renderExtraActions(row) : null}
                </td>
              )}
            </tr>
          )) : (
            <tr>
              <td colSpan={actionColSpan}>
                <div className="empty-state">暂无符合条件的数据</div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
