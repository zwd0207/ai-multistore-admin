import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import {
  adaptWarehouseBatch,
  adaptWarehouseTrackingDetail,
  adaptWarehouseWritebackCapability,
  REMOVE_REASON_CODES,
  warehouseRequest,
  writebackResultLabel,
} from '../features/shipping/warehouseBatch';

const STAGES = [
  ['prepare', '待生成发货批次'],
  ['warehouse', '已发仓库，等待回传'],
  ['review', '仓库表导入与异常校验'],
  ['confirm', '待确认平台回填'],
  ['result', '已完成与失败'],
];

const WORKBENCH_STAGE_MAP = {
  pending: 'prepare',
  waiting: 'warehouse',
  review: 'review',
  writeback: 'confirm',
  completed: 'result',
};

const REMOVE_REASONS = ['收件信息需要修改', '客户要求取消', '订单已取消', '商品货号有误', '商品缺货', '仓库异常'];

const text = (value, fallback = '-') => String(value ?? '').trim() || fallback;
const same = (left, right) => String(left ?? '').trim().toLowerCase() === String(right ?? '').trim().toLowerCase();

function writebackSafeMessage(errorOrResult, fallback = '平台回填未能继续，请重新核对后再试。') {
  const status = errorOrResult?.status;
  const reason = String(errorOrResult?.skip_reason || errorOrResult?.skipReason || '').toLowerCase();
  if (status === 401) return '登录已过期，请重新登录。';
  if (status === 403 || reason.includes('permission') || reason.includes('forbidden')) return '当前账号没有平台回填权限，操作已停止。';
  if (reason.includes('candidate') || reason.includes('changed') || reason.includes('stale')) return '订单或物流信息已变化，请重新核对。';
  if (reason.includes('capability') || reason.includes('disabled') || reason.includes('closed')) return '当前平台回填能力未开放，操作已停止。';
  return fallback;
}

function WritebackCapabilityReview({
  capability,
  loading,
  approval,
  approvalExpired,
  writebackConfirm,
  setWritebackConfirm,
  finalConfirm,
  setFinalConfirm,
  onRequestApproval,
  onExecute,
}) {
  const singleOrderText = capability?.maxRows === 1
    ? '仅支持 1 个商品订单'
    : capability?.maxRows ? `最多支持 ${capability.maxRows} 个商品订单` : '后端未提供限制信息';
  const canExecute = approval?.status === 'approval_granted'
    && capability?.allowedAction === 'execute'
    && Boolean(approval?.token);
  return (
    <div className="writeback-capability-review">
      {loading ? <div className="form-info">正在读取平台回填能力...</div> : null}
      {capability ? (
        <div className="writeback-capability-grid">
          <div><span>能力状态</span><strong><StatusBadge value={capability.status} /></strong></div>
          <div><span>订单限制</span><strong>{singleOrderText}</strong></div>
          <div><span>店铺</span><strong>{capability.storeName}</strong></div>
          <div><span>商品订单</span><strong>{capability.productOrderNo}</strong></div>
          <div><span>承运商</span><strong>{capability.carrier}</strong></div>
          <div><span>物流单号</span><strong>{capability.trackingNumberMasked}</strong></div>
          <div><span>平台最新状态</span><strong>{capability.platformLatestStatus}</strong></div>
          <div><span>审批有效期</span><strong>{approval?.expiresAt || capability.approvalExpiresAt}</strong></div>
          <div><span>平台检查时间</span><strong>{capability.platformCheckedAt}</strong></div>
        </div>
      ) : !loading ? <div className="form-error">平台回填能力未能确认，操作已停止。</div> : null}
      {approvalExpired ? <div className="form-error">信息已变化，请重新确认。</div> : null}
      {!approval ? (
        <>
          <label className="checkbox-line"><input type="checkbox" checked={writebackConfirm} onChange={(event) => setWritebackConfirm(event.target.checked)} /><span>我已完成唯一复核：店铺、商品订单、承运商、平台最新状态和物流信息均无误。</span></label>
          <button className="button primary" type="button" disabled={loading || !capability || capability.allowedAction !== 'approve'} onClick={onRequestApproval}>申请平台回填审批</button>
        </>
      ) : canExecute ? (
        <>
          <div className="form-info">审批已通过，请完成二次确认后执行；审批有效期：{approval.expiresAt || capability?.approvalExpiresAt || '-'}</div>
          <label className="checkbox-line"><input type="checkbox" checked={finalConfirm} onChange={(event) => setFinalConfirm(event.target.checked)} /><span>我已再次确认以上信息，并同意执行本次平台回填。</span></label>
          <button className="button primary" type="button" disabled={!finalConfirm} onClick={onExecute}>确认执行平台回填</button>
        </>
      ) : <div className="form-error">当前审批不能执行平台回填，请以最新能力状态为准。</div>}
    </div>
  );
}

