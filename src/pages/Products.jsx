import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import mockApi from '../services/mockApi';

const api = { list: mockApi.getProducts, create: mockApi.createProduct, update: mockApi.updateProduct, remove: mockApi.deleteProduct };
const platformOptions = ['Naver', 'Coupang', 'Gmarket', '11街', '옥션'];
const statusOptions = ['판매중', '销售中', '심사중', '판매중지', '草稿'];
const columns = [
  { key: 'name', title: '商品名称', render: (value, row) => <div><strong>{value}</strong><small className="cell-subtitle">{row.sku}</small></div> },
  { key: 'store', title: '所属店铺' }, { key: 'platform', title: '平台' }, { key: 'price', title: '售价', render: (value) => `₩ ${Number(value).toLocaleString()}` },
  { key: 'stock', title: '库存' }, { key: 'status', title: '销售状态', render: (value) => <StatusBadge value={value} /> }, { key: 'updatedAt', title: '最近同步' },
];
const fields = [
  { key: 'name', label: '商品名称', required: true }, { key: 'sku', label: 'SKU', required: true }, { key: 'store', label: '所属店铺', required: true },
  { key: 'platform', label: '平台', type: 'select', required: true, options: platformOptions }, { key: 'price', label: '售价（韩元）', type: 'number', required: true },
  { key: 'stock', label: '库存', type: 'number', required: true }, { key: 'status', label: '销售状态', type: 'select', required: true, options: statusOptions },
];
export default function Products() { return <ResourcePage title="商品管理" description="查看并维护跨平台商品、价格及库存信息" resourceName="商品" api={api} columns={columns} fields={fields} statuses={statusOptions} platforms={platformOptions} initialForm={{ name: '', sku: '', store: '', platform: '', price: 0, stock: 0, status: '' }} />; }
