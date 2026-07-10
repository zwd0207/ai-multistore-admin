import { useEffect, useMemo, useRef, useState } from 'react';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';

const STAGES = [
  ['prepare', '待生成发货批次'],
  ['warehouse', '已发仓库，等待回传'],
  ['review', '仓库表导入与异常校验'],
  ['confirm', '待确认平台回填'],
  ['result', '已完成与失败'],
];

const REMOVE_REASONS = ['订单已取消', '客户修改订单', '商品缺货', '收件信息需要修改', '其他原因'];

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

function parseReturnSheet(content, rows) {
  const lines = content.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const values = lines.map((line) => line.split(/[,，\t]/).map((part) => part.trim()));
  const start = values[0]?.some((cell) => /订单|运单|快递/.test(cell)) ? 1 : 0;
  return values.slice(start).map((cells, index) => {
    const [productOrderNo, company, trackingNo, quantity] = cells;
    const row = rows.find((item) => item.productOrderNo === productOrderNo || item.orderNo === productOrderNo);
    const problems = [];
    if (!row) problems.push('找不到对应商品订单');
    if (!company) problems.push('缺少快递公司');
    if (!trackingNo) problems.push('缺少运单号');
    if (quantity && row && Number(quantity) !== row.quantity) problems.push('发货数量与订单不一致');
    const duplicate = trackingNo && values.slice(start).filter((other) => other[2] === trackingNo).length > 1;
    if (duplicate) problems.push('运单号重复');
    return {
      id: `${productOrderNo || index}-${index}`,
      rowId: row?.id,
      productOrderNo: productOrderNo || '未填写',
      productName: row?.productName || '-',
      company: company || '-',
      trackingNo: trackingNo || '-',
      quantity: quantity || String(row?.quantity || ''),
      result: problems.length ? (problems.some((item) => item === '找不到对应商品订单' || item.startsWith('缺少')) ? '无法处理' : '需要人工确认') : '可以正常处理',
      reason: problems.join('；'),
    };
  });
}

