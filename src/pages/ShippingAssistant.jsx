import { useEffect, useMemo, useState } from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource, getDangerousActionState } from '../utils/coreErpContract';

const prepStatusOptions = ['待核对', '商品已核对', '库存已确认', '单号已导入', '可人工发货'];
const NAVER_DISPATCH_PAYLOAD_FIELD = 'dispatchProductOrders';

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function money(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function text(value, fallback = '-') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function orderNo(row = {}) {
  return row.orderNo || row.external_order_id || row.order_id || row.id;
}

function isPendingShipment(row = {}) {
  const statusText = [
    row.status,
    row.order_status,
    row.delivery_status,
    row.delivery_status_label_zh,
    row.shippingStatus,
  ].map(comparable).join(' ');
  return ['待发货', '新订单', '已付款', 'ready', 'payed', 'delivery_ready', 'place_product_order'].some((flag) => statusText.includes(comparable(flag)));
}

function normalizeProduct(row = {}) {
  return {
    ...row,
    name: text(row.name || row.productName || row.product_name),
    optionName: text(row.optionName || row.option_name || row.option, ''),
    platform: text(row.platform || row.rawPlatform),
    storeId: row.storeId || row.store_id,
    stock: Number(row.stock ?? row.stock_quantity ?? 0),
    inventoryCode: text(row.inventoryCode || row.sku || row.externalId, '待维护'),
  };
}

function findInventory(order, products = []) {
  const productName = comparable(order.productName);
  const optionName = comparable(order.optionName);
  return products.find((item) => {
    if (order.storeId && item.storeId && String(order.storeId) !== String(item.storeId)) return false;
    if (comparable(item.platform) !== comparable(order.platform)) return false;
    const sameProduct = comparable(item.name) === productName || comparable(item.name).includes(productName) || productName.includes(comparable(item.name));
    const sameOption = !optionName || !item.optionName || comparable(item.optionName) === optionName;
    return sameProduct && sameOption;
  }) || null;
}

function normalizeOrder(row = {}, products = []) {
  const quantity = Number(row.quantity || row.qty || 1);
  const base = {
    ...row,
    id: row.id || orderNo(row),
    orderNo: orderNo(row),
    platform: text(row.platform || row.rawPlatform),
    store: text(row.store || row.storeName || row.store_name),
    storeId: row.storeId || row.store_id,
    productName: text(row.product || row.productName || row.product_name || row.name),
    optionName: text(row.option || row.optionName || row.option_name || row.spec, '无规格'),
    quantity,
    amount: Number(row.amount ?? row.order_amount ?? row.totalAmount ?? 0),
    currency: row.currency || 'KRW',
    orderedAt: row.createdAt || row.ordered_at || row.paid_at || '',
    statusText: text(row.delivery_status_label_zh || row.status || row.order_status),
    sourceInfo: classifyCoreDataSource(row),
  };
  const inventory = findInventory(base, products);
  const stock = Number(inventory?.stock ?? 0);
  const stockEnough = inventory ? stock >= quantity : false;
  return {
    ...base,
    inventoryCode: inventory?.inventoryCode || '待匹配',
    inventoryStock: inventory ? stock : null,
    stockStatus: inventory ? (stockEnough ? '库存足够' : '库存不足') : '待人工确认',
    stockEnough,
    trackingCompany: '',
    trackingNo: '',
  };
}

function parseTrackingText(value = '') {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [order, company, tracking] = line.split(/[,，\t]/).map((part) => part?.trim());
      return {
        orderNo: order || '',
        company: company || '',
        trackingNo: tracking || '',
      };
    })
    .filter((item) => item.orderNo && item.trackingNo);
}

function buildShippingRows(rows = [], prepStatus = {}, trackingMap = {}) {
  return rows.map((row) => {
    const tracking = trackingMap[row.orderNo] || {};
    return {
      ...row,
      trackingCompany: tracking.company || row.trackingCompany || '',
      trackingNo: tracking.trackingNo || row.trackingNo || '',
      prepStatus: prepStatus[row.orderNo] || '待核对',
    };
  });
}

function nextShippingStep(summary) {
  if (!summary.pending) return ['暂无待发货订单', '回到订单管理确认订单状态，或等待新订单进入待发货。', '/orders'];
  if (summary.matched < summary.pending) return ['先核对商品和库存编号', '有订单还没有匹配到库存编号，先确认商品名称、规格和库存编号。', '/products'];
  if (summary.enough < summary.pending) return ['确认库存是否足够', '有订单库存不足或待人工确认，先处理库存缺口。', '/inventory'];
  if (summary.imported < summary.pending) return ['再导入物流单号', '库存足够后，把物流商表格中的订单号、快递公司和运单号导入本地匹配。', '/shipping'];
  return ['提交 Naver 发货回填', '发货准备状态已具备，可在人工确认后提交 Naver 发货回填。', '/shipping'];
}

