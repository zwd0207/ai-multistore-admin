import BackendReadOnlyPage from '../components/common/BackendReadOnlyPage';
import StatusBadge from '../components/common/StatusBadge';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import MockEmails from './MockEmails';

const accountColumns = [
  { key: 'email', title: '邮箱地址', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'provider', title: '服务商' },
  { key: 'label', title: '账号标签' },
  { key: 'hasCredential', title: '凭证', render: (value) => (value ? '已配置' : '未配置') },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'lastCheckedAt', title: '最近检查' },
  { key: 'remark', title: '备注' },
];

const importantColumns = [
  { key: 'subject', title: '重要邮件', render: (value, row) => <div><strong>{value}</strong><small className="cell-subtitle">{row.snippet}</small></div> },
  { key: 'platform', title: '平台' },
  { key: 'type', title: '类型' },
  { key: 'sender', title: '发件人' },
  { key: 'priority', title: '优先级', render: (value) => <StatusBadge value={value} /> },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'receivedAt', title: '收件时间' },
];

function BackendEmails() {
  return (
    <>
      <BackendReadOnlyPage
        title="邮箱管理"
        description="读取 Codex1 email-accounts，只读展示当前店铺邮箱账号，不展示任何认证原文。"
        resourceName="邮箱账号"
        loadData={dataProvider.getEmailAccounts}
        columns={accountColumns}
      />
      <BackendReadOnlyPage
        title="重要邮件"
        description="读取 Codex1 important-emails，只读展示当前店铺的重要邮件摘要。"
        resourceName="重要邮件"
        loadData={dataProvider.getImportantEmails}
        columns={importantColumns}
      />
    </>
  );
}

export default function Emails() {
  if (isBackendSource) return <BackendEmails />;
  return <MockEmails />;
}
