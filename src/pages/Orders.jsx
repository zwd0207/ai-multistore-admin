import { useMemo, useState } from 'react';
import ResourcePage from '../components/common/ResourcePage';
import MockSyncPanel from '../components/common/MockSyncPanel';
import StatusBadge from '../components/common/StatusBadge';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
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

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '真实只读检测开关未启用，后端已拒绝发起外部请求。',
    real_api_test_disabled: '真实只读检测开关未启用，后端已拒绝发起外部请求。',
    ip_not_allowed: '当前服务器公网 IP 不在 Coupang OpenAPI allowlist 中。',
    auth_failed: 'Coupang 认证失败，请检查凭证、vendorId、权限或 IP allowlist。',
    CREDENTIAL_DECRYPT_FAILED: '本地凭证解密失败，请在当前加密 key 环境下重新保存凭证。',
    decrypt_failed: '本地凭证解密失败，请在当前加密 key 环境下重新保存凭证。',
  };
  return messages[code] || error?.message || '订单同步请求失败，请检查 Codex1 后端状态。';
}

function validateWindow(startDate, endDate, maxPages) {
  if (!startDate || !endDate) return '请选择 start_date 和 end_date。';
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '日期格式无效。';
  if (start > end) return 'start_date 不能晚于 end_date。';
  const daySpan = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
  if (daySpan > 3) return '单次日期窗口最多 3 天。';
  if (Number(maxPages) < 1 || Number(maxPages) > 3) return 'max_pages 必须在 1 到 3 之间。';
  return '';
}

function ResultGrid({ result, mode }) {
  if (!result) return null;
  const isPreview = mode === 'preview';
  const emptyCount = isPreview
    ? Number(result.wouldCreate || 0) + Number(result.wouldUpdate || 0)
    : Number(result.createdCount || 0) + Number(result.updatedCount || 0);
  const emptyMessage = emptyCount === 0 ? '同步成功，无符合条件订单。' : '';

  return (
    <div className="coupang-sync-result">
      <div className="sync-result-banner">{emptyMessage || '请求完成，结果如下。'}</div>
      <div className="sync-result-grid">
        {isPreview ? (
          <>
            <span>would_create</span><strong>{result.wouldCreate}</strong>
            <span>would_update</span><strong>{result.wouldUpdate}</strong>
          </>
        ) : (
          <>
            <span>created_count</span><strong>{result.createdCount}</strong>
            <span>updated_count</span><strong>{result.updatedCount}</strong>
            <span>skipped_count</span><strong>{result.skippedCount}</strong>
          </>
        )}
        <span>page_count</span><strong>{result.pageCount}</strong>
        <span>next_cursor_exists</span><strong>{result.nextCursorExists ? 'true' : 'false'}</strong>
        <span>date window</span><strong>{result.startDate} ~ {result.endDate}</strong>
        <span>KST window</span>
        <strong>{formatKstDateTimeWithLabel(result.windowStartAt)} / {formatKstDateTimeWithLabel(result.windowEndAt)}</strong>
        <span>sample_ids</span><strong>{result.sampleIds?.length ? result.sampleIds.join(', ') : '[]'}</strong>
      </div>
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
      setMessage('mock 模式不执行 Coupang 真实只读订单检测，请切换 backend 模式使用该入口。');
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
        ? 'Preview 完成：只读取 Coupang 只读接口，未写入 orders。'
        : 'Sync 完成：只写入本地 orders，不会对 Coupang 平台做写操作。');
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
          <h2>Coupang 订单只读同步</h2>
          <p>这是 Coupang 只读接口；Sync 只写本地数据库，不会对 Coupang 平台做写操作。</p>
        </div>
        <span className="period-chip">store #{selectedStoreId} · {selectedStore?.name}</span>
      </div>

      <div className="sync-control-grid">
        <label>
          <span>start_date</span>
          <input type="date" value={form.startDate} onChange={(event) => setForm({ ...form, startDate: event.target.value })} />
        </label>
        <label>
          <span>end_date</span>
          <input type="date" value={form.endDate} onChange={(event) => setForm({ ...form, endDate: event.target.value })} />
        </label>
        <label>
          <span>max_pages</span>
          <input type="number" min="1" max="3" value={form.maxPages} onChange={(event) => setForm({ ...form, maxPages: Number(event.target.value) })} />
        </label>
        <div className="sync-action-row">
          <button className="button ghost" onClick={() => run('preview')} disabled={Boolean(loadingAction)}>Preview</button>
          <button className="button primary" onClick={() => run('sync')} disabled={Boolean(loadingAction)}>Sync</button>
        </div>
      </div>

      <p className="mock-sync-note">单次日期窗口最多 3 天，max_pages 最大 3。不会显示或保存 key / secret / token / header / signature。</p>
      {validationError && <div className="sync-inline-warning">{validationError}</div>}
      {loadingAction && <div className="sync-inline-warning">{loadingAction === 'preview' ? 'Preview 请求中...' : 'Sync 请求中...'}</div>}
      {message && <div className="mock-sync-success">{message}</div>}
      {error && <div className="mock-sync-error">{error}</div>}
      <ResultGrid result={result} mode={mode} />
    </section>
  );
}

export default function Orders() {
  const { selectedStoreId } = useStoreContext();
  const { versions } = useSyncRefresh();
  return (
    <>
      <CoupangOrderSyncPanel />
      <ResourcePage
        title="订单管理"
        description="跟踪各店铺订单履约、配送与退款状态。"
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
