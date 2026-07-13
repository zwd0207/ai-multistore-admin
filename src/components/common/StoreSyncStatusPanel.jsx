import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from './StatusBadge';
import dataProvider from '../../services/dataProvider';
import { formatStoreSyncTime, storeSyncStatusLabel } from '../../utils/storeSyncStatus';

const RESOURCE_ROWS = [
  ['orders', '订单'],
  ['customerInquiries', '客服'],
  ['products', '商品'],
  ['logistics', '物流'],
];
const MAX_RECOVERY_POLLS = 17;
const RECOVERY_POLL_DELAY_MS = 4000;

function connectionActionPath(storeId) {
  return `/stores?storeId=${encodeURIComponent(storeId)}&focus=connection`;
}

function ResourceStatus({ resource, showOperatorMessage }) {
  const label = storeSyncStatusLabel(resource?.status);
  return (
    <article className="store-sync-resource">
      <div className="store-sync-resource-heading">
        <strong>{label}</strong>
        <StatusBadge value={label} />
      </div>
      <dl>
        <div><dt>最后成功</dt><dd>{formatStoreSyncTime(resource?.lastSuccessAt)}</dd></div>
        <div><dt>下次同步</dt><dd>{formatStoreSyncTime(resource?.nextRunAt)}</dd></div>
      </dl>
      {showOperatorMessage && resource?.operatorMessage ? (
        <p className="store-sync-operator-message">{resource.operatorMessage}</p>
      ) : null}
    </article>
  );
}

function attentionResources(row) {
  return RESOURCE_ROWS.filter(([key]) => row.automaticReadStatus?.[key]?.attentionState !== 'none');
}

function updateRow(rows, nextRow) {
  return rows.map((row) => (
    String(row.storeId) === String(nextRow.storeId) ? nextRow : row
  ));
}

function waitForPoll() {
  return new Promise((resolve) => setTimeout(resolve, RECOVERY_POLL_DELAY_MS));
}

