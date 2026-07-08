import BackendReadOnlyPage from '../components/common/BackendReadOnlyPage';
import StatusBadge from '../components/common/StatusBadge';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import MockAppeals from './MockAppeals';

const columns = [
  { key: 'caseNo', title: '申诉编号', render: (value, row) => <div><strong>{value || `CASE-${row.id}`}</strong><small className="cell-subtitle">{row.title}</small></div> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'type', title: '类型' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'deadlineAt', title: '截止时间' },
  { key: 'submittedAt', title: '提交时间' },
  { key: 'resolvedAt', title: '解决时间' },
  { key: 'summary', title: '摘要' },
  { key: 'actionRequired', title: '下一步动作' },
];

function BackendAppeals() {
  return (
    <BackendReadOnlyPage
      title="申诉中心"
      description="查看当前店铺的申诉事项、截止时间和需要补充的资料。"
      resourceName="申诉案件"
      loadData={dataProvider.getAppealCases}
      columns={columns}
      emptyState={{
        title: '当前没有申诉案件',
        description: '当前没有申诉案件。你可以新建申诉资料档案，用于整理正品审核、侵权、结算冻结、客户投诉等资料。',
        actions: (
          <>
            <button type="button" className="button primary" disabled>新建申诉案件（暂未开放）</button>
            <button type="button" className="button ghost" disabled>查看资料模板（暂未开放）</button>
          </>
        ),
      }}
    />
  );
}

export default function Appeals() {
  if (isBackendSource) return <BackendAppeals />;
  return <MockAppeals />;
}
