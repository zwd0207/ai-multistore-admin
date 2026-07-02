import { useEffect, useMemo, useState } from 'react';
import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
import { getNaverOrderPreviewStatus } from '../utils/capabilityStatusMapper';
import { buildNaverOrderFulfillmentSummary } from '../utils/naverOrderFulfillment';
import { formatKstDateTimeWithLabel, getKstDateOffsetString, getKstTodayString } from '../utils/time';

const api = {
  list: dataProvider.getOrders,
  create: mockApi.createOrder,
  update: mockApi.updateOrder,
  remove: mockApi.deleteOrder,
};

const statusOptions = ['待发货', '配送中', '已完成', '取消/退款'];
const columns = [
  { key: 'orderNo', title: '订单编号', render: (value) => <strong>{value}</strong> },
  { key: 'product', title: '商品' },
  { key: 'store', title: '店铺' },
  { key: 'customer', title: '客户' },
  { key: 'phone', title: '联系电话' },
  { key: 'amount', title: '订单金额', render: (value, row) => `${Number(value || 0).toLocaleString()} ${row.currency || 'KRW'}` },
  { key: 'status', title: '订单状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '下单时间' },
];
const fields = [
  { key: 'orderNo', label: '订单编号', required: true },
  { key: 'product', label: '商品名', required: true },
  { key: 'store', label: '店铺', required: true },
  { key: 'customer', label: '客户', required: true },
  { key: 'amount', label: '订单金额（KRW）', type: 'number', required: true },
  { key: 'status', label: '订单状态', type: 'select', required: true, options: statusOptions },
  { key: 'createdAt', label: '下单时间', required: true, placeholder: '2026-06-29 15:00' },
];

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function firstText(...values) {
  const value = values
    .map((item) => {
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        return item.label_zh ?? item.label ?? item.name ?? item.raw ?? item.value ?? '';
      }
      if (Array.isArray(item)) return item.filter(Boolean).join(', ');
      return item;
    })
    .find((item) => item !== undefined && item !== null && String(item).trim() !== '');
  return value === undefined ? '' : String(value).trim();
}

function displayText(...values) {
  return firstText(...values) || '待接入';
}

function formatMoney(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function getOrderStoreId(order = {}) {
  return order.storeId ?? order.store_id;
}

function isNaverOrderForStore(order = {}, selectedStore = {}, selectedStoreId = '') {
  const platform = normalizePlatform(order.rawPlatform || order.platform);
  if (platform !== 'naver') return false;
  const orderStoreId = getOrderStoreId(order);
  if (selectedStoreId && orderStoreId !== undefined && orderStoreId !== null) {
    return String(orderStoreId) === String(selectedStoreId);
  }
  return firstText(order.store, order.store_name) === firstText(selectedStore?.name);
}

function getCompleteOrderFields(order = {}, previewFields = {}) {
  const rawData = order.raw_data || {};
  const complete = previewFields || {};
  return {
    orderNo: displayText(complete.externalOrderId, complete.external_order_id, order.fullOrderNo, order.orderNo, order.external_order_id),
    productOrderNo: displayText(complete.externalProductOrderId, complete.external_product_order_id, order.productOrderNo, order.external_product_order_id, rawData.external_product_order_id),
    platformProductId: displayText(complete.platformProductId, complete.platform_product_id, order.platformProductId, order.platform_product_id, rawData.platform_product_id),
    productName: displayText(complete.productName, complete.product_name, order.productName, order.product, order.product_name),
    optionName: displayText(complete.optionName, complete.option_name, order.optionName, order.option_name, rawData.option_name),
    quantity: displayText(complete.quantity, order.quantity),
    amount: formatMoney(complete.orderAmount ?? complete.order_amount ?? order.amount ?? order.order_amount, complete.currency || order.currency),
    orderStatus: displayText(complete.orderStatusLabelZh, complete.order_status_label_zh, complete.orderStatus, complete.order_status, order.status, order.order_status),
    paymentStatus: displayText(complete.paymentStatus, complete.payment_status, order.paymentStatus, order.payment_status),
    deliveryStatus: displayText(complete.deliveryStatusLabelZh, complete.delivery_status_label_zh, complete.deliveryStatus, complete.delivery_status, order.deliveryStatusLabelZh, order.delivery_status_label_zh, order.deliveryStatus, order.delivery_status),
    claimStatus: displayText(complete.claimStatusLabelZh, complete.claim_status_label_zh, complete.claimStatus, complete.claim_status, order.claimStatusLabelZh, order.claim_status_label_zh, order.claimStatus, order.claim_status),
    buyerName: displayText(complete.buyerName, complete.buyer_name, order.buyerName, order.buyer_name, order.customerName, order.customer),
    buyerPhone: displayText(complete.buyerPhone, complete.buyer_phone, order.buyerPhone, order.buyer_phone, order.phone),
    receiverName: displayText(complete.receiverName, complete.receiver_name, order.receiverName, order.receiver_name),
    receiverPhone: displayText(complete.receiverPhone, complete.receiver_phone, order.receiverPhone, order.receiver_phone),
    receiverAddress: displayText(complete.receiverAddress, complete.receiver_address, order.receiverAddress, order.receiver_address),
    zipCode: displayText(complete.zipCode, complete.zip_code, order.zipCode, order.zip_code),
    orderedAt: displayText(formatKstDateTimeWithLabel(complete.orderedAt || complete.ordered_at || order.ordered_at || order.createdAt || order.created_at), '待接入'),
    paidAt: displayText(formatKstDateTimeWithLabel(complete.paidAt || complete.paid_at || order.paid_at || order.paidAt), '待接入'),
    sourceType: displayText(order.sourceType, order.source_type),
    mappingVersion: displayText(complete.mappingVersion, complete.mapping_version, order.mappingVersion, rawData.mapping_version),
    rawResponseSaved: complete.rawResponseSaved ?? complete.raw_response_saved ?? order.rawResponseSaved ?? rawData.raw_response_saved ?? false,
  };
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '后端真实只读开关未开启，本次没有访问平台。',
    real_api_test_disabled: '后端真实只读开关未开启，本次没有访问平台。',
    ip_not_allowed: '服务器 IP 不在平台白名单内，请联系管理员处理。',
    auth_failed: '平台授权失败，请检查连接资料、权限或 IP 白名单。',
    CREDENTIAL_DECRYPT_FAILED: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
    decrypt_failed: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
  };
  return messages[code] || error?.message || '订单请求失败，请检查后端服务状态。';
}

