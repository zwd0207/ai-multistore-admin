import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
import { filterVisibleBusinessStores, normalizeStoreDisplay } from '../utils/storeDisplay';

const baseApi = {
  list: dataProvider.getStores,
  create: isBackendSource ? dataProvider.createStore : mockApi.createStore,
  update: isBackendSource ? dataProvider.updateStore : mockApi.updateStore,
  remove: mockApi.deleteStore,
};

const api = {
  ...baseApi,
  list: async (params = {}) => {
    const page = Math.max(Number(params.page) || 1, 1);
    const pageSize = Math.max(Number(params.pageSize) || 5, 1);
    const result = await baseApi.list({ ...params, page: 1, pageSize: 100 });
    let rows = filterVisibleBusinessStores(result.data || result.items || []);
    const keyword = String(params.keyword || '').trim().toLowerCase();
    const platform = String(params.platform || '').trim().toLowerCase();
    const status = String(params.status || '').trim();
    if (keyword) {
      rows = rows.filter((item) => `${item.name || ''} ${item.manager || ''} ${item.platform || ''}`.toLowerCase().includes(keyword));
    }
    if (platform) {
      rows = rows.filter((item) => String(item.platform || '').trim().toLowerCase() === platform);
    }
    if (status) {
      rows = rows.filter((item) => String(item.status || '').trim() === status);
    }
    const total = rows.length;
    const start = (page - 1) * pageSize;
    const pageRows = rows.slice(start, start + pageSize);
    return {
      ...result,
      data: pageRows,
      items: pageRows,
      total,
      page,
      pageSize,
    };
  },
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
      description="查看真实业务店铺、平台归属、负责人和运营状态。测试店铺默认隐藏在普通运营页面之外。"
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
        region: '韩国',
        language: 'ko-KR',
        status: '正常运营',
        remark: '',
      }}
      canCreate
      canEdit
      canDelete={!isBackendSource}
      onSaved={(store) => refreshStores({ preferredStoreId: selectedStoreId || normalizeStoreDisplay(store)?.id })}
    />
  );
}
