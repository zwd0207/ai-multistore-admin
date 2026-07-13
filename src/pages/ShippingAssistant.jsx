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
import { adaptWarehouseBatch, adaptWarehouseTrackingDetail, REMOVE_REASON_CODES, warehouseRequest } from '../features/shipping/warehouseBatch';

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
  const [platformWriteEnabled, setPlatformWriteEnabled] = useState(!isBackendSource);

  useEffect(() => {
    if (!isBackendSource) return undefined;
    let cancelled = false;
    dataProvider.healthCheck()
      .then((health) => {
        if (cancelled) return;
        const approved = health.approved_platform_write_operations || health.approvedPlatformWriteOperations || [];
        setPlatformWriteEnabled(
          health.controlled_platform_writes_enabled === true
          && approved.includes('naver_shipment_dispatch'),
        );
      })
      .catch(() => { if (!cancelled) setPlatformWriteEnabled(false); });
    return () => { cancelled = true; };
  }, []);

  const refreshBatches = async ({ restoreUrgent = false } = {}) => {
    const storeId = query.storeId || selectedStoreId;
    if (!storeId) return;
    const result = await dataProvider.getWarehouseShippingBatches({ storeId, platform: query.platform || 'naver' });
    const next = (result.items || []).map(adaptWarehouseBatch);
    setBatches(next);
    if (deepLinkBatchId) {
      setActiveStage(deepLinkStage);
      setActiveBatchId(deepLinkBatchId);
      return;
    }
    if (restoreUrgent) {
      const urgent = ['review', 'confirm', 'warehouse'].map((stage) => next.find((batch) => batch.stage === stage)).find(Boolean);
      if (urgent) { setActiveStage(urgent.stage); setActiveBatchId(String(urgent.id)); }
      else { setActiveStage('prepare'); setActiveBatchId(''); }
    }
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
    if (!activeBatch || !['review', 'confirm'].includes(activeStage)) { setTrackingDetails([]); return; }
    refreshTrackingDetails(activeBatch.id).catch(() => setTrackingDetails([]));
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

  const submitWriteback = async () => {
    if (!activeBatch) return;
    if (approvalExpired || !writebackConfirm) return setNotice('物流信息已变化或尚未确认，请重新核对并勾选确认后再提交。');
    const approval = await dataProvider.requestWarehouseShippingApproval(activeBatch.id, 'writeback', { confirmation: true });
    const approvalToken = approval.approval_token || approval.token;
    if (approval.status !== 'approval_granted' || !approvalToken) { setApprovalExpired(true); return setNotice('信息已变化，请重新核对后再次确认。'); }
    const result = await dataProvider.confirmWarehouseShippingWriteback(activeBatch.id, warehouseRequest.writeback(approvalToken));
    if (!['success', 'partial_success'].includes(result.status)) { setApprovalExpired(true); return setNotice('发货信息未能提交，请重新核对或联系管理员。'); }
    await refreshBatches(); setWritebackConfirm(false); setApprovalExpired(false); setActiveStage('result'); setNotice(result.status === 'success' ? '发货信息已成功回填平台。' : '部分订单回填失败，请查看结果并重新处理。');
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
        {activeStage === 'confirm' ? <><p>请逐条核对以下商品订单的物流信息。数据变化后必须重新确认。</p><table className="data-table"><thead><tr><th>商品订单号</th><th>商品</th><th>快递公司</th><th>物流单号</th><th>处理</th></tr></thead><tbody>{trackingDetails.filter((item) => ['ready_for_writeback', 'platform_failed'].includes(item.status)).map((item) => { const batchRow = activeBatch.rows.find((row) => String(row.id) === String(item.batchRowId)); return <tr key={item.id}><td>{item.productOrderNo}</td><td>{item.productName}</td><td>{item.carrier}</td><td>{item.trackingNumber}</td><td>{batchRow && !batchRow.removed ? <button type="button" onClick={() => setRemoveRow(batchRow)}>移出批次</button> : '-'}</td></tr>; })}</tbody></table>{approvalExpired ? <div className="form-error">信息已变化，请重新确认。</div> : null}{platformWriteEnabled ? <><label className="checkbox-line"><input type="checkbox" checked={writebackConfirm} onChange={(event) => setWritebackConfirm(event.target.checked)} /><span>我已确认店铺、订单、商品、快递公司和物流单号无误，并同意提交到当前平台。</span></label><button className="button primary" type="button" onClick={submitWriteback}>确认并回填平台</button></> : <div className="form-info">模拟试运营已完成到人工确认阶段。真实平台回填保持关闭，本批次不会提交到 Naver。</div>}</> : null}
        {activeStage === 'result' ? <EmptyState title={activeBatch.failed ? '发货信息处理失败' : '发货批次已完成'} description={activeBatch.failed ? '请查看失败原因并修正后重新处理。' : '该批次已从当前待办中移除。'} /> : null}
      </>}
    </section>}
    {removeRow ? <section className="content-card"><h2>移出商品订单</h2><p>商品订单 {removeRow.productOrderNo} 将从 {activeBatch?.code} 移出。</p><select value={removeReason} onChange={(event) => setRemoveReason(event.target.value)}><option value="">选择移出原因</option>{REMOVE_REASONS.map((reason) => <option key={reason} value={reason}>{reason}</option>)}</select>{activeBatch?.requiresWarehouseStop ? <label className="checkbox-line"><input type="checkbox" checked={warehouseStopped} onChange={(event) => setWarehouseStopped(event.target.checked)} /><span>我已确认仓库已经停止发货。</span></label> : null}<div className="modal-actions-inline"><button type="button" className="button ghost" onClick={() => setRemoveRow(null)}>取消</button><button type="button" className="button danger" onClick={removeFromBatch}>确认移出</button></div></section> : null}
  </>;
}