function AllStoreStatus({ rows, adminStoreIds }) {
  return (
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
                  showOperatorMessage={adminStoreIds.has(String(row.storeId))}
                />
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

export default function StoreSyncStatusPanel({ rows = [], attentionSummary = {}, canManageRecovery = () => false }) {
  const [visibleRows, setVisibleRows] = useState(rows);
  const [visibleAttentionSummary, setVisibleAttentionSummary] = useState(attentionSummary);
  const [recoveringStoreId, setRecoveringStoreId] = useState('');
  const [feedback, setFeedback] = useState({});

  useEffect(() => setVisibleRows(rows), [rows]);
  useEffect(() => setVisibleAttentionSummary(attentionSummary), [attentionSummary]);

  const adminStoreIds = useMemo(
    () => new Set(visibleRows.filter((row) => canManageRecovery(row.storeId)).map((row) => String(row.storeId))),
    [visibleRows, canManageRecovery],
  );
  const attentionRows = visibleRows
    .map((row) => ({ row, attention: attentionResources(row) }))
    .filter(({ attention }) => attention.length);

  const pollStoreOverview = async (storeId) => {
    let observedAutomaticRetry = false;
    for (let attempt = 0; attempt < MAX_RECOVERY_POLLS; attempt += 1) {
      await waitForPoll();
      try {
        const overview = await dataProvider.getStoreOverview({ includeInactive: false });
        setVisibleAttentionSummary(overview?.automaticReadAttentionSummary || {});
        const nextRow = (overview?.stores || []).find((item) => String(item.storeId) === String(storeId));
        if (!nextRow) return;
        setVisibleRows((current) => updateRow(current, nextRow));
        const attention = attentionResources(nextRow);
        if (attention.some(([key]) => nextRow.automaticReadStatus?.[key]?.attentionState === 'automatic_retry')) {
          observedAutomaticRetry = true;
        }
        const reblocked = observedAutomaticRetry
          && attention.some(([key]) => nextRow.automaticReadStatus?.[key]?.attentionState === 'admin_action');
        if (!attention.length || reblocked || attempt === MAX_RECOVERY_POLLS - 1) return;
      } catch {
        return;
      }
    }
  };

  const recover = async (row) => {
    if (recoveringStoreId || !adminStoreIds.has(String(row.storeId))) return;
    setRecoveringStoreId(String(row.storeId));
    setFeedback((current) => ({ ...current, [row.storeId]: '' }));
    try {
      await dataProvider.recoverAutomaticRead(row.storeId);
      setFeedback((current) => ({ ...current, [row.storeId]: '验证通过，已安排恢复' }));
      await pollStoreOverview(row.storeId);
    } catch (error) {
      setFeedback((current) => ({
        ...current,
        [row.storeId]: error.message || '恢复安排失败，请稍后重试。',
      }));
    } finally {
      setRecoveringStoreId('');
    }
  };

  return (
    <section className="content-card store-sync-panel">
      <div className="card-title">
        <div>
          <h2>
            店铺自动同步状态
            {visibleAttentionSummary.affectedStoreCount ? `（${visibleAttentionSummary.affectedStoreCount} 个店铺需关注）` : ''}
          </h2>
          <p>
            {visibleAttentionSummary.affectedResourceCount
              ? `有 ${visibleAttentionSummary.affectedResourceCount} 个资源需要关注，按店铺查看订单、客服、商品和物流的自动读取状态。`
              : '按店铺查看订单、客服、商品和物流的自动读取状态。'}
          </p>
        </div>
      </div>
      {!visibleRows.length ? (
        <p className="store-sync-empty">暂无店铺同步状态。</p>
      ) : (
        <>
          {!attentionRows.length ? <p className="store-sync-healthy-line">自动读取正常</p> : (
            <div className="store-sync-attention-stores">
              {attentionRows.map(({ row, attention }) => {
            const isAdmin = adminStoreIds.has(String(row.storeId));
            const actionResource = attention
              .map(([key]) => row.automaticReadStatus?.[key])
              .find((resource) => resource?.adminAction && resource.adminAction !== 'none');
            const actionPath = actionResource?.actionPath || connectionActionPath(row.storeId);
            return (
              <article className="store-sync-attention-store" key={row.storeId}>
                <div className="store-sync-store-heading">
                  <strong>{row.storeName}</strong>
                  <span>{row.platform || '-'}</span>
                </div>
                <div className="store-sync-attention-list">
                  {attention.map(([key, label]) => (
                    <div key={key} className="store-sync-resource-column attention">
                      <h3>{label}</h3>
                      <ResourceStatus resource={row.automaticReadStatus?.[key]} showOperatorMessage />
                    </div>
                  ))}
                </div>
                {isAdmin && actionResource?.adminAction === 'verify_and_recover' && actionResource.recoveryEligible ? (
                  <div className="store-sync-admin-action">
                    <button
                      className="button primary compact"
                      type="button"
                      onClick={() => recover(row)}
                      disabled={recoveringStoreId === String(row.storeId)}
                    >
                      {recoveringStoreId === String(row.storeId) ? '正在安排恢复...' : '验证并恢复读取'}
                    </button>
                  </div>
                ) : null}
                {isAdmin && actionResource?.adminAction === 'manual_review' ? (
                  <div className="store-sync-admin-action">
                    <Link className="button ghost compact" to={actionPath}>检查连接资料</Link>
                  </div>
                ) : null}
              </article>
            );
              })}
            </div>
          )}
          {Object.entries(feedback).filter(([, message]) => message).length ? (
            <div className="store-sync-feedback-list" aria-live="polite">
              {Object.entries(feedback).filter(([, message]) => message).map(([storeId, message]) => (
                <p key={storeId} className="inline-action-feedback">{message}</p>
              ))}
            </div>
          ) : null}
          <details className="store-sync-full-status">
            <summary>查看全部店铺状态</summary>
            <AllStoreStatus rows={visibleRows} adminStoreIds={adminStoreIds} />
          </details>
        </>
      )}
    </section>
  );
}