function WritebackResultReview({ activeBatch, capability, trackingDetails, writebackResult, onReconcile, onReapprove }) {
  const resultStatus = writebackResult?.status || (activeBatch?.failed ? 'failed' : 'success');
  const unknown = resultStatus === 'unknown' || trackingDetails.some((item) => item.status === 'unknown');
  const failed = !unknown && ['failed', 'partial_success', 'writeback_failed'].includes(resultStatus);
  const safeReason = writebackResult?.safe_failure_reason || writebackResult?.safeFailureReason
    || writebackResult?.safe_reason || writebackResult?.safeReason
    || trackingDetails.find((item) => item.reason)?.reason || capability?.operatorMessage || '平台回填未完成。';
  return (
    <div className="writeback-result-review">
      <EmptyState
        title={unknown ? '平台结果待核对' : (failed ? '发货信息处理失败' : '发货批次已完成')}
        description={unknown ? '平台返回结果暂时无法确认，请进行结果核对。' : (failed ? `安全原因：${safeReason}` : '发货信息已完成处理。')}
      />
      {trackingDetails.length ? (
        <table className="data-table"><thead><tr><th>商品订单号</th><th>承运商</th><th>物流单号</th><th>平台结果</th></tr></thead><tbody>{trackingDetails.map((row) => <tr key={row.id}><td>{row.productOrderNo}</td><td>{row.carrier}</td><td>{row.trackingNumberTail}</td><td><StatusBadge value={writebackResultLabel(row.status)} /></td></tr>)}</tbody></table>
      ) : null}
      {unknown ? <button className="button primary" type="button" data-action="reconcile" onClick={onReconcile}>核对平台结果</button> : null}
      {failed && capability?.allowedAction === 'approve' ? <button className="button primary" type="button" onClick={onReapprove}>重新申请审批</button> : null}
    </div>
  );
}

function isPending(row = {}) {
  const value = [row.status, row.order_status, row.delivery_status, row.delivery_status_label_zh].join(' ').toLowerCase();
  return ['待发货', '新订单', '已付款', 'ready', 'payed', 'delivery_ready', 'place_product_order'].some((item) => value.includes(item.toLowerCase()));
}

function normalizeOrder(row = {}) {
  return {
    id: String(row.id || row.product_order_id || row.external_product_order_id || row.external_order_id),
    orderId: row.id,
    orderNo: text(row.external_order_id || row.orderNo || row.order_id),
    productOrderNo: text(row.external_product_order_id || row.product_order_id || row.productOrderNo || row.external_order_id),
    platform: text(row.platform || row.rawPlatform),
    store: text(row.store || row.store_name || row.storeName),
    storeId: row.store_id || row.storeId,
    productName: text(row.product_name || row.productName || row.product),
    optionName: text(row.option_name || row.optionName || row.option, '无规格'),
    quantity: Number(row.quantity || row.qty || 1),
    receiver: text(row.receiver_name || row.receiverName || row.buyer_name, '待确认'),
    phone: text(row.receiver_phone || row.receiverPhone, '待确认'),
    address: text(row.receiver_address || row.receiverAddress, '待确认'),
    inventoryCode: text(row.inventory_code || row.inventoryCode || row.sku, '待确认'),
    stock: Number(row.stock ?? row.stock_quantity ?? 0),
  };
}

