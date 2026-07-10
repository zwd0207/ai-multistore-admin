import { useMemo, useState } from 'react';
import { useStoreContext } from '../../context/StoreContext';
import { useSyncRefresh } from '../../context/SyncRefreshContext';
import dataProvider from '../../services/dataProvider';
import Modal from './Modal';

const resourceOrder = ['products', 'orders', 'customer_inquiries'];
const coupangIpBlockedLabel = 'Coupang：IP 白名单未通过';
const customerInquiryNotOpenLabel = '客服消息暂未接入';
const connectionBlockedErrorCodes = new Set([
  'ip_not_allowed',
  'auth_failed',
  'permission_forbidden',
  'product_api_not_allowed',
  'order_api_not_allowed',
  'credential_not_ready',
  'credential_invalid',
  'credential_not_found',
  'channel_no_missing',
  'channel_selection_required',
  'blocked_by_connection',
]);

function normalizePlatform(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized.includes('naver')) return 'naver';
  if (normalized.includes('coupang')) return 'coupang';
  return '';
}

function statusTone(label, status, errorCode = '') {
  const text = String(label || '');
  const code = String(errorCode || '').toLowerCase();
  if (connectionBlockedErrorCodes.has(code)) return 'danger';
  if (status === 'success' || text.includes('完成')) return 'success';
  if (text.includes('IP 白名单未通过') || text.includes('权限未开通') || text.includes('平台连接未通过') || status === 'failed') return 'danger';
  if (text.includes('同步中') || text.includes('正在重新验证')) return 'info';
  if (text.includes('暂未') || text.includes('待') || status === 'skipped') return 'warning';
  return 'neutral';
}

function resultTitle(item) {
  return `${item.platform || '-'} · ${item.resourceLabel || item.resource || '-'}`;
}

function sortItems(items = []) {
  return [...items].sort((a, b) => (
    resourceOrder.indexOf(a.resource) - resourceOrder.indexOf(b.resource)
  ));
}

function errorStatusLabel(error) {
  const code = error?.errorCode || error?.detail?.error_code || '';
  const message = error?.message || '';
  if (code === 'ip_not_allowed' || message.includes('IP')) return '最近一次同步：IP 白名单未通过';
  if (String(code).includes('permission') || message.includes('权限')) return '最近一次同步：API 权限未开通';
  return '同步失败';
}

export default function ManualStoreSyncButton() {
  const {
    selectedStore,
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const { markSynced } = useSyncRefresh();
  const [statusLabel, setStatusLabel] = useState('待同步');
  const [statusKind, setStatusKind] = useState('idle');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  const platform = useMemo(
    () => normalizePlatform(selectedStore?.rawPlatform || selectedStore?.platform),
    [selectedStore],
  );
  const tone = statusTone(statusLabel, statusKind);

  const runSync = async () => {
    if (loading) return;
    if (storeLoading || !selectedStoreId) {
      setStatusLabel(storeError || '请先选择店铺');
      setStatusKind('failed');
      return;
    }

    setLoading(true);
    setStatusLabel('正在重新验证...');
    setStatusKind('running');
    try {
      const syncResult = await dataProvider.runManualStoreSync({
        storeId: selectedStoreId,
        platforms: platform ? [platform] : ['naver', 'coupang'],
        includeProducts: true,
        includeOrders: true,
        includeCustomerInquiries: true,
        replacePolicy: 'delete_absent_when_full_snapshot',
      });
      setResult(syncResult);
      setModalOpen(true);
      setStatusLabel(syncResult.statusLabel || '本地同步完成');
      setStatusKind(syncResult.status || 'success');
      markSynced('manualSync');
    } catch (error) {
      setResult(null);
      setModalOpen(false);
      setStatusLabel(errorStatusLabel(error));
      setStatusKind('failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="manual-sync-control">
      <button
        type="button"
        className="button primary manual-sync-button"
        onClick={runSync}
        disabled={loading || storeLoading || Boolean(storeError)}
      >
        {loading ? '正在重新验证...' : '手动同步'}
      </button>
      <span className={`manual-sync-status ${tone}`}>{statusLabel}</span>

      <Modal
        open={modalOpen}
        title={result?.modalTitle || '手动同步结果'}
        onClose={() => setModalOpen(false)}
        showFooter={false}
        width="760px"
      >
        <div className="manual-sync-result">
          <div className="manual-sync-summary">
            <strong>{result?.modalTitle || result?.statusLabel || '同步结果'}</strong>
            <span>只写入本地 ERP，不会修改 Naver / Coupang 平台数据。</span>
            {result?.connectionBlocked ? (
              <span>本次重新验证仍未通过：请确认平台白名单生效时间、服务器出口 IP、店铺 API 权限。</span>
            ) : null}
          </div>
          <div className="manual-sync-result-list">
            {sortItems(result?.items || []).map((item) => (
              <article key={`${item.rawPlatform}-${item.resource}`} className={`manual-sync-result-item ${statusTone(item.message, item.status, item.errorCode)}`}>
                <div>
                  <strong>{resultTitle(item)}</strong>
                  <p>{item.message || (item.resource === 'customer_inquiries' ? customerInquiryNotOpenLabel : '暂无结果')}</p>
                </div>
                <div className="manual-sync-counts">
                  <span>新增 {item.createdCount}</span>
                  <span>更新 {item.updatedCount}</span>
                  <span>删除 {item.deletedCount}</span>
                </div>
              </article>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  );
}
