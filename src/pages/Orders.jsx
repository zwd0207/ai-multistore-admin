import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource, getDangerousActionState } from '../utils/coreErpContract';

const PAGE_SIZE = 20;

const statusTabs = [
  { key: '', label: '全部订单' },
  { key: 'new', label: '新订单' },
  { key: 'pending', label: '待发货' },
  { key: 'shipped', label: '已发货' },
  { key: 'cancel', label: '取消订单' },
  { key: 'return', label: '退货订单' },
  { key: 'exchange', label: '换货订单' },
  { key: 'abnormal', label: '异常订单' },
];

function textOf(...values) {
  return values.filter(Boolean).map((value) => String(value)).join(' ');
}

function normalizedOrder(row = {}) {
  const statusText = textOf(row.status, row.order_status, row.delivery_status_label_zh, row.claim_status_label_zh);
  const product = row.product || row.productName || row.product_name || row.name || '-';
  const option = row.option || row.optionName || row.option_name || row.spec || '-';
  const shippingStatus = row.deliveryStatusLabelZh || row.delivery_status_label_zh || row.shippingStatus || row.delivery_status || '-';
  return {
    ...row,
    orderNo: row.orderNo || row.external_order_id || row.order_id || row.id,
    platform: row.platform || row.rawPlatform || '-',
    store: row.store || row.storeName || row.store_name || '-',
    product,
    option,
    quantity: row.quantity || row.qty || 1,
    amount: row.amount ?? row.order_amount ?? row.totalAmount ?? 0,
    statusText: statusText || '-',
    shippingStatus,
    logisticsCompany: row.logisticsCompany || row.deliveryCompany || row.delivery_company || row.courier || '-',
    trackingNo: row.trackingNo || row.trackingNumber || row.tracking_number || row.invoiceNo || '-',
    createdAt: row.createdAt || row.ordered_at || row.orderDate || row.paid_at || '',
    receiverName: row.receiverName || row.receiver_name || row.customer || row.buyer_name || '',
    receiverPhone: row.receiverPhone || row.receiver_phone || row.phone || row.buyer_phone || '',
    receiverAddress: row.receiverAddress || row.receiver_address || row.address || '',
    sourceInfo: classifyCoreDataSource(row),
  };
}

function matchesStatus(row, statusKey) {
  if (!statusKey) return true;
  const text = textOf(row.statusText, row.status, row.order_status, row.delivery_status, row.claim_status).toLowerCase();
  const checks = {
    new: ['新订单', '已付款', 'payed', 'place_product_order'],
    pending: ['待发货', 'ready', 'delivery_ready'],
    shipped: ['已发货', '配送中', 'delivering', 'dispatched', 'shipped'],
    cancel: ['取消', 'cancel'],
    return: ['退货', 'return'],
    exchange: ['换货', 'exchange'],
    abnormal: ['异常', '取消', '退款', '退货', '换货', 'claim', 'refund', 'return', 'exchange', 'cancel'],
  };
  return (checks[statusKey] || []).some((flag) => text.includes(flag.toLowerCase()));
}

function copyReceiverText(order = {}) {
  return [
    `收件人：${order.receiverName || '-'}`,
    `电话：${order.receiverPhone || '-'}`,
    `地址：${order.receiverAddress || '-'}`,
  ].join('\n');
}

async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  return false;
}

