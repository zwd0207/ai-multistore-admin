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
const MAX_RECOVERY_POLLS = 8;
const RECOVERY_POLL_DELAY_MS = 1000;

function connectionActionPath(storeId) {
  return `/stores?storeId=${encodeURIComponent(storeId)}&focus=connection`;
}

function ResourceStatus({ resource, showOperatorMessage }) {
  const unavailable = resource?.safeFailureReason === 'not_supported';
  const label = unavailable ? (resource.safeFailureLabel || '暂未接入自动读取') : storeSyncStatusLabel(resource?.status);
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

export default function StoreSyncStatusPanel({ rows = [], attentionSummary = {}, canManageRecovery = () => false }) {
  const [visibleRows, setVisibleRows] = useState(rows);
  const [recoveringStoreId, setRecoveringStoreId] = useState('');
  const [feedback, setFeedback] = useState({});

  useEffect(() => setVisibleRows(rows), [rows]);

  const adminStoreIds = useMemo(
    () => new Set(visibleRows.filter((row) => canManageRecovery(row.storeId)).map((row) => String(row.storeId))),
    [visibleRows, canManageRecovery],
  );

  const pollStoreOverview = async (storeId) => {
    for (let attempt = 0; attempt < MAX_RECOVERY_POLLS; attempt += 1) {
      try {
        const overview = await dataProvider.getStoreOverview({ includeInactive: false });
        const nextRow = (overview?.stores || []).find((item) => String(item.storeId) === String(storeId));
        if (!nextRow) return;
        setVisibleRows((current) => updateRow(current, nextRow));
        const attention = attentionResources(nextRow);
        const reblocked = attention.some(([key]) => nextRow.automaticReadStatus?.[key]?.attentionState === 'admin_action');
        if (!attention.length || reblocked || attempt === MAX_RECOVERY_POLLS - 1) return;
      } catch {
        return;
      }
      await waitForPoll();
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
            {attentionSummary.affectedStoreCount ? `（${attentionSummary.affectedStoreCount} 个店铺需关注）` : ''}
          </h2>
          <p>
            {attentionSummary.affectedResourceCount
              ? `有 ${attentionSummary.affectedResourceCount} 个资源需要关注，按店铺查看订单、客服、商品和物流的自动读取状态。`
              : '按店铺查看订单、客服、商品和物流的自动读取状态。'}
          </p>
        </div>
      </div>
      {!visibleRows.length ? (
        <p className="store-sync-empty">暂无店铺同步状态。</p>
      ) : (
        <div className="store-sync-list">
          {visibleRows.map((row) => {
            const attention = attentionResources(row);
            const isAdmin = adminStoreIds.has(String(row.storeId));
            const actionResource = attention
              .map(([key]) => row.automaticReadStatus?.[key])
              .find((resource) => resource?.adminAction && resource.adminAction !== 'none');
            const actionPath = actionResource?.actionPath || connectionActionPath(row.storeId);
            return (
              <article className="store-sync-store" key={row.storeId}>
                <div className="store-sync-store-heading">
                  <strong>{row.storeName}</strong>
                  <span>{row.platform || '-'}</span>
                </div>
                {!attention.length ? (
                  <>
                    <p className="store-sync-healthy-line">自动读取状态正常</p>
                    <details className="store-sync-full-status">
                      <summary>查看完整状态</summary>
                      <div className="store-sync-resource-grid">
                        {RESOURCE_ROWS.map(([key, label]) => (
                          <div key={key} className="store-sync-resource-column">
                            <h3>{label}</h3>
                            <ResourceStatus resource={row.automaticReadStatus?.[key]} showOperatorMessage={isAdmin} />
                          </div>
                        ))}
                      </div>
                    </details>
                  </>
                ) : (
                  <>
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
                    <details className="store-sync-full-status">
                      <summary>查看完整状态（含正常资源）</summary>
                      <div className="store-sync-resource-grid">
                        {RESOURCE_ROWS.map(([key, label]) => (
                          <div key={key} className="store-sync-resource-column">
                            <h3>{label}</h3>
                            <ResourceStatus resource={row.automaticReadStatus?.[key]} showOperatorMessage={isAdmin} />
                          </div>
                        ))}
                      </div>
                    </details>
                  </>
                )}
                {feedback[row.storeId] ? <p className="inline-action-feedback">{feedback[row.storeId]}</p> : null}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
