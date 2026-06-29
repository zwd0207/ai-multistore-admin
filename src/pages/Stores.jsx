import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import mockApi from '../services/mockApi';

const api = { list: mockApi.getStores, create: mockApi.createStore, update: mockApi.updateStore, remove: mockApi.deleteStore };
const platformOptions = ['Naver', 'Coupang', 'Gmarket', '11街', '옥션'];
const statusOptions = ['正常运营', '정상 운영', '审核中', '심사중', '申诉中', '판매중지'];
const columns = [
  { key: 'name', title: '店铺名称', render: (value) => <strong>{value}</strong> }, { key: 'platform', title: '平台' },
  { key: 'manager', title: '负责人' }, { key: 'region', title: '地区' }, { key: 'products', title: '商品数' },
  { key: 'status', title: '运营状态', render: (value) => <StatusBadge value={value} /> }, { key: 'updatedAt', title: '最近更新' },
];
const fields = [
  { key: 'name', label: '店铺名称', required: true }, { key: 'platform', label: '平台', type: 'select', required: true, options: platformOptions },
  { key: 'manager', label: '负责人', required: true }, { key: 'region', label: '地区', required: true },
  { key: 'products', label: '商品数', type: 'number' }, { key: 'status', label: '运营状态', type: 'select', required: true, options: statusOptions },
];
export default function Stores() { return <ResourcePage title="店铺管理" description="统一管理多平台店铺及其运营状态" resourceName="店铺" api={api} columns={columns} fields={fields} statuses={statusOptions} platforms={platformOptions} initialForm={{ name: '', platform: '', manager: '', region: '', products: 0, status: '' }} />; }