function validateWindow(startDate, endDate, maxPages) {
  if (!startDate || !endDate) return '请选择开始日期和结束日期。';
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '日期格式无效。';
  if (start > end) return '开始日期不能晚于结束日期。';
  const daySpan = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
  if (daySpan > 3) return '单次订单查询窗口最多 3 天。';
  if (Number(maxPages) < 1 || Number(maxPages) > 3) return '单次最多读取 3 页。';
  return '';
}

function ResultGrid({ result, mode }) {
  if (!result) return null;
  const isPreview = mode === 'preview';
  const createCount = Number(isPreview ? result.wouldCreate : result.createdCount || 0);
  const updateCount = Number(isPreview ? result.wouldUpdate : result.updatedCount || 0);
  const skippedCount = Number(result.skippedCount || 0);

  return (
    <div className="coupang-sync-result">
      <div className="sync-result-banner">
        {isPreview
          ? `订单预览完成：预计新增 ${createCount} 条，预计更新 ${updateCount} 条。`
          : `本地订单写入完成：新增 ${createCount} 条，更新 ${updateCount} 条，跳过 ${skippedCount} 条。`}
      </div>
      <TechnicalDetails
        items={[
          { label: 'would_create', value: result.wouldCreate },
          { label: 'would_update', value: result.wouldUpdate },
          { label: 'created_count', value: result.createdCount },
          { label: 'updated_count', value: result.updatedCount },
          { label: 'skipped_count', value: result.skippedCount },
          { label: 'page_count', value: result.pageCount },
          { label: 'next_cursor_exists', value: result.nextCursorExists },
          { label: 'date_window', value: `${result.startDate} ~ ${result.endDate}` },
          { label: 'KST_window', value: `${formatKstDateTimeWithLabel(result.windowStartAt)} / ${formatKstDateTimeWithLabel(result.windowEndAt)}` },
          { label: 'sample_ids', value: result.sampleIds?.length ? result.sampleIds.join(', ') : '[]' },
        ]}
      />
    </div>
  );
}

function CoupangOrderSyncPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const { markSynced } = useSyncRefresh();
  const [form, setForm] = useState({
    startDate: getKstDateOffsetString(-2),
    endDate: getKstTodayString(),
    maxPages: 1,
  });
  const [mode, setMode] = useState('');
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loadingAction, setLoadingAction] = useState('');

  const isCoupangStore = normalizePlatform(selectedStore?.platform) === 'coupang';
  const validationError = useMemo(
    () => validateWindow(form.startDate, form.endDate, form.maxPages),
    [form.endDate, form.maxPages, form.startDate],
  );

  if (!isCoupangStore) return null;

  const run = async (action) => {
    setMessage('');
    setError('');
    setResult(null);
    setMode(action);

    if (!isBackendSource) {
      setMessage('mock 模式只展示页面效果，不执行真实平台订单读取。');
      return;
    }
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoadingAction(action);
    try {
      const payload = {
        storeId: selectedStoreId,
        startDate: form.startDate,
        endDate: form.endDate,
        maxPages: Number(form.maxPages),
      };
      const nextResult = action === 'preview'
        ? await dataProvider.previewCoupangOrders(payload)
        : await dataProvider.syncCoupangOrders(payload);
      setResult(nextResult);
      setMessage(action === 'preview'
        ? '订单预览已完成，本次只估算影响，不写入本地订单。'
        : '订单已写入本地数据库，不会对 Coupang 平台做写操作。');
      if (action === 'sync') markSynced('orders');
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoadingAction('');
    }
  };

  return (
    <section className="content-card coupang-order-sync-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Coupang 订单读取</h2>
          <p>先查看指定日期内是否有订单，再按需写入本地。不会修改 Coupang 平台订单。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>

      <div className="sync-control-grid">
        <label>
          <span>开始日期</span>
          <input type="date" value={form.startDate} onChange={(event) => setForm({ ...form, startDate: event.target.value })} />
        </label>
        <label>
          <span>结束日期</span>
          <input type="date" value={form.endDate} onChange={(event) => setForm({ ...form, endDate: event.target.value })} />
        </label>
        <label>
          <span>最多读取页数</span>
          <input type="number" min="1" max="3" value={form.maxPages} onChange={(event) => setForm({ ...form, maxPages: Number(event.target.value) })} />
        </label>
        <div className="sync-action-row">
          <button className="button ghost" onClick={() => run('preview')} disabled={Boolean(loadingAction)}>预览订单</button>
          <button className="button primary" onClick={() => run('sync')} disabled={Boolean(loadingAction)}>写入本地</button>
        </div>
      </div>

      <p className="mock-sync-note">单次日期窗口最多 3 天，最多读取 3 页。页面不会显示平台密钥、临时授权、请求签名或订单原始响应。</p>
      {validationError && <div className="sync-inline-warning">{validationError}</div>}
      {loadingAction && <div className="sync-inline-warning">{loadingAction === 'preview' ? '正在预览订单...' : '正在写入本地订单...'}</div>}
      {message && <div className="mock-sync-success">{message}</div>}
      {error && <div className="mock-sync-error">{error}</div>}
      <ResultGrid result={result} mode={mode} />
    </section>
  );
}

function NaverOrderPreviewStatusPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [orders, setOrders] = useState([]);
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';
  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setOrders([]);
      return undefined;
    }
    let cancelled = false;
    dataProvider.getOrders({
      storeId: selectedStoreId,
      platform: 'naver',
      page: 1,
      pageSize: 100,
    })
      .then((orderResponse) => {
        if (!cancelled) setOrders(orderResponse.data || orderResponse.items || []);
      })
      .catch(() => {
        if (!cancelled) setOrders([]);
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId]);

  if (!isNaverStore) return null;
  const status = getNaverOrderPreviewStatus();
  const fulfillmentSummary = buildNaverOrderFulfillmentSummary(orders, {
    selectedStore,
    selectedStoreId,
  });

  return (
    <section className="content-card naver-preview-status-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 订单状态</h2>
          <p>Naver 单条订单本地写入测试已完成。订单详情完整字段先在 mock 受控展示；真实后端完整字段保存需要后续单独批准。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>
      <div className="business-capability-grid compact">
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>本地订单</strong>
            <span>已写入 1 条</span>
          </div>
          <p>已完成 1 条 Naver 订单本地写入测试。</p>
          <small>订单状态为已付款 / 新订单，金额 499,000 KRW。</small>
        </article>
        <article className={`business-capability-card ${fulfillmentSummary.tone}`}>
          <div className="business-capability-head">
            <strong>履约 / 售后只读分类</strong>
            <span>{fulfillmentSummary.statusLabel}</span>
          </div>
          <p>{fulfillmentSummary.businessMessage}</p>
          <small>状态只来自本地脱敏订单，不请求 Naver，不执行平台写操作。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>新订单 / 待发货</strong>
            <span>{fulfillmentSummary.newOrders + fulfillmentSummary.pendingDispatch} 条</span>
          </div>
          <p>新订单 {fulfillmentSummary.newOrders} 条，待发货 {fulfillmentSummary.pendingDispatch} 条。</p>
          <small>不把已付款订单误显示为已发货。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>配送状态</strong>
            <span>{fulfillmentSummary.inDelivery + fulfillmentSummary.delivered} 条</span>
          </div>
          <p>配送中 {fulfillmentSummary.inDelivery} 条，配送完成 {fulfillmentSummary.delivered} 条。</p>
          <small>当前只读展示配送状态，不接入配送写接口。</small>
        </article>
        <article className={fulfillmentSummary.claimRequestCount > 0 ? 'business-capability-card warning' : 'business-capability-card muted'}>
          <div className="business-capability-head">
            <strong>取消 / 退货 / 换货</strong>
            <span>{fulfillmentSummary.claimRequestCount} 条</span>
          </div>
          <p>取消请求 {fulfillmentSummary.cancelRequests} 条，退货请求 {fulfillmentSummary.returnRequests} 条，换货请求 {fulfillmentSummary.exchangeRequests} 条。</p>
          <small>售后请求只进入待办识别，不自动处理。</small>
        </article>
        <article className={fulfillmentSummary.unknown > 0 ? 'business-capability-card warning' : 'business-capability-card muted'}>
          <div className="business-capability-head">
            <strong>异常订单</strong>
            <span>{fulfillmentSummary.unknown} 条</span>
          </div>
          <p>{fulfillmentSummary.unknown > 0 ? '存在未识别状态，需要人工确认。' : '当前没有未识别订单状态。'}</p>
          <small>未知状态不会抛错，也不会进入平台写操作。</small>
        </article>
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>只读复核</strong>
            <span>{status.feed.statusLabel}</span>
          </div>
          <p>{status.feed.reason}</p>
          <small>复核没有新增写入，也没有重复创建订单。</small>
        </article>
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>详情展示边界</strong>
            <span>受控展示</span>
          </div>
          <p>完整买家和收件信息只放在订单详情区，Dashboard、日志和技术详情不展开。</p>
          <small>未保存平台原始响应、授权凭证、请求头或签名。</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>正式订单同步</strong>
            <span>未开放</span>
          </div>
          <p>{status.sync.reason}</p>
          <small>批量订单同步、发货、取消、退货、换货写操作都需要单独确认。</small>
        </article>
      </div>
      <TechnicalDetails
        description="技术状态仅供管理员排查，普通卖家页面默认不展示。"
        items={[
          { label: 'orders_store8', value: 1 },
          { label: 'source_type', value: 'naver_real_order_sync' },
          { label: 'post_write_preview_status', value: 'success' },
          { label: 'local_sync_result.status', value: 'not_requested' },
          { label: 'raw_response_saved', value: false },
          { label: 'privacy_fields_redacted', value: true },
          { label: 'address_saved', value: false },
          { label: 'fulfillment.source', value: fulfillmentSummary.source },
          { label: 'fulfillment.total', value: fulfillmentSummary.total },
          { label: 'fulfillment.new_orders', value: fulfillmentSummary.newOrders },
          { label: 'fulfillment.pending_dispatch', value: fulfillmentSummary.pendingDispatch },
          { label: 'fulfillment.in_delivery', value: fulfillmentSummary.inDelivery },
          { label: 'fulfillment.delivered', value: fulfillmentSummary.delivered },
          { label: 'fulfillment.cancel_requests', value: fulfillmentSummary.cancelRequests },
          { label: 'fulfillment.return_requests', value: fulfillmentSummary.returnRequests },
          { label: 'fulfillment.exchange_requests', value: fulfillmentSummary.exchangeRequests },
          { label: 'fulfillment.unknown', value: fulfillmentSummary.unknown },
          { label: 'platform_writes_enabled', value: fulfillmentSummary.platformWritesEnabled },
          { label: 'formal_order_sync_status', value: 'not_open' },
        ]}
      />
      <p className="mock-sync-note">订单详情区可受控展示完整订单号、商品编号和买家信息；平台密钥、临时授权、请求签名和订单原始响应仍不会展示。</p>
    </section>
  );
}

