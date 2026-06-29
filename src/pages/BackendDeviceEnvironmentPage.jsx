import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider from '../services/dataProvider';

const api = {
  list: dataProvider.getDeviceEnvironments,
  create: dataProvider.createDeviceEnvironment,
  update: dataProvider.updateDeviceEnvironment,
  remove: async () => {
    throw new Error('本阶段不迁移删除操作');
  },
};

const statusOptions = ['active', 'inactive', 'warning'];
const deviceTypeOptions = ['desktop', 'laptop', 'mobile', 'tablet', 'server'];
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
const fields = [
  { key: 'name', label: '环境名称', required: true },
  { key: 'deviceType', label: '设备类型', type: 'select', required: true, options: deviceTypeOptions },
  { key: 'osName', label: '系统' },
  { key: 'browserName', label: '浏览器' },
  { key: 'ipLabel', label: 'IP 标识' },
  { key: 'proxyLabel', label: '代理标识' },
  { key: 'status', label: '状态', type: 'select', required: true, options: statusOptions },
  { key: 'lastUsedAt', label: '最近使用时间', type: 'datetime-local' },
  { key: 'remark', label: '备注' },
];

export default function BackendDeviceEnvironmentPage({ title, description, resourceName }) {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const canWrite = Boolean(selectedStoreId) && !storeLoading && !storeError;

  return (
    <ResourcePage
      title={title}
      description={storeError || (!selectedStoreId && !storeLoading ? '请先选择店铺' : description)}
      resourceName={resourceName}
      api={api}
      columns={columns}
      fields={fields}
      statuses={statusOptions}
      initialForm={{
        name: '',
        deviceType: 'desktop',
        osName: '',
        browserName: '',
        ipLabel: '',
        proxyLabel: '',
        status: 'active',
        lastUsedAt: '',
        remark: '',
      }}
      canCreate={canWrite}
      canEdit={canWrite}
      canDelete={false}
      extraParams={selectedStoreId ? { storeId: selectedStoreId } : {}}
      reloadKey={selectedStoreId}
    />
  );
}
