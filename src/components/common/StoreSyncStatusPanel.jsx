import StatusBadge from './StatusBadge';
import { formatStoreSyncTime, storeSyncStatusLabel } from '../../utils/storeSyncStatus';

const RESOURCE_ROWS = [
  ['orders', '订单'],
  ['customerInquiries', '客服'],
  ['products', '商品'],
  ['logistics', '物流'],
];

function ResourceStatus({ resource, canViewFailureReason }) {
  const unavailable = resource?.safeFailureReason === 'not_supported';
  const label = unavailable ? resource.safeFailureLabel : storeSyncStatusLabel(resource?.status);
  return (
    <article className="store-sync-resource">
      <div className="store-sync-resource-heading">
        <strong>{label}</strong>
        <StatusBadge value={unavailable ? '暂未接入' : label} />
      </div>
      <dl>
        <div><dt>最后成功</dt><dd>{formatStoreSyncTime(resource?.lastSuccessAt)}</dd></div>
        <div><dt>下次同步</dt><dd>{formatStoreSyncTime(resource?.nextRunAt)}</dd></div>
      </dl>
      {canViewFailureReason && resource?.safeFailureLabel && !unavailable ? (
        <details className="store-sync-safe-reason">
          <summary>查看失败原因</summary>
          <p>{resource.safeFailureLabel}</p>
        </details>
      ) : null}
    </article>
  );
}

export default function StoreSyncStatusPanel({ rows = [], canViewFailureReason = () => false }) {
  return (
    <section className="content-card store-sync-panel">
      <div className="card-title">
        <div>
          <h2>店铺自动同步状态</h2>
          <p>按店铺查看订单、客服、商品和物流的自动读取状态。</p>
        </div>
      </div>
      {!rows.length ? (
        <p className="store-sync-empty">暂无店铺同步状态。</p>
      ) : (
        <div className="store-sync-list">
          {rows.map((row) => (
            <article className="store-sync-store" key={row.storeId}>
              <div className="store-sync-store-heading">
                <strong>{row.storeName}</strong>
                <span>{row.platform || '-'}</span>
              </div>
              <div className="store-sync-resource-grid">
                {RESOURCE_ROWS.map(([key, label]) => (
                  <div key={key} className="store-sync-resource-column">
                    <h3>{label}</h3>
                    <ResourceStatus
                      resource={row.automaticReadStatus?.[key]}
                      canViewFailureReason={canViewFailureReason(row.storeId)}
                    />
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