function downloadCsv(batch) {
  const header = ['商品订单号', '订单号', '商品', '规格', '数量', '仓库货号', '收件人', '联系电话', '收件地址', '快递公司', '运单号'];
  const rows = batch.rows.map((row) => [row.productOrderNo, row.orderNo, row.productName, row.optionName, row.quantity, row.inventoryCode, row.receiver, row.phone, row.address, '', '']);
  const blob = new Blob([[header, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n')], { type: 'text/csv;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${batch.code}-仓库发货表.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

export default function ShippingAssistant() {
  const { stores, selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const fileInput = useRef(null);
  const [query, setQuery] = useState({ keyword: '', platform: '', storeId: '' });
  const [draft, setDraft] = useState(query);
  const [orders, setOrders] = useState([]);
  const [selected, setSelected] = useState([]);
  const [batches, setBatches] = useState([]);
  const [activeStage, setActiveStage] = useState('prepare');
  const [activeBatchId, setActiveBatchId] = useState('');
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [downloadConfirm, setDownloadConfirm] = useState(false);
  const [removeRow, setRemoveRow] = useState(null);
  const [removeReason, setRemoveReason] = useState('');
  const [warehouseStopped, setWarehouseStopped] = useState(false);
  const [writebackConfirm, setWritebackConfirm] = useState(false);
  const [approvalExpired, setApprovalExpired] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (storeLoading) return;
      setLoading(true); setError('');
      try {
        const params = { page: 1, pageSize: 200 };
        if (isBackendSource && (query.storeId || selectedStoreId)) params.storeId = query.storeId || selectedStoreId;
        const result = await dataProvider.getOrders(params);
        const next = (result.data || result.items || []).filter(isPending).map(normalizeOrder).filter((row) => {
          const haystack = [row.orderNo, row.productOrderNo, row.productName, row.optionName, row.store].join(' ').toLowerCase();
          return (!query.keyword || haystack.includes(query.keyword.toLowerCase()))
            && (!query.platform || same(row.platform, query.platform))
            && (!query.storeId || String(row.storeId) === String(query.storeId));
        });
        if (!cancelled) setOrders(next);
      } catch (requestError) { if (!cancelled) setError(requestError.message || '待发货订单加载失败，请稍后重试。'); }
      finally { if (!cancelled) setLoading(false); }
    }
    load(); return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading]);

  const assigned = useMemo(() => new Set(batches.flatMap((batch) => batch.rows.filter((row) => !row.removed).map((row) => row.id))), [batches]);
  const pendingRows = orders.filter((row) => !assigned.has(row.id));
  const activeBatch = batches.find((batch) => String(batch.id) === String(activeBatchId)) || batches[0] || null;
  const stageBatches = useMemo(() => ({
    prepare: pendingRows,
    warehouse: batches.filter((batch) => batch.sent && !batch.imported && !batch.completed),
    review: batches.filter((batch) => batch.imported && !batch.confirmed && !batch.completed),
    confirm: batches.filter((batch) => batch.confirmed && !batch.completed),
    result: batches.filter((batch) => batch.completed || batch.failed),
  }), [batches, pendingRows]);

  const createBatch = () => {
    const rows = pendingRows.filter((row) => selected.includes(row.id));
    if (!rows.length) return setNotice('请先勾选要发给仓库的商品订单。');
    if (new Set(rows.map((row) => `${row.storeId}|${row.platform}`)).size > 1) return setNotice('一个发货批次只能包含同一店铺、同一平台的订单，请重新选择。');
    const batch = { id: Date.now(), code: `SHIP-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${String(batches.length + 1).padStart(2, '0')}`, store: rows[0].store, storeId: rows[0].storeId, platform: rows[0].platform, rows, sent: false, imported: false, confirmed: false, completed: false, failed: false, imports: [] };
    setBatches((current) => [batch, ...current]); setActiveBatchId(batch.id); setSelected([]); setActiveStage('warehouse'); setNotice(`已创建 ${batch.code}，请确认影响范围后下载仓库发货表。`);
  };

  const changeBatch = (update) => {
    if (!activeBatch) return;
    setBatches((current) => current.map((batch) => batch.id === activeBatch.id ? { ...batch, ...update } : batch));
    setWritebackConfirm(false); setApprovalExpired(true);
  };

  const onFile = (event) => {
    const file = event.target.files?.[0];
    if (!file || !activeBatch) return;
    const reader = new FileReader();
    reader.onload = () => {
      const imports = parseReturnSheet(String(reader.result || ''), activeBatch.rows.filter((row) => !row.removed));
      changeBatch({ imported: true, imports }); setActiveStage('review'); setNotice(`已读取 ${file.name}，请先处理异常行。`);
    };
    reader.readAsText(file, 'utf-8');
  };

  const confirmImport = () => {
    if (!activeBatch) return;
    const blocked = activeBatch.imports.filter((row) => row.result === '无法处理');
    if (blocked.length) return setNotice('仍有无法处理的记录，请修正仓库回传表后重新上传。');
    changeBatch({ confirmed: true }); setApprovalExpired(false); setActiveStage('confirm'); setNotice('物流信息已确认，请逐条核对后再确认提交。');
  };

  const submitWriteback = () => {
    if (!activeBatch) return;
    if (approvalExpired || !writebackConfirm) return setNotice('物流信息已变化或尚未确认，请重新核对并勾选确认后再提交。');
    changeBatch({ completed: true }); setApprovalExpired(false); setActiveStage('result'); setNotice('发货信息已完成确认，已从待办中移除。平台提交由受控流程另行执行。');
  };

  const removeFromBatch = () => {
    if (!activeBatch || !removeRow || !removeReason) return setNotice('移出前必须选择原因。');
    if (activeBatch.sent && !warehouseStopped) return setNotice('该批次已发给仓库，请先确认仓库已经停止发货。');
    changeBatch({ rows: activeBatch.rows.map((row) => row.id === removeRow.id ? { ...row, removed: true, removeReason } : row) });
    setRemoveRow(null); setRemoveReason(''); setWarehouseStopped(false); setNotice('该商品订单已移出发货批次。');
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
        <div className="card-title"><div><h2>{activeBatch.code}</h2><p>{activeBatch.store} · {activeBatch.platform} · {activeBatch.rows.filter((row) => !row.removed).length} 个商品订单 · {activeBatch.rows.filter((row) => !row.removed).reduce((sum, row) => sum + row.quantity, 0)} 件商品</p></div><select value={activeBatch.id} onChange={(event) => setActiveBatchId(event.target.value)}>{batches.map((batch) => <option key={batch.id} value={batch.id}>{batch.code} · {batch.store}</option>)}</select></div>
        {activeStage === 'warehouse' ? <><p>下载前请确认：本次会导出 {activeBatch.rows.filter((row) => !row.removed).length} 个商品订单的完整收件信息，仅供仓库发货使用。</p><label className="checkbox-line"><input type="checkbox" checked={downloadConfirm} onChange={(event) => setDownloadConfirm(event.target.checked)} /><span>我已核对店铺、订单数量和收件信息范围。</span></label><button className="button primary" type="button" disabled={!downloadConfirm} onClick={() => { downloadCsv(activeBatch); changeBatch({ sent: true }); setApprovalExpired(false); setNotice('仓库发货表已下载。发送给仓库后，请等待回传表。'); }}>下载仓库发货表</button><div className="modal-actions-inline"><input ref={fileInput} type="file" accept=".csv,.txt" onChange={onFile} /><button className="button ghost" type="button" onClick={() => fileInput.current?.click()}>上传仓库回传表</button></div></> : null}
        {activeStage === 'review' ? <><div className="summary-grid"><SummaryCard title="可以正常处理" value={activeBatch.imports.filter((row) => row.result === '可以正常处理').length} tone="success" /><SummaryCard title="需要人工确认" value={activeBatch.imports.filter((row) => row.result === '需要人工确认').length} tone="warning" /><SummaryCard title="无法处理" value={activeBatch.imports.filter((row) => row.result === '无法处理').length} tone="danger" /></div><table className="data-table"><thead><tr><th>商品订单号</th><th>商品</th><th>快递公司</th><th>运单号</th><th>结果</th><th>原因</th></tr></thead><tbody>{activeBatch.imports.map((row) => <tr key={row.id}><td>{row.productOrderNo}</td><td>{row.productName}</td><td>{row.company}</td><td>{row.trackingNo}</td><td><StatusBadge value={row.result} /></td><td>{row.reason || '无'}</td></tr>)}</tbody></table><button className="button primary" type="button" onClick={confirmImport}>确认可处理记录</button></> : null}
        {activeStage === 'confirm' ? <><p>请逐条核对以下商品订单的物流信息。数据变化后必须重新确认。</p><table className="data-table"><thead><tr><th>商品订单号</th><th>商品</th><th>快递公司</th><th>运单号</th><th>处理</th></tr></thead><tbody>{activeBatch.imports.filter((item) => item.result !== '无法处理').map((item) => <tr key={item.id}><td>{item.productOrderNo}</td><td>{item.productName}</td><td>{item.company}</td><td>{item.trackingNo}</td><td><button type="button" onClick={() => setRemoveRow(activeBatch.rows.find((row) => row.id === item.rowId))}>移出批次</button></td></tr>)}</tbody></table>{approvalExpired ? <div className="form-error">物流信息已变化，请重新核对后再确认。</div> : null}<label className="checkbox-line"><input type="checkbox" checked={writebackConfirm} onChange={(event) => setWritebackConfirm(event.target.checked)} /><span>我已确认店铺、订单、商品、快递公司和运单号无误。</span></label><button className="button primary" type="button" onClick={submitWriteback}>确认发货信息</button></> : null}
        {activeStage === 'result' ? <EmptyState title={activeBatch.failed ? '发货信息处理失败' : '发货批次已完成'} description={activeBatch.failed ? '请查看失败原因并修正后重新处理。' : '该批次已从当前待办中移除。'} /> : null}
      </>}
    </section>}
    {removeRow ? <section className="content-card"><h2>移出商品订单</h2><p>商品订单 {removeRow.productOrderNo} 将从 {activeBatch?.code} 移出。</p><select value={removeReason} onChange={(event) => setRemoveReason(event.target.value)}><option value="">选择移出原因</option>{REMOVE_REASONS.map((reason) => <option key={reason} value={reason}>{reason}</option>)}</select>{activeBatch?.sent ? <label className="checkbox-line"><input type="checkbox" checked={warehouseStopped} onChange={(event) => setWarehouseStopped(event.target.checked)} /><span>我已确认仓库已经停止发货。</span></label> : null}<div className="modal-actions-inline"><button type="button" className="button ghost" onClick={() => setRemoveRow(null)}>取消</button><button type="button" className="button danger" onClick={removeFromBatch}>确认移出</button></div></section> : null}
  </>;
}
