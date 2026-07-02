import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';

const api = {
  list: dataProvider.getStores,
  create: isBackendSource ? dataProvider.createStore : mockApi.createStore,
  update: isBackendSource ? dataProvider.updateStore : mockApi.updateStore,
  remove: mockApi.deleteStore,
};

const platformOptions = ['Naver', 'Coupang', 'Gmarket', '11st', 'Auction'];
const statusOptions = ['正常运营', '审核中', '申诉中', '暂停使用'];
const columns = [
  { key: 'name', title: '店铺名称', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'manager', title: '负责人' },
  { key: 'region', title: '地区' },
  { key: 'products', title: '商品数' },
  { key: 'status', title: '运营状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'updatedAt', title: '最近更新' },
];
const fields = [
  { key: 'name', label: '店铺名称', required: true },
  { key: 'platform', label: '平台', type: 'select', required: true, options: platformOptions },
  { key: 'manager', label: '负责人' },
  { key: 'region', label: '地区', required: true },
  { key: 'language', label: '语言', required: true },
  { key: 'status', label: '运营状态', type: 'select', required: true, options: statusOptions },
  { key: 'remark', label: '备注' },
];

export default function Stores() {
  const { selectedStoreId, refreshStores } = useStoreContext();

  return (
    <ResourcePage
      title="店铺管理"
      description="统一管理 Naver、Coupang 等平台店铺和运营状态。"
      resourceName="店铺"
      api={api}
      columns={columns}
      fields={fields}
      statuses={statusOptions}
      platforms={platformOptions}
      initialForm={{
        name: '',
        platform: 'Naver',
        manager: '',
        region: 'KR',
        language: 'ko-KR',
        status: '正常运营',
        remark: '',
      }}
      canCreate
      canEdit
      canDelete={!isBackendSource}
      onSaved={(store) => refreshStores({ preferredStoreId: selectedStoreId || store?.id })}
    />
  );
}
