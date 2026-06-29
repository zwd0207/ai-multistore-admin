import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import mockApi from '../services/mockApi';

const api = { list: mockApi.getOrders, create: mockApi.createOrder, update: mockApi.updateOrder, remove: mockApi.deleteOrder };
const columns = [
  { key: 'orderNo', title: '订单编号', render: (value) => <strong>{value}</strong> }, { key: 'product', title: '商品' }, { key: 'store', title: '所属店铺' },
  { key: 'customer', title: '客户' }, { key: 'amount', title: '订单金额', render: (value) => `₩ ${Number(value).toLocaleString()}` },
  { key: 'status', title: '订单状态', render: (value) => <StatusBadge value={value} /> }, { key: 'createdAt', title: '下单时间' },
];
const fields = [
  { key: 'orderNo', label: '订单编号', required: true }, { key: 'product', label: '商品名称', required: true }, { key: 'store', label: '所属店铺', required: true },
  { key: 'customer', label: '客户', required: true }, { key: 'amount', label: '订单金额（韩元）', type: 'number', required: true },
  { key: 'status', label: '订单状态', type: 'select', required: true, options: ['待发货', '배송중', '구매확정', '取消退款'] }, { key: 'createdAt', label: '下单时间', required: true, placeholder: '2026-06-29 15:00' },
];
export default function Orders() { return <ResourcePage title="订单管理" description="跟踪各店铺订单履约、配送与退款状态" resourceName="订单" api={api} columns={columns} fields={fields} statuses={['待发货', '배송중', '구매확정', '取消退款']} initialForm={{ orderNo: '', product: '', store: '', customer: '', amount: 0, status: '', createdAt: '' }} />; }
