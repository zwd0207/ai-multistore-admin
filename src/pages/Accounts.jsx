import BackendReadOnlyPage from '../components/common/BackendReadOnlyPage';
import StatusBadge from '../components/common/StatusBadge';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import MockAccounts from './MockAccounts';

const columns = [
  { key: 'name', title: '凭证名称', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'accessKeyStatus', title: '访问密钥状态' },
  { key: 'secretKeyStatus', title: '私密密钥状态' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '创建时间' },
  { key: 'updatedAt', title: '更新时间' },
];

function BackendAccounts() {
  return (
    <BackendReadOnlyPage
      title="账号管理"
      description="本阶段读取 Codex1 credentials，只显示凭证配置状态，不展示任何密钥原文。"
      resourceName="API 凭证"
      loadData={dataProvider.getCredentials}
      columns={columns}
    />
  );
}

export default function Accounts() {
  if (isBackendSource) return <BackendAccounts />;
  return <MockAccounts />;
}
