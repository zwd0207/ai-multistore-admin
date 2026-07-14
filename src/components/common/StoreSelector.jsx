import { useStoreContext } from '../../context/StoreContext';

export default function StoreSelector() {
  const {
    stores, selectedStore, selectedStoreId, setSelectedStoreId, loading, error,
  } = useStoreContext();

  if (loading) return <span className="store-selector is-muted">店铺加载中</span>;
  if (error) return <span className="store-selector is-error">{error}</span>;
  if (!stores.length) return <span className="store-selector is-muted">暂无店铺数据</span>;

  const network = selectedStore?.network || {};
  const location = [network.country, network.region, network.city].filter(Boolean).join(' / ');
  const checkedAt = selectedStore?.directoryCheckedAt;
  const checkedLabel = checkedAt && !Number.isNaN(Date.parse(checkedAt))
    ? new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(new Date(checkedAt))
    : '';
  const statusText = {
    no_ip: '暂未分配 IP',
    dynamic: '动态网络，打开店铺时分配 IP',
    not_configured: '网络环境待同步',
    pending: '归属查询中',
    failed: '归属查询失败，等待重试',
    not_applicable: '私网或保留地址',
    success: location || '归属已确认',
  }[network.status] || '网络环境待同步';
  const networkText = [
    network.ipAddress ? `IP ${network.ipAddress}` : null,
    statusText,
    selectedStore?.openOnly ? '仅打开后台' : null,
    checkedLabel ? `最近同步 ${checkedLabel}` : null,
  ].filter(Boolean).join(' · ');

  return (
    <div className="store-selector-block">
      <label className="store-selector">
        <span>当前店铺</span>
        <select value={selectedStoreId || ''} onChange={(event) => setSelectedStoreId(event.target.value)}>
          {stores.map((store) => (
            <option key={store.id} value={store.id}>{store.name}</option>
          ))}
        </select>
      </label>
      <small className={`store-network-summary status-${network.status || 'not-configured'}`} title={networkText}>
        {networkText}
      </small>
    </div>
  );
}