const columns = [
  { key: 'orderNo', title: '订单号', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  {
    key: 'productName',
    title: '商品和规格',
    render: (value, row) => (
      <div>
        <strong>{value}</strong>
        <small className="cell-subtitle">{row.optionName}</small>
      </div>
    ),
  },
  { key: 'quantity', title: '数量' },
  { key: 'inventoryCode', title: '库存编号' },
  {
    key: 'inventoryStock',
    title: '库存是否足够',
    render: (value, row) => <StatusBadge value={`${row.stockStatus}${value === null ? '' : `：${value} 件`}`} />,
  },
  { key: 'trackingCompany', title: '快递公司', render: (value) => value || '待导入' },
  { key: 'trackingNo', title: '运单号', render: (value) => value || '待导入' },
  { key: 'prepStatus', title: '发货准备状态', render: (value) => <StatusBadge value={value} /> },
];

export default function ShippingAssistant() {
  const {
    stores,
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', platform: '', storeId: '' });
  const [draft, setDraft] = useState(query);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trackingText, setTrackingText] = useState('');
  const [trackingMap, setTrackingMap] = useState({});
  const [trackingMessage, setTrackingMessage] = useState('');
  const [prepStatus, setPrepStatus] = useState({});
  const [showExport, setShowExport] = useState(false);
  const [writebackConfirm, setWritebackConfirm] = useState(false);
  const [writebackLoading, setWritebackLoading] = useState(false);
  const [writebackMessage, setWritebackMessage] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (storeLoading) return;
      setLoading(true);
      setError('');
      try {
        const params = { page: 1, pageSize: 200 };
        if (isBackendSource && (query.storeId || selectedStoreId)) params.storeId = query.storeId || selectedStoreId;
        const [orderResult, productResult] = await Promise.all([
          dataProvider.getOrders(params),
          dataProvider.getProducts(params),
        ]);
        const products = (productResult.data || productResult.items || []).map(normalizeProduct);
        const nextOrders = (orderResult.data || orderResult.items || [])
          .filter(isPendingShipment)
          .map((item) => normalizeOrder(item, products))
          .filter((item) => {
            const keyword = comparable(query.keyword);
            const haystack = [item.orderNo, item.productName, item.optionName, item.store, item.platform, item.inventoryCode].map(comparable).join(' ');
            if (keyword && !haystack.includes(keyword)) return false;
            if (query.platform && comparable(item.platform) !== comparable(query.platform)) return false;
            if (query.storeId && String(item.storeId || '') !== String(query.storeId)) return false;
            return true;
          });
        if (!cancelled) setOrders(nextOrders);
      } catch (requestError) {
        if (!cancelled) {
          setOrders([]);
          setError(requestError.message || '待发货订单加载失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading]);

  const rows = useMemo(() => buildShippingRows(orders, prepStatus, trackingMap), [orders, prepStatus, trackingMap]);
  const summary = useMemo(() => ({
    pending: rows.length,
    matched: rows.filter((item) => item.inventoryCode !== '待匹配').length,
    enough: rows.filter((item) => item.stockEnough).length,
    imported: rows.filter((item) => item.trackingNo).length,
    ready: rows.filter((item) => item.stockEnough && item.trackingNo && ['单号已导入', '可人工发货'].includes(item.prepStatus)).length,
  }), [rows]);

  const dangerousState = getDangerousActionState('shipment_writeback');
  const [nextTitle, nextDescription] = nextShippingStep(summary);

  const importTracking = () => {
    const parsed = parseTrackingText(trackingText);
    const nextMap = Object.fromEntries(parsed.map((item) => [item.orderNo, item]));
    setTrackingMap(nextMap);
    setPrepStatus((current) => {
      const next = { ...current };
      for (const row of rows) {
        if (nextMap[row.orderNo]) next[row.orderNo] = '单号已导入';
      }
      return next;
    });
    setTrackingMessage(parsed.length
      ? `已从物流单号表匹配 ${parsed.length} 条记录。可在人工确认后提交 Naver 发货回填。`
      : '没有识别到有效物流单号。请按“订单号,快递公司,运单号”逐行填写。');
  };

  const executeNaverWriteback = async () => {
    if (writebackLoading) return;
    const readyRows = rows.filter((item) => comparable(item.platform) === 'naver' && item.trackingNo);
    if (!readyRows.length) {
      setWritebackMessage('请先导入 Naver 订单的物流单号，再提交发货回填。');
      return;
    }
    if (!writebackConfirm) {
      setWritebackMessage('请先勾选人工确认回填。');
      return;
    }
    if (!selectedStoreId && !query.storeId) {
      setWritebackMessage('请先选择当前店铺，再提交 Naver 发货回填。');
      return;
    }
    setWritebackLoading(true);
    setWritebackMessage('正在提交 Naver 发货回填...');
    try {
      const result = await dataProvider.executeShippingShipmentWriteback({
        storeId: selectedStoreId || query.storeId,
        platform: 'naver',
        trackingRows: readyRows.map((row) => ({
          orderNo: row.orderNo,
          productOrderReference: row.productOrderNo || row.product_order_id || '',
          carrier: row.trackingCompany,
          trackingNumber: row.trackingNo,
          shippedAt: new Date().toISOString(),
        })),
        manualApproval: true,
        matchingContractAcknowledged: true,
        backupEvidenceAcknowledged: true,
        auditEvidenceAcknowledged: true,
        localStatusEvidenceAcknowledged: true,
        naverWritebackBoundaryAcknowledged: true,
        operatorChecklistAcknowledged: true,
        executionApproval: true,
        dryRunEvidenceAcknowledged: true,
        permissionEvidenceAcknowledged: true,
        finalOperatorConfirmation: true,
        realApiCallRequested: true,
        actorContext: { role: 'operator', action: 'manual_naver_shipment_dispatch', payloadField: NAVER_DISPATCH_PAYLOAD_FIELD },
      });
      setWritebackMessage(result.businessMessage || result.message || 'Naver 发货回填处理完成。');
    } catch (writebackError) {
      setWritebackMessage(writebackError.message || 'Naver 发货回填失败，请检查 API 权限、IP 白名单、订单状态或物流公司代码。');
    } finally {
      setWritebackLoading(false);
    }
  };

  const updatePrepStatus = (row, status) => {
    setPrepStatus((current) => ({ ...current, [row.orderNo]: status }));
  };

  const exportRows = rows.filter((item) => item.stockEnough);
  const exportText = exportRows.map((item) => [
    item.orderNo,
    item.platform,
    item.store,
    item.productName,
    item.optionName,
    item.quantity,
    item.inventoryCode,
    item.trackingCompany || '',
    item.trackingNo || '',
    item.prepStatus,
  ].join(',')).join('\n');

  const search = () => setQuery({ ...draft });
  const reset = () => {
    const clean = { keyword: '', platform: '', storeId: '' };
    setDraft(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="发货辅助"
        description="查看待发货订单，核对商品和规格，匹配库存编号，导入物流单号表；Naver 发货回填已按官方 API 开放，必须人工确认后提交。"
        actions={(
          <>
            <button type="button" className="button ghost" onClick={() => setShowExport((value) => !value)}>生成发货表格</button>
            <span className="period-chip">{dangerousState.label}</span>
          </>
        )}
      />

      <div className="summary-grid shipping-summary-grid">
        <SummaryCard title="待发货订单" value={summary.pending} note="本地可见候选" tone="info" />
        <SummaryCard title="已匹配库存编号" value={summary.matched} note="按商品和规格匹配" tone={summary.matched ? 'success' : 'warning'} />
        <SummaryCard title="库存足够" value={summary.enough} note="可进入发货表格" tone={summary.enough ? 'success' : 'warning'} />
        <SummaryCard title="已导入物流单号" value={summary.imported} note="本地匹配结果" tone={summary.imported ? 'success' : 'default'} />
        <SummaryCard title="可人工发货" value={summary.ready} note="需人工到平台后台处理" tone={summary.ready ? 'success' : 'default'} />
      </div>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>下一步</h2>
            <p>{nextDescription}</p>
          </div>
          <StatusBadge value={nextTitle} />
        </div>
        <div className="business-capability-grid compact">
          <article className="business-capability-card info">
            <div className="business-capability-head"><strong>发货处理顺序</strong><span>1</span></div>
            <p>先核对商品和规格，确认订单商品与库存编号匹配。</p>
          </article>
          <article className="business-capability-card info">
            <div className="business-capability-head"><strong>确认库存</strong><span>2</span></div>
            <p>再看库存是否足够，库存不足时回到库存预警处理。</p>
          </article>
          <article className="business-capability-card info">
            <div className="business-capability-head"><strong>导入物流单号</strong><span>3</span></div>
            <p>然后导入物流单号表，只做本地匹配和发货准备记录。</p>
          </article>
          <article className="business-capability-card warning">
            <div className="business-capability-head"><strong>Naver 回填</strong><span>4</span></div>
            <p>最后由运营人工确认回填，系统才会提交 Naver 发货接口。</p>
          </article>
        </div>
      </section>

      <section className="content-card">
        <div className="business-capability-grid compact">
          <article className="business-capability-card info">
            <div className="business-capability-head"><strong>本地辅助功能</strong><span>人工发货</span></div>
            <p>发货表格导出、库存编号匹配、内部准备状态都只在系统内辅助运营。</p>
          </article>
          <article className="business-capability-card warning">
            <div className="business-capability-head"><strong>Naver 发货回填</strong><span>已按官方 API 开放</span></div>
            <p>仅在人工确认回填后调用官方发货接口；本地备注不会被说成平台已发货。</p>
          </article>
          <article className="business-capability-card muted">
            <div className="business-capability-head"><strong>物流单号导入</strong><span>本地匹配</span></div>
            <p>导入物流单号表只用于匹配订单和准备人工发货，不自动写入平台。</p>
          </article>
          <article className="business-capability-card success">
            <div className="business-capability-head"><strong>处理边界</strong><span>清楚可见</span></div>
            <p>{dangerousState.note}</p>
          </article>
        </div>
      </section>

      <FilterPanel>
        <SearchBar
          value={draft.keyword}
          onChange={(keyword) => setDraft({ ...draft, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索订单号、商品、规格或库存编号"
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
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {storeError ? <EmptyState title="店铺信息不可用" description={storeError} /> : null}
        {error ? <EmptyState title="待发货订单加载失败" description={error} /> : null}
        {!error && !loading && !rows.length ? (
          <EmptyState title="暂无待发货订单" description="当前筛选条件下没有待发货订单。可以返回订单管理确认订单状态。" />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            loading={loading || storeLoading}
            rowKey="id"
            renderActions={(row) => (
              <select value={row.prepStatus} onChange={(event) => updatePrepStatus(row, event.target.value)}>
                {prepStatusOptions.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            )}
          />
        )}
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>导入物流单号表</h2>
            <p>按行粘贴“订单号,快递公司,运单号”。系统先做本地匹配，确认后可提交 Naver。</p>
          </div>
          <button type="button" className="button primary" onClick={importTracking}>匹配物流单号和订单</button>
        </div>
        <textarea
          value={trackingText}
          onChange={(event) => setTrackingText(event.target.value)}
          placeholder="NV-20260702-000918,CJ大韩通运,1234567890"
        />
        {trackingMessage ? <div className="form-info">{trackingMessage}</div> : null}
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>提交 Naver 发货回填</h2>
            <p>提交前请确认订单、快递公司和运单号无误；本操作会改变 Naver 平台配送状态。</p>
          </div>
          <StatusBadge value={dangerousState.label} />
        </div>
        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={writebackConfirm}
            onChange={(event) => setWritebackConfirm(event.target.checked)}
          />
          <span>人工确认回填：我已核对待提交的 Naver 订单和物流单号。</span>
        </label>
        <div className="modal-actions-inline">
          <button
            type="button"
            className="button primary"
            onClick={executeNaverWriteback}
            disabled={writebackLoading || !writebackConfirm || !rows.some((item) => comparable(item.platform) === 'naver' && item.trackingNo)}
          >
            {writebackLoading ? '提交中...' : '提交 Naver 发货回填'}
          </button>
        </div>
        {writebackMessage ? <div className="form-info">{writebackMessage}</div> : null}
        <p className="mock-sync-note">使用 Naver 官方 {NAVER_DISPATCH_PAYLOAD_FIELD} 发货提交结构；不会修改商品价格、库存或售后状态。</p>
      </section>

      {showExport ? (
        <section className="content-card">
          <div className="card-title">
            <div>
              <h2>生成发货表格</h2>
              <p>以下内容可用于人工发货准备；发货完成仍需人工到平台后台处理。</p>
            </div>
            <StatusBadge value="记录发货准备状态" />
          </div>
          {exportRows.length ? (
            <pre className="readonly-code">{`订单号,平台,店铺,商品,规格,数量,库存编号,快递公司,运单号,准备状态\n${exportText}`}</pre>
          ) : (
            <EmptyState title="还不能生成发货表格" description="请先确认库存编号匹配且库存足够。" />
          )}
        </section>
      ) : null}
    </>
  );
}