const columns = [
  { key: 'orderNo', title: '订单号', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'product', title: '商品名' },
  { key: 'option', title: '规格' },
  { key: 'quantity', title: '数量' },
  { key: 'amount', title: '订单金额', render: (value, row) => `${Number(value || 0).toLocaleString()} ${row.currency || 'KRW'}` },
  { key: 'statusText', title: '订单状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '下单时间' },
  { key: 'shippingStatus', title: '发货状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'logisticsCompany', title: '快递公司' },
  { key: 'trackingNo', title: '运单号' },
];

export default function Orders() {
  const {
    stores,
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [query, setQuery] = useState({
    keyword: '',
    platform: '',
    storeId: '',
    status: '',
  });
  const [draft, setDraft] = useState(query);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeOrder, setActiveOrder] = useState(null);
  const [noteModal, setNoteModal] = useState({ open: false, order: null });
  const [notes, setNotes] = useState({});
  const [copyMessage, setCopyMessage] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (storeLoading) return;
      setLoading(true);
      setError('');
      try {
        const params = {
          page: 1,
          pageSize: 100,
          keyword: query.keyword,
          platform: query.platform,
        };
        if (isBackendSource && (query.storeId || selectedStoreId)) params.storeId = query.storeId || selectedStoreId;
        const result = await dataProvider.getOrders(params);
        let nextRows = (result.data || result.items || []).map(normalizedOrder);
        if (!isBackendSource && query.storeId) {
          const store = stores.find((item) => String(item.id) === String(query.storeId));
          nextRows = nextRows.filter((item) => item.store === store?.name || String(item.storeId || item.store_id) === String(query.storeId));
        }
        nextRows = nextRows.filter((item) => matchesStatus(item, query.status));
        if (!cancelled) setRows(nextRows);
      } catch (loadError) {
        if (!cancelled) {
          setRows([]);
          setError(loadError.message || '订单数据加载失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading, stores]);

  const summary = useMemo(() => ({
    total: rows.length,
    pending: rows.filter((item) => matchesStatus(item, 'pending')).length,
    shipped: rows.filter((item) => matchesStatus(item, 'shipped')).length,
    abnormal: rows.filter((item) => matchesStatus(item, 'abnormal')).length,
  }), [rows]);

  const search = () => setQuery({ ...draft });
  const reset = () => {
    const next = { keyword: '', platform: '', storeId: '', status: '' };
    setDraft(next);
    setQuery(next);
  };

  const openNote = (order) => {
    setNoteModal({ open: true, order });
  };

  const saveNote = () => {
    const orderNo = noteModal.order?.orderNo;
    if (orderNo) setNotes((current) => ({ ...current, [orderNo]: noteModal.note || '' }));
    setNoteModal({ open: false, order: null, note: '' });
  };

  const handleCopy = async (order) => {
    const ok = await copyToClipboard(copyReceiverText(order));
    setCopyMessage(ok ? `已复制 ${order.orderNo} 的收件信息` : '当前浏览器不支持自动复制，请在详情中手动复制。');
    setTimeout(() => setCopyMessage(''), 2400);
  };

  const dangerousState = getDangerousActionState('shipment_writeback');

  return (
    <>
      <PageHeader
        title="订单管理"
        description="搜索、筛选和查看订单详情。本阶段不执行平台取消、退货、换货或发货回填。"
        actions={(
          <>
            <Link className="button ghost" to="/shipping">跳转发货辅助</Link>
            <span className="period-chip">{dangerousState.label}</span>
          </>
        )}
      />

      <div className="summary-grid">
        <SummaryCard title="订单列表" value={summary.total} note="当前筛选结果" tone="info" />
        <SummaryCard title="待发货" value={summary.pending} note="进入发货辅助人工处理" tone={summary.pending ? 'warning' : 'success'} />
        <SummaryCard title="已发货" value={summary.shipped} note="来自本地保存记录" tone="success" />
        <SummaryCard title="异常订单" value={summary.abnormal} note="取消/退货/换货只做提醒" tone={summary.abnormal ? 'danger' : 'success'} />
      </div>

      <FilterPanel>
        <SearchBar
          value={draft.keyword}
          onChange={(keyword) => setDraft({ ...draft, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索订单号、商品、收件人、运单号"
        >
          <select value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })}>
            <option value="">全部平台</option>
            <option value="Naver">Naver</option>
            <option value="Coupang">Coupang</option>
            <option value="Gmarket">Gmarket/ESM</option>
          </select>
          <select value={draft.storeId} onChange={(event) => setDraft({ ...draft, storeId: event.target.value })}>
            <option value="">全部店铺</option>
            {stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}
          </select>
          <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
            {statusTabs.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {storeError ? <EmptyState title="店铺信息不可用" description={storeError} /> : null}
        {error ? <EmptyState title="订单数据加载失败" description={error} /> : null}
        {copyMessage ? <div className="form-info">{copyMessage}</div> : null}
        <DataTable
          columns={columns}
          rows={rows.slice(0, PAGE_SIZE)}
          loading={loading || storeLoading}
          rowKey="id"
          renderActions={(row) => (
            <>
              <button type="button" onClick={() => setActiveOrder(row)}>详情</button>
              <button type="button" onClick={() => handleCopy(row)}>复制收件信息</button>
              <Link to="/shipping">发货辅助</Link>
              <button type="button" onClick={() => openNote(row)}>内部备注</button>
              <button type="button" disabled title="暂未开放">平台处理暂未开放</button>
            </>
          )}
        />
      </section>

      <DetailModal
        open={Boolean(activeOrder)}
        title={activeOrder ? `订单详情 · ${activeOrder.orderNo}` : '订单详情'}
        onClose={() => setActiveOrder(null)}
        width="min(980px, 94vw)"
      >
        {activeOrder ? (
          <>
            <div className="detail-grid">
              {[
                ['平台', activeOrder.platform],
                ['店铺', activeOrder.store],
                ['商品', activeOrder.product],
                ['规格', activeOrder.option],
                ['数量', activeOrder.quantity],
                ['订单金额', `${Number(activeOrder.amount || 0).toLocaleString()} ${activeOrder.currency || 'KRW'}`],
                ['订单状态', <StatusBadge value={activeOrder.statusText} />],
                ['发货状态', <StatusBadge value={activeOrder.shippingStatus} />],
                ['快递公司', activeOrder.logisticsCompany],
                ['运单号', activeOrder.trackingNo],
                ['数据来源', activeOrder.sourceInfo.label],
                ['内部备注', notes[activeOrder.orderNo] || '暂无'],
              ].map(([label, value]) => (
                <div className="detail-item" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <section className="content-card">
              <h3>收件信息</h3>
              <p className="mock-sync-note">复制只发生在本地剪贴板，不会回写平台。</p>
              <pre className="readonly-code">{copyReceiverText(activeOrder)}</pre>
              <button className="button ghost" type="button" onClick={() => handleCopy(activeOrder)}>复制收件信息</button>
            </section>
            <section className="content-card">
              <h3>暂未开放操作</h3>
              <p>{dangerousState.note} 取消订单、退货订单、换货订单和发货回填需后续单独审批。</p>
            </section>
          </>
        ) : (
          <EmptyState title="暂无订单详情" description="请选择一条订单查看详情。" />
        )}
      </DetailModal>

      <Modal
        open={noteModal.open}
        title={noteModal.order ? `内部备注 · ${noteModal.order.orderNo}` : '内部备注'}
        onClose={() => setNoteModal({ open: false, order: null, note: '' })}
        onConfirm={saveNote}
        confirmText="保存本地备注"
      >
        <FormField label="备注内容">
          <input
            value={noteModal.note ?? notes[noteModal.order?.orderNo] ?? ''}
            onChange={(event) => setNoteModal({ ...noteModal, note: event.target.value })}
            placeholder="仅保存在系统本地，不回写平台"
          />
        </FormField>
        <p className="mock-sync-note">内部备注是本地辅助功能，不会同步到 Naver / Coupang / Gmarket。</p>
      </Modal>
    </>
  );
}