function DetailItem({ label, value }) {
  return (
    <div className="detail-item">
      <span>{label}</span>
      <strong>{value || '待接入'}</strong>
    </div>
  );
}

function NaverOrderCompleteDetailPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [orders, setOrders] = useState([]);
  const [selectedOrderId, setSelectedOrderId] = useState('');
  const [loadError, setLoadError] = useState('');
  const [previewResult, setPreviewResult] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setOrders([]);
      setSelectedOrderId('');
      setLoadError('');
      setPreviewResult(null);
      setPreviewError('');
      return undefined;
    }
    let cancelled = false;
    setLoadError('');
    setPreviewResult(null);
    setPreviewError('');
    dataProvider.getOrders({
      storeId: selectedStoreId,
      platform: 'naver',
      page: 1,
      pageSize: 100,
    })
      .then((orderResponse) => {
        if (cancelled) return;
        const naverOrders = (orderResponse.data || orderResponse.items || []).filter(
          (order) => isNaverOrderForStore(order, selectedStore, selectedStoreId),
        );
        setOrders(naverOrders);
        setSelectedOrderId((currentId) => (
          naverOrders.some((order) => String(order.id) === String(currentId))
            ? currentId
            : String(naverOrders[0]?.id || '')
        ));
      })
      .catch((error) => {
        if (!cancelled) {
          setOrders([]);
          setSelectedOrderId('');
          setLoadError(error.message || 'Naver 订单详情加载失败。');
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStore, selectedStoreId]);

  if (!isNaverStore) return null;

  const activeOrder = orders.find((order) => String(order.id) === String(selectedOrderId)) || orders[0];
  const previewFields = previewResult?.available ? previewResult.completeFields : {};
  const fields = activeOrder ? getCompleteOrderFields(activeOrder, previewFields) : null;
  const completeFieldReady = Boolean(activeOrder && fields?.orderNo !== '待接入' && fields?.buyerName !== '待接入');
  const previewAllowed = !isBackendSource || String(selectedStoreId) === '8';

  const runCompleteFieldPreview = async () => {
    if (previewLoading || !activeOrder || !previewAllowed) return;
    setPreviewLoading(true);
    setPreviewError('');
    setPreviewResult(null);
    try {
      const result = await dataProvider.previewNaverOrderCompleteFields({
        storeId: selectedStoreId,
        credentialId: 7,
      });
      setPreviewResult(result);
      if (!result.available) {
        setPreviewError(result.businessMessage || '当前窗口没有可展示的 Naver 订单完整字段。');
      }
    } catch (error) {
      setPreviewError(formatError(error));
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 订单详情</h2>
          <p>完整订单号、商品编号和买家信息只在内部订单详情区展示；Dashboard 仍保持摘要口径。</p>
        </div>
        <span className="period-chip">{selectedStore?.name || 'Naver 店铺'}</span>
      </div>
      <div className="sync-action-row">
        <button
          className="button primary"
          onClick={runCompleteFieldPreview}
          disabled={!activeOrder || previewLoading || !previewAllowed}
        >
          {previewLoading ? '读取完整字段中...' : '读取完整字段只读预览'}
        </button>
        <span className="mock-sync-note">
          {previewAllowed
            ? '手动读取 Codex1 只读 preview，不写 orders，不开放正式订单同步。'
            : '当前完整字段只读预览仅限 pxg球包店 store_id=8。'}
        </span>
      </div>
      {loadError ? (
        <div className="mock-sync-error">{loadError}</div>
      ) : null}
      {previewResult?.available ? (
        <div className="mock-sync-success">已读取完整字段只读预览，页面仅展示结果，不写库。</div>
      ) : null}
      {previewError ? (
        <div className="mock-sync-error">{previewError}</div>
      ) : null}
      {!activeOrder ? (
        <div className="empty-state">当前店铺暂无可展示的 Naver 本地订单详情。</div>
      ) : (
        <>
          <div className="detail-toolbar">
            {orders.map((order) => (
              <button
                className={String(order.id) === String(activeOrder.id) ? 'button primary' : 'button ghost'}
                key={order.id}
                onClick={() => setSelectedOrderId(String(order.id))}
              >
                {displayText(order.orderNo, order.external_order_id)}
              </button>
            ))}
          </div>
          <div className="detail-modal">
            <section className="detail-section">
              <h3>订单信息</h3>
              <div className="detail-grid">
                <DetailItem label="完整订单号" value={fields.orderNo} />
                <DetailItem label="商品订单号" value={fields.productOrderNo} />
                <DetailItem label="订单状态" value={fields.orderStatus} />
                <DetailItem label="付款状态" value={fields.paymentStatus} />
                <DetailItem label="订单金额" value={fields.amount} />
                <DetailItem label="下单时间" value={fields.orderedAt} />
                <DetailItem label="付款时间" value={fields.paidAt} />
                <DetailItem label="来源" value={fields.sourceType} />
              </div>
            </section>
            <section className="detail-section">
              <h3>商品信息</h3>
              <div className="detail-grid">
                <DetailItem label="平台商品编号" value={fields.platformProductId} />
                <DetailItem label="商品名" value={fields.productName} />
                <DetailItem label="选项" value={fields.optionName} />
                <DetailItem label="数量" value={fields.quantity} />
              </div>
            </section>
            <section className="detail-section">
              <h3>买家与收件信息</h3>
              <div className="detail-grid">
                <DetailItem label="买家姓名" value={fields.buyerName} />
                <DetailItem label="买家电话" value={fields.buyerPhone} />
                <DetailItem label="收件人" value={fields.receiverName} />
                <DetailItem label="收件电话" value={fields.receiverPhone} />
                <DetailItem label="邮编" value={fields.zipCode} />
                <DetailItem label="收件地址" value={fields.receiverAddress} />
              </div>
            </section>
            <section className="detail-section">
              <h3>配送与售后</h3>
              <div className="detail-grid">
                <DetailItem label="配送状态" value={fields.deliveryStatus} />
                <DetailItem label="售后状态" value={fields.claimStatus} />
              </div>
            </section>
          </div>
          <p className="mock-sync-note">页面不会自动请求 Naver；只有点击完整字段只读预览时才通过 Codex1 做受控读取。该操作不写 orders，不保存原始响应，不开放正式订单同步。</p>
          <TechnicalDetails
            description="仅保留字段可用性和口径，不展示平台原始响应。"
            items={[
              { label: 'complete_field_view', value: completeFieldReady },
              { label: 'complete_field_preview_requested', value: Boolean(previewResult?.requested) },
              { label: 'complete_field_preview_available', value: Boolean(previewResult?.available) },
              { label: 'preview_status', value: previewResult?.previewStatus },
              { label: 'feed_called', value: previewResult?.feedCalled },
              { label: 'detail_called', value: previewResult?.detailCalled },
              { label: 'dashboard_summary_only', value: true },
              { label: 'formal_order_sync_open', value: false },
              { label: 'raw_response_saved', value: fields.rawResponseSaved },
              { label: 'mapping_version', value: fields.mappingVersion },
              { label: 'codex1_schema_write_enabled', value: previewResult?.savePlan?.codex1SchemaWriteEnabled ?? false },
              { label: 'orders_written', value: previewResult?.savePlan?.ordersWritten ?? false },
              { label: 'sync_log_written', value: previewResult?.savePlan?.syncLogWritten ?? false },
              { label: 'tested_success_written', value: previewResult?.savePlan?.testedSuccessWritten ?? false },
            ]}
          />
        </>
      )}
    </section>
  );
}

export default function Orders() {
  const { selectedStoreId, loading: storeLoading } = useStoreContext();
  const { versions } = useSyncRefresh();
  const pageApi = useMemo(() => ({
    ...api,
    list: (params) => {
      if (isBackendSource && (storeLoading || !selectedStoreId)) {
        return Promise.resolve({
          data: [],
          items: [],
          total: 0,
          page: params?.page || 1,
          pageSize: params?.pageSize || 5,
        });
      }
      return dataProvider.getOrders(params);
    },
  }), [selectedStoreId, storeLoading]);
  return (
    <>
      <NaverOrderPreviewStatusPanel />
      <NaverOrderCompleteDetailPanel />
      <CoupangOrderSyncPanel />
      <ResourcePage
        title="订单管理"
        description="查看订单履约、发货、退款和异常处理状态。"
        resourceName="订单"
        api={pageApi}
        columns={columns}
        fields={fields}
        statuses={statusOptions}
        initialForm={{ orderNo: '', product: '', store: '', customer: '', amount: 0, status: '', createdAt: '' }}
        readOnly={isBackendSource}
        extraParams={isBackendSource && selectedStoreId ? { storeId: selectedStoreId } : {}}
        reloadKey={`${selectedStoreId}-${versions.orders}`}
      />
    </>
  );
}
