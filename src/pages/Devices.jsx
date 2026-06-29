import BackendReadOnlyPage from '../components/common/BackendReadOnlyPage';
import StatusBadge from '../components/common/StatusBadge';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import MockDevices from './MockDevices';

const backendColumns = [
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

function BackendDevices() {
  return (
    <BackendReadOnlyPage
      title="设备管理"
      description="读取 Codex1 device-environments，只展示当前店铺的设备与环境标签。"
      resourceName="设备环境"
      loadData={dataProvider.getDeviceEnvironments}
      columns={backendColumns}
    />
  );
}

export default function Devices() {
  if (isBackendSource) return <BackendDevices />;
  return <MockDevices />;
}
