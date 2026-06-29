import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';

const api = {
  list: dataProvider.getOrders,
  create: mockApi.createOrder,
  update: mockApi.updateOrder,
  remove: mockApi.deleteOrder,
};

const statusOptions = ['待发货', '배송중', '구매확정', '取消退款'];
const columns = [
  { key: 'orderNo', title: '订单编号', render: (value) => <strong>{value}</strong> },
  { key: 'product', title: '商品' },
  { key: 'store', title: '所属店铺' },
  { key: 'customer', title: '客户' },
  { key: 'phone', title: '联系电话' },
  { key: 'amount', title: '订单金额', render: (value, row) => `${Number(value || 0).toLocaleString()} ${row.currency || 'KRW'}` },
  { key: 'status', title: '订单状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '下单时间' },
];
const fields = [
  { key: 'orderNo', label: '订单编号', required: true },
  { key: 'product', label: '商品名称', required: true },
  { key: 'store', label: '所属店铺', required: true },
  { key: 'customer', label: '客户', required: true },
  { key: 'amount', label: '订单金额（韩元）', type: 'number', required: true },
  { key: 'status', label: '订单状态', type: 'select', required: true, options: statusOptions },
  { key: 'createdAt', label: '下单时间', required: true, placeholder: '2026-06-29 15:00' },
];

export default function Orders() {
  const { selectedStoreId } = useStoreContext();
  return (
    <ResourcePage
      title="订单管理"
      description="跟踪各店铺订单履约、配送与退款状态"
      resourceName="订单"
      api={api}
      columns={columns}
      fields={fields}
      statuses={statusOptions}
      initialForm={{ orderNo: '', product: '', store: '', customer: '', amount: 0, status: '', createdAt: '' }}
      readOnly={isBackendSource}
      extraParams={isBackendSource ? { storeId: selectedStoreId } : {}}
      reloadKey={selectedStoreId}
    />
  );
}
