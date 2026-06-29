import BackendReadOnlyPage from '../components/common/BackendReadOnlyPage';
import StatusBadge from '../components/common/StatusBadge';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import MockEnvironment from './MockEnvironment';

const columns = [
  { key: 'name', title: '环境名称', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'deviceType', title: '设备类型' },
  { key: 'osName', title: '系统' },
  { key: 'browserName', title: '浏览器' },
  { key: 'ipLabel', title: 'IP 标识' },
  { key: 'proxyLabel', title: '代理标识' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'lastUsedAt', title: '最近使用' },
  { key: 'remark', title: '备注' },
];

function BackendEnvironment() {
  return (
    <BackendReadOnlyPage
      title="环境管理"
      description="复用 Codex1 device-environments，只读展示当前店铺登录环境、设备与代理标签。"
      resourceName="环境"
      loadData={dataProvider.getDeviceEnvironments}
      columns={columns}
    />
  );
}

export default function Environment() {
  if (isBackendSource) return <BackendEnvironment />;
  return <MockEnvironment />;
}