export default function ShippingAssistant() {
  const [searchParams] = useSearchParams();
  const deepLinkStage = WORKBENCH_STAGE_MAP[searchParams.get('stage')] || 'prepare';
  const deepLinkBatchId = searchParams.get('batchId') || '';
  const deepLinkOrderId = searchParams.get('orderId') || '';
  const { stores, selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const fileInput = useRef(null);
  const [query, setQuery] = useState({ keyword: '', platform: '', storeId: '' });
  const [draft, setDraft] = useState(query);
  const [orders, setOrders] = useState([]);
  const [selected, setSelected] = useState([]);
  const [batches, setBatches] = useState([]);
  const [activeStage, setActiveStage] = useState(deepLinkStage);
  const [activeBatchId, setActiveBatchId] = useState(deepLinkBatchId);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [downloadConfirm, setDownloadConfirm] = useState(false);
  const [removeRow, setRemoveRow] = useState(null);
  const [removeReason, setRemoveReason] = useState('');
  const [warehouseStopped, setWarehouseStopped] = useState(false);
  const [writebackConfirm, setWritebackConfirm] = useState(false);
  const [approvalExpired, setApprovalExpired] = useState(false);
  const [trackingDetails, setTrackingDetails] = useState([]);
  const [writebackCapability, setWritebackCapability] = useState(null);
  const [writebackCapabilityLoading, setWritebackCapabilityLoading] = useState(false);
  const [writebackApproval, setWritebackApproval] = useState(null);
  const [finalWritebackConfirm, setFinalWritebackConfirm] = useState(false);
  const [writebackResult, setWritebackResult] = useState(null);
  const [resultBatch, setResultBatch] = useState(null);

  const refreshBatches = async ({ restoreUrgent = false } = {}) => {
    const storeId = query.storeId || selectedStoreId;
    if (!storeId) return [];
    const result = await dataProvider.getWarehouseShippingBatches({ storeId, platform: query.platform || 'naver' });
    const next = (result.items || []).map(adaptWarehouseBatch);
    setBatches(next);
    if (deepLinkBatchId) {
      setActiveStage(deepLinkStage);
      setActiveBatchId(deepLinkBatchId);
      return next;
    }
    if (restoreUrgent) {
      const urgent = ['review', 'confirm', 'warehouse'].map((stage) => next.find((batch) => batch.stage === stage)).find(Boolean);
      if (urgent) { setActiveStage(urgent.stage); setActiveBatchId(String(urgent.id)); }
      else { setActiveStage('prepare'); setActiveBatchId(''); }
    }
    return next;
  };

  const refreshTrackingDetails = async (batchId) => {
    if (!batchId) return;
    const result = await dataProvider.getWarehouseShippingTrackingDetails(batchId);
    if (result.status !== 'ready') throw new Error('tracking_details_unavailable');
    setTrackingDetails((result.items || result.rows || []).map(adaptWarehouseTrackingDetail));
  };

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (storeLoading) return;
      setLoading(true); setError('');
      try {
        const params = { page: 1, pageSize: 100 };
        if (isBackendSource && (query.storeId || selectedStoreId)) params.storeId = query.storeId || selectedStoreId;
        const result = await dataProvider.getOrders(params);
        const next = (result.data || result.items || []).filter(isPending).map(normalizeOrder).filter((row) => {
          const haystack = [row.orderNo, row.productOrderNo, row.productName, row.optionName, row.store].join(' ').toLowerCase();
          return (!query.keyword || haystack.includes(query.keyword.toLowerCase()))
            && (!query.platform || same(row.platform, query.platform))
            && (!query.storeId || String(row.storeId) === String(query.storeId));
        });
        if (!cancelled) {
          setOrders(next);
          if (deepLinkOrderId && next.some((item) => String(item.orderId ?? item.id) === deepLinkOrderId)) {
            setSelected([deepLinkOrderId]);
          }
          await refreshBatches({ restoreUrgent: !deepLinkBatchId });
        }
      } catch (requestError) { if (!cancelled) setError(requestError.message || '待发货订单加载失败，请稍后重试。'); }
      finally { if (!cancelled) setLoading(false); }
    }
    load(); return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading, deepLinkBatchId, deepLinkOrderId, deepLinkStage]);

  const assigned = useMemo(() => new Set(batches.flatMap((batch) => batch.rows.filter((row) => !row.removed).map((row) => String(row.orderId)))), [batches]);
  const pendingRows = orders.filter((row) => !assigned.has(row.id));
  const stageBatches = useMemo(() => ({
    prepare: pendingRows,
    warehouse: batches.filter((batch) => batch.stage === 'warehouse'),
    review: batches.filter((batch) => batch.stage === 'review'),
    confirm: batches.filter((batch) => batch.stage === 'confirm'),
    result: batches.filter((batch) => batch.stage === 'result'),
  }), [batches, pendingRows]);
  const currentStageBatches = activeStage === 'prepare' ? [] : stageBatches[activeStage];
  const activeBatch = currentStageBatches.find((batch) => String(batch.id) === String(activeBatchId)) || currentStageBatches[0] || null;
  const activeStoreName = stores.find((store) => String(store.id) === String(activeBatch?.storeId))?.name || `店铺 ${activeBatch?.storeId || '-'}`;

  useEffect(() => {
    const trackingBatch = activeStage === 'result' ? (activeBatch || resultBatch) : activeBatch;
    if (!trackingBatch || !['review', 'confirm', 'result'].includes(activeStage)) { setTrackingDetails([]); return; }
    refreshTrackingDetails(trackingBatch.id).catch(() => setTrackingDetails([]));
  }, [activeBatch?.id, activeStage, resultBatch?.id]);

  useEffect(() => {
    let cancelled = false;
    setWritebackApproval(null);
    setFinalWritebackConfirm(false);
    setApprovalExpired(false);
    if (activeStage !== 'result') setWritebackResult(null);
    if (!activeBatch || activeStage !== 'confirm') {
      setWritebackCapability(null);
      setWritebackCapabilityLoading(false);
      return () => { cancelled = true; };
    }
    setWritebackCapabilityLoading(false);
    setWritebackCapability(adaptWarehouseWritebackCapability(activeBatch.writebackCapability));
    return () => { cancelled = true; };
  }, [activeBatch?.id, activeStage]);

  const createBatch = async () => {
    const rows = pendingRows.filter((row) => selected.includes(row.id));
    if (!rows.length) return setNotice('请先勾选要发给仓库的商品订单。');
    if (new Set(rows.map((row) => `${row.storeId}|${row.platform}`)).size > 1) return setNotice('一个发货批次只能包含同一店铺、同一平台的订单，请重新选择。');
    const result = await dataProvider.createWarehouseShippingBatch(warehouseRequest.create({ storeId: rows[0].storeId, platform: rows[0].platform, orderIds: rows.map((row) => row.orderId) }));
    if (result.status !== 'created') return setNotice('无法创建批次，请检查订单状态后重新选择。');
    await refreshBatches(); setActiveBatchId(result.batch.id); setSelected([]); setActiveStage('warehouse'); setNotice(`已创建 ${result.batch.batch_no}，请确认影响范围后下载仓库发货表。`);
  };


  const onFile = (event) => {
    const file = event.target.files?.[0];
    if (!file || !activeBatch) return;
    if (!file.name.toLowerCase().endsWith('.xlsx')) { setNotice('请选择仓库回传的 XLSX 文件。'); return; }
    const reader = new FileReader();
    reader.onload = async () => {
      const content = String(reader.result || '').split(',')[1] || '';
      const result = await dataProvider.importWarehouseShippingTracking(activeBatch.id, warehouseRequest.importSheet({ fileName: file.name, fileContentBase64: content }));
      if (result.status !== 'warehouse_return_imported') { setNotice('信息已变化，请重新确认。'); return; }
      await refreshBatches(); setActiveStage('review'); setNotice(`已读取 ${file.name}，请先处理异常行。`);
    };
    reader.readAsDataURL(file);
  };

  const confirmImport = async () => {
    if (!activeBatch) return;
    const confirmIds = trackingDetails.filter((row) => row.status === 'needs_confirmation' && row.batchRowId).map((row) => row.batchRowId);
    const result = await dataProvider.confirmWarehouseShippingBatch(activeBatch.id, warehouseRequest.confirm(confirmIds));
    if (result.status !== 'ready_to_writeback') return setNotice('信息已变化，请重新确认。');
    await refreshBatches(); setApprovalExpired(false); setActiveStage('confirm'); setNotice('物流信息已确认，请逐条核对后再确认提交。');
  };

  const requestWritebackApproval = async () => {
    if (!activeBatch) return;
    if (approvalExpired || !writebackConfirm) return setNotice('请先完成唯一复核并勾选确认。');
    if (!writebackCapability || writebackCapability.allowedAction !== 'approve') return setNotice(writebackCapability?.operatorMessage || '当前平台回填能力未开放，操作已停止。');
    try {
      const approval = await dataProvider.requestWarehouseShippingApproval(activeBatch.id, 'writeback', { confirmation: true });
      const approvalToken = approval.approval_token || approval.token;
      const approvedCapability = adaptWarehouseWritebackCapability(approval.writeback_capability || approval.writebackCapability || writebackCapability);
      if (approvedCapability) setWritebackCapability(approvedCapability);
      if (approval.status !== 'approval_granted' || !approvalToken || approvedCapability?.allowedAction !== 'execute') {
        setApprovalExpired(true);
        return setNotice(approvedCapability?.operatorMessage || writebackSafeMessage(approval, '审批未能进入执行阶段，请重新核对。'));
      }
      setWritebackApproval({ token: approvalToken, status: approval.status, expiresAt: approval.expires_at || approval.expiresAt || approvedCapability?.approvalExpiresAt || '-' });
      setFinalWritebackConfirm(false);
      setNotice('审批已通过，请完成二次确认后执行。');
    } catch (error) {
      setApprovalExpired(true);
      setNotice(writebackSafeMessage(error));
    }
  };

  const submitWriteback = async () => {
    if (!activeBatch || !writebackApproval) return setNotice('请先获取有效审批。');
    if (!finalWritebackConfirm) return setNotice('请完成二次确认后再执行。');
    try {
      const result = await dataProvider.confirmWarehouseShippingWriteback(activeBatch.id, warehouseRequest.writeback(writebackApproval.token));
      setWritebackResult(result);
      setResultBatch(result.batch ? adaptWarehouseBatch(result.batch) : activeBatch);
      await refreshBatches();
      setWritebackApproval(null);
      setFinalWritebackConfirm(false);
      setWritebackConfirm(false);
      setApprovalExpired(false);
      setActiveStage('result');
      if (result.status === 'success') setNotice('发货信息已成功回填平台。');
      else if (result.status === 'unknown') setNotice('平台结果待核对，请使用核对结果操作。');
      else setNotice('发货信息回填失败，请查看安全原因并重新申请审批。');
    } catch (error) {
      setWritebackApproval(null);
      setFinalWritebackConfirm(false);
      setApprovalExpired(true);
      setNotice(writebackSafeMessage(error));
    }
  };

  const reconcileUnknown = async () => {
    const targetBatch = activeBatch || resultBatch;
    if (!targetBatch) return;
    try {
      const result = await dataProvider.reconcileWarehouseShippingWriteback(targetBatch.id);
      setWritebackResult(result);
      const nextCapability = adaptWarehouseWritebackCapability(result.writeback_capability || result.writebackCapability);
      if (nextCapability) setWritebackCapability(nextCapability);
      if (result.batch) setResultBatch(adaptWarehouseBatch(result.batch));
      const nextBatches = await refreshBatches();
      const refreshedBatch = nextBatches?.find((batch) => String(batch.id) === String(targetBatch.id));
      if (refreshedBatch) setResultBatch(refreshedBatch);
      await refreshTrackingDetails(targetBatch.id);
      setNotice(result.status === 'reconciled_success' ? '平台结果已核对完成。' : '已提交平台结果核对。');
    } catch (error) {
      setNotice(writebackSafeMessage(error, '平台结果核对暂时无法完成，请稍后再试。'));
    }
  };

  const removeFromBatch = async () => {
    if (!activeBatch || !removeRow || !removeReason) return setNotice('移出前必须选择原因。');
    if (activeBatch.requiresWarehouseStop && !warehouseStopped) return setNotice('该批次已发给仓库，请先确认仓库已经停止发货。');
    const result = await dataProvider.removeWarehouseShippingRow(activeBatch.id, removeRow.id, warehouseRequest.remove({ reasonCode: REMOVE_REASON_CODES[removeReason], warehouseStoppedShipping: warehouseStopped }));
    if (result.status !== 'removed') return setNotice('信息已变化，请重新确认。');
    await refreshBatches(); setRemoveRow(null); setRemoveReason(''); setWarehouseStopped(false); setNotice('该商品订单已移出发货批次。');
  };

  const summary = { pending: pendingRows.length, warehouse: stageBatches.warehouse.length, review: stageBatches.review.length, confirm: stageBatches.confirm.length, result: stageBatches.result.length };
  const rowsForStage = activeStage === 'prepare' ? pendingRows : activeBatch?.rows.filter((row) => !row.removed) || [];

  return <>
    <PageHeader title="仓库发货" description="先处理待发货订单，再按批次发送仓库、导入物流信息并确认发货结果。" />
    {notice ? <div className="form-info">{notice}</div> : null}
    {error || storeError ? <EmptyState title="仓库发货暂时无法加载" description={error || storeError} /> : null}
    <div className="summary-grid shipping-summary-grid">
      <SummaryCard title="待生成批次" value={summary.pending} note="先选择商品订单" tone="warning" />
      <SummaryCard title="等待仓库回传" value={summary.warehouse} note="已发给仓库" tone="info" />
      <SummaryCard title="等待检查" value={summary.review} note="仓库表已导入" tone="warning" />
      <SummaryCard title="待确认提交" value={summary.confirm} note="逐条核对物流信息" tone="warning" />
      <SummaryCard title="已完成或失败" value={summary.result} note="查看处理结果" tone="success" />
    </div>
    <div className="tab-row" aria-label="发货阶段">
      {STAGES.map(([key, label], index) => <button type="button" key={key} className={activeStage === key ? 'active' : ''} onClick={() => setActiveStage(key)}>{index + 1}. {label}</button>)}
    </div>

    {activeStage === 'prepare' ? <>
      <FilterPanel><SearchBar value={draft.keyword} onChange={(keyword) => setDraft({ ...draft, keyword })} onSearch={() => setQuery({ ...draft })} onReset={() => { const clean = { keyword: '', platform: '', storeId: '' }; setDraft(clean); setQuery(clean); }} placeholder="搜索订单号、商品或规格"><select value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })}><option value="">全部平台</option><option value="Naver">Naver</option><option value="Coupang">Coupang</option></select><select value={draft.storeId} onChange={(event) => setDraft({ ...draft, storeId: event.target.value })}><option value="">全部店铺</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></SearchBar></FilterPanel>
      <section className="content-card"><div className="card-title"><div><h2>待发给仓库</h2><p>已选择 {selected.length} 个商品订单。一个批次只能选择同一店铺、同一平台。</p></div><button className="button primary" type="button" onClick={createBatch}>创建发货批次</button></div>{!loading && !rowsForStage.length ? <EmptyState title="没有待处理的发货订单" description="新订单进入待发货后会显示在这里。" /> : <table className="data-table"><thead><tr><th><input aria-label="选择全部" type="checkbox" checked={rowsForStage.length > 0 && selected.length === rowsForStage.length} onChange={(event) => setSelected(event.target.checked ? rowsForStage.map((row) => row.id) : [])} /></th><th>商品订单号</th><th>店铺</th><th>商品和规格</th><th>数量</th><th>仓库货号</th><th>收件信息</th></tr></thead><tbody>{rowsForStage.map((row) => <tr key={row.id}><td><input aria-label={`选择 ${row.productOrderNo}`} type="checkbox" checked={selected.includes(row.id)} onChange={() => setSelected((current) => current.includes(row.id) ? current.filter((id) => id !== row.id) : [...current, row.id])} /></td><td><strong>{row.productOrderNo}</strong><small className="cell-subtitle">订单 {row.orderNo}</small></td><td>{row.store}</td><td>{row.productName}<small className="cell-subtitle">{row.optionName}</small></td><td>{row.quantity}</td><td>{row.inventoryCode}</td><td>{row.receiver}<small className="cell-subtitle">{row.phone} · {row.address}</small></td></tr>)}</tbody></table>}</section>
    </> : <section className="content-card">
      {!activeBatch ? <EmptyState title="当前阶段没有发货批次" description="请先在第一阶段创建发货批次。" /> : <>
        <div className="card-title"><div><h2>{activeBatch.code}</h2><p>{activeStoreName} · {activeBatch.platform} · {activeBatch.rows.filter((row) => !row.removed).length} 个商品订单 · {activeBatch.rows.filter((row) => !row.removed).reduce((sum, row) => sum + row.quantity, 0)} 件商品</p></div><select value={activeBatch.id} onChange={(event) => setActiveBatchId(event.target.value)}>{currentStageBatches.map((batch) => <option key={batch.id} value={batch.id}>{batch.code} · {stores.find((store) => String(store.id) === String(batch.storeId))?.name || `店铺 ${batch.storeId}`}</option>)}</select></div>
        {activeStage === 'warehouse' ? <><p>下载前请确认：本次会导出完整收件信息，仅供仓库发货使用。</p><label className="checkbox-line"><input type="checkbox" checked={downloadConfirm} onChange={(event) => setDownloadConfirm(event.target.checked)} /><span>我已核对店铺、订单数量和收件信息范围。</span></label><button className="button primary" type="button" disabled={!downloadConfirm} onClick={async () => { const approval = await dataProvider.requestWarehouseShippingApproval(activeBatch.id, 'manifest', { confirmation: true }); const approvalToken = approval.approval_token || approval.token; if (approval.status !== 'approval_granted' || !approvalToken) return setNotice('信息已变化，请重新确认。'); const result = await dataProvider.downloadWarehouseShippingManifest(activeBatch.id, warehouseRequest.manifest(approvalToken)); if (result.status !== 'warehouse_manifest_ready') return setNotice('信息已变化，请重新确认。'); const link = document.createElement('a'); link.href = `data:${result.content_type};base64,${result.file_content_base64}`; link.download = result.file_name; link.click(); await refreshBatches(); setNotice('仓库发货表已下载。'); }}>下载仓库发货表</button><div className="modal-actions-inline"><input ref={fileInput} type="file" accept=".xlsx" onChange={onFile} /><button className="button ghost" type="button" onClick={() => fileInput.current?.click()}>上传仓库回传表</button></div></> : null}
        {activeStage === 'review' ? <><div className="summary-grid"><SummaryCard title="可以正常处理" value={activeBatch.counts.normal} tone="success" /><SummaryCard title="需要人工确认" value={activeBatch.counts.needs_confirmation} tone="warning" /><SummaryCard title="无法处理" value={activeBatch.counts.blocked} tone="danger" /></div><table className="data-table"><thead><tr><th>商品订单号</th><th>商品</th><th>快递公司</th><th>物流单号</th><th>结果</th><th>原因</th></tr></thead><tbody>{trackingDetails.map((row) => <tr key={row.id}><td>{row.productOrderNo}</td><td>{row.productName}</td><td>{row.carrier}</td><td>{row.trackingNumber}</td><td><StatusBadge value={row.status} /></td><td>{row.reason || '无'}</td></tr>)}</tbody></table><button className="button primary" type="button" onClick={confirmImport}>确认可处理记录</button></> : null}
        {activeStage === 'confirm' ? <><p>请逐条核对以下商品订单的物流信息。数据变化后必须重新确认。</p><table className="data-table"><thead><tr><th>商品订单号</th><th>商品</th><th>承运商</th><th>物流单号</th><th>处理</th></tr></thead><tbody>{trackingDetails.filter((item) => ['ready_for_writeback', 'platform_failed'].includes(item.status)).map((item) => { const batchRow = activeBatch.rows.find((row) => String(row.id) === String(item.batchRowId)); return <tr key={item.id}><td>{item.productOrderNo}</td><td>{item.productName}</td><td>{item.carrier}</td><td>{item.trackingNumberTail}</td><td>{batchRow && !batchRow.removed ? <button type="button" onClick={() => setRemoveRow(batchRow)}>移出批次</button> : '-'}</td></tr>; })}</tbody></table><WritebackCapabilityReview capability={writebackCapability} loading={writebackCapabilityLoading} approval={writebackApproval} approvalExpired={approvalExpired} writebackConfirm={writebackConfirm} setWritebackConfirm={setWritebackConfirm} finalConfirm={finalWritebackConfirm} setFinalConfirm={setFinalWritebackConfirm} onRequestApproval={requestWritebackApproval} onExecute={submitWriteback} /></> : null}
        {activeStage === 'result' ? <WritebackResultReview activeBatch={activeBatch || resultBatch} capability={(activeBatch || resultBatch)?.writebackCapability} trackingDetails={trackingDetails} writebackResult={writebackResult} onReconcile={reconcileUnknown} onReapprove={() => { setActiveStage('confirm'); setResultBatch(null); setWritebackResult(null); setWritebackConfirm(false); }} /> : null}
      </>}
    </section>}
    {removeRow ? <section className="content-card"><h2>移出商品订单</h2><p>商品订单 {removeRow.productOrderNo} 将从 {activeBatch?.code} 移出。</p><select value={removeReason} onChange={(event) => setRemoveReason(event.target.value)}><option value="">选择移出原因</option>{REMOVE_REASONS.map((reason) => <option key={reason} value={reason}>{reason}</option>)}</select>{activeBatch?.requiresWarehouseStop ? <label className="checkbox-line"><input type="checkbox" checked={warehouseStopped} onChange={(event) => setWarehouseStopped(event.target.checked)} /><span>我已确认仓库已经停止发货。</span></label> : null}<div className="modal-actions-inline"><button type="button" className="button ghost" onClick={() => setRemoveRow(null)}>取消</button><button type="button" className="button danger" onClick={removeFromBatch}>确认移出</button></div></section> : null}
  </>;
}
