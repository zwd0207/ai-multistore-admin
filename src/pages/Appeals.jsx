import BackendReadOnlyPage from '../components/common/BackendReadOnlyPage';
import StatusBadge from '../components/common/StatusBadge';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import MockAppeals from './MockAppeals';

const columns = [
  { key: 'caseNo', title: '案件编号', render: (value, row) => <div><strong>{value || `CASE-${row.id}`}</strong><small className="cell-subtitle">{row.title}</small></div> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'type', title: '类型' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'deadlineAt', title: '截止时间' },
  { key: 'submittedAt', title: '提交时间' },
  { key: 'resolvedAt', title: '解决时间' },
  { key: 'summary', title: '摘要' },
  { key: 'actionRequired', title: '待处理动作' },
];

function BackendAppeals() {
  return (
    <BackendReadOnlyPage
      title="申诉管理"
      description="读取 Codex1 appeal-cases，只读展示当前店铺申诉案件。"
      resourceName="申诉案件"
      loadData={dataProvider.getAppealCases}
      columns={columns}
    />
  );
}

export default function Appeals() {
  if (isBackendSource) return <BackendAppeals />;
  return <MockAppeals />;
}
