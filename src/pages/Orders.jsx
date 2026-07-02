import { useMemo, useState } from 'react';
import ResourcePage from '../components/common/ResourcePage';
import MockSyncPanel from '../components/common/MockSyncPanel';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
import { getNaverOrderPreviewStatus } from '../utils/capabilityStatusMapper';
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
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';
  if (!isNaverStore) return null;
  const status = getNaverOrderPreviewStatus();

  return (
    <section className="content-card naver-preview-status-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 订单状态</h2>
          <p>{status.feed.reason}</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>
      <div className="business-capability-grid">
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>订单接口</strong>
            <span>{status.feed.statusLabel}</span>
          </div>
          <p>当前时间范围内没有新的订单变更。</p>
          <small>暂时不需要处理订单同步。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>订单详情</strong>
            <span>{status.detail.statusLabel}</span>
          </div>
          <p>{status.detail.reason}</p>
          <small>{status.detail.nextAction}</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>正式订单同步</strong>
            <span>未开放</span>
          </div>
          <p>{status.sync.reason}</p>
          <small>{status.sync.nextAction}</small>
        </article>
      </div>
      <TechnicalDetails
        description="技术状态仅供管理员排查，普通卖家页面默认不展示。"
        items={[
          { label: 'preview_status', value: 'success_empty' },
          { label: 'detail_query', value: 'not_executed_without_order_change' },
          { label: 'raw_response_saved', value: false },
          { label: 'batch_sync_status', value: 'not_open' },
        ]}
      />
      <p className="mock-sync-note">页面不会展示完整订单标识、客户隐私、收件信息、平台密钥、临时授权、请求签名或订单原始响应。</p>
    </section>
  );
}

export default function Orders() {
  const { selectedStoreId } = useStoreContext();
  const { versions } = useSyncRefresh();
  return (
    <>
      <NaverOrderPreviewStatusPanel />
      <CoupangOrderSyncPanel />
      <ResourcePage
        title="订单管理"
        description="查看订单履约、发货、退款和异常处理状态。"
        resourceName="订单"
        api={api}
        columns={columns}
        fields={fields}
        statuses={statusOptions}
        initialForm={{ orderNo: '', product: '', store: '', customer: '', amount: 0, status: '', createdAt: '' }}
        readOnly={isBackendSource}
        extraParams={isBackendSource ? { storeId: selectedStoreId } : {}}
        reloadKey={`${selectedStoreId}-${versions.orders}`}
        extraActions={isBackendSource ? <MockSyncPanel types={['orders']} compact /> : null}
      />
    </>
  );
}
