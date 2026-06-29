import { useEffect, useMemo, useState } from 'react';
import { useStoreContext } from '../../context/StoreContext';
import { useSyncRefresh } from '../../context/SyncRefreshContext';
import dataProvider, { isBackendSource } from '../../services/dataProvider';

const syncConfig = {
  products: {
    label: '商品',
    buttonText: '本地 mock 同步商品',
    successText: '本地 mock 商品同步完成',
    action: dataProvider.syncProductsMock,
  },
  orders: {
    label: '订单',
    buttonText: '本地 mock 同步订单',
    successText: '本地 mock 订单同步完成',
    action: dataProvider.syncOrdersMock,
  },
  customerInquiries: {
    label: '客服',
    buttonText: '本地 mock 同步客服',
    successText: '本地 mock 客服同步完成',
    action: dataProvider.syncCustomerInquiriesMock,
  },
};

const supportedPlatforms = ['naver', 'coupang'];

function normalizePlatform(value) {
  const normalized = String(value || '').trim().toLowerCase();
  return supportedPlatforms.includes(normalized) ? normalized : '';
}

function resolveCredentialPlatform(credentials = []) {
  const match = credentials.find((item) => (
    item.status === 'active'
    && item.hasAccessKey
    && item.hasSecretKey
    && supportedPlatforms.includes(normalizePlatform(item.platform))
  ));
  return normalizePlatform(match?.platform);
}

function sanitizeError(error) {
  return error?.message || '无法连接 Codex1 后端或后端返回错误';
}

export default function MockSyncPanel({ types = ['products', 'orders', 'customerInquiries'], compact = false, onSynced }) {
  const {
    selectedStore,
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const { markSynced } = useSyncRefresh();
  const [credentialPlatform, setCredentialPlatform] = useState('');
  const [manualPlatform, setManualPlatform] = useState('');
  const [metadataError, setMetadataError] = useState('');
  const [loadingTypes, setLoadingTypes] = useState({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const storePlatform = normalizePlatform(selectedStore?.platform);
  const resolvedPlatform = manualPlatform || storePlatform || credentialPlatform;
  const needsPlatformChoice = !storePlatform && !credentialPlatform;
  const visibleTypes = types.filter((type) => syncConfig[type]);

  useEffect(() => {
    let cancelled = false;
    setCredentialPlatform('');
    setMetadataError('');
    setManualPlatform('');

    if (!isBackendSource || !selectedStoreId || storePlatform) return () => { cancelled = true; };

    dataProvider.getCredentials({ storeId: selectedStoreId, page: 1, pageSize: 100 })
      .then((result) => {
        if (cancelled) return;
        const platform = resolveCredentialPlatform(result.data || result.items || []);
        setCredentialPlatform(platform);
      })
      .catch((requestError) => {
        if (cancelled) return;
        setMetadataError(requestError.message || '凭证平台元数据加载失败');
      });

    return () => { cancelled = true; };
  }, [selectedStoreId, storePlatform]);

  const statusText = useMemo(() => {
    if (storeLoading) return '正在读取店铺上下文...';
    if (storeError) return storeError;
    if (!selectedStoreId) return '请先选择店铺';
    if (!resolvedPlatform) return metadataError || '请选择平台';
    return '当前为本地 mock 同步，未连接真实平台';
  }, [metadataError, resolvedPlatform, selectedStoreId, storeError, storeLoading]);

  const runSync = async (type) => {
    if (loadingTypes[type]) return;
    setMessage('');
    setError('');

    if (!selectedStoreId) {
      setError('请先选择店铺');
      return;
    }
    if (!resolvedPlatform) {
      setError('请选择平台');
      return;
    }

    setLoadingTypes((current) => ({ ...current, [type]: true }));
    try {
      await syncConfig[type].action({ storeId: selectedStoreId, platform: resolvedPlatform });
      markSynced(type);
      if (onSynced) await onSynced(type);
      setMessage(`${syncConfig[type].successText}，已写入本地后端，同步日志已刷新`);
    } catch (requestError) {
      setError(`本地 mock 同步失败：${sanitizeError(requestError)}`);
    } finally {
      setLoadingTypes((current) => ({ ...current, [type]: false }));
    }
  };

  return (
    <div className={`mock-sync-panel ${compact ? 'compact' : ''}`}>
      {!compact && <strong>本地 mock 同步</strong>}
      <span className="mock-sync-note">{statusText}</span>
      {needsPlatformChoice && (
        <select value={manualPlatform} onChange={(event) => setManualPlatform(event.target.value)}>
          <option value="">请选择平台</option>
          {supportedPlatforms.map((platform) => <option key={platform} value={platform}>{platform}</option>)}
        </select>
      )}
      {visibleTypes.map((type) => (
        <button
          key={type}
          className="button ghost"
          onClick={() => runSync(type)}
          disabled={storeLoading || loadingTypes[type]}
        >
          {loadingTypes[type] ? `${syncConfig[type].label}同步中...` : syncConfig[type].buttonText}
        </button>
      ))}
      {message && <span className="mock-sync-success">{message}</span>}
      {error && <span className="mock-sync-error">{error}</span>}
    </div>
  );
}
