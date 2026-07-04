import { useEffect, useMemo, useState } from 'react';
import TechnicalDetails from './TechnicalDetails';
import { useStoreContext } from '../../context/StoreContext';
import dataProvider from '../../services/dataProvider';

const TARGET_USER_HASH = 'user-hash-11111111aaaaaaaa';
const TARGET_ROLE = 'operator';

function statusTone(result) {
  if (!result) return 'muted';
  if (result.status === 'membership_assignment_runtime_mock_ready') return 'success';
  if (result.skipReason === 'duplicate_active_membership') return 'info';
  return 'warning';
}

function statusLabel(result) {
  if (!result) return '待检查';
  if (result.status === 'membership_assignment_runtime_mock_ready') return '可进入后续审批';
  if (result.skipReason === 'target_user_not_found') return '目标用户待创建';
  if (result.skipReason === 'duplicate_active_membership') return '无需重复分配';
  return '需管理员复核';
}

function nextActionText(result) {
  if (!result) return '正在读取本地只读检查结果。';
  if (result.status === 'membership_assignment_runtime_mock_ready') {
    return '可以规划后续真实成员分配阶段，但当前页面不会创建用户或成员关系。';
  }
  if (result.skipReason === 'target_user_not_found') {
    return '需要先完成受控用户创建或邀请阶段，再重新做店铺成员分配检查。';
  }
  if (result.skipReason === 'duplicate_active_membership') {
    return '当前已有相同店铺角色，运营上不需要再次分配。';
  }
  return '请管理员查看折叠详情中的阻断原因，当前不进入写入阶段。';
}

export default function StoreMembershipReadonlyPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [state, setState] = useState({ loading: false, result: null, error: '' });
  const storeId = Number(selectedStoreId || selectedStore?.id || 8);

  const requestPayload = useMemo(() => ({
    actorContext: { actor_id: 'local-admin', role: 'admin', store_ids: [storeId] },
    targetUserKeyHash: TARGET_USER_HASH,
    targetStoreId: storeId,
    targetRole: TARGET_ROLE,
    manualApproval: true,
    assignmentReason: 'store membership readonly UI check',
  }), [storeId]);

  useEffect(() => {
    if (!storeId) return undefined;
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: '' }));
    dataProvider.checkStoreMembershipReadonly(requestPayload)
      .then((result) => {
        if (!cancelled) setState({ loading: false, result, error: '' });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            loading: false,
            result: null,
            error: error?.message || '店铺成员只读检查暂时无法加载。',
          });
        }
      });
    return () => { cancelled = true; };
  }, [requestPayload, storeId]);

  const { loading, result, error } = state;
  const tone = statusTone(result);

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>店铺成员权限检查</h2>
          <p>这里仅检查某个用户是否具备后续分配到当前店铺的条件，不会创建用户、登录会话或店铺成员关系。</p>
        </div>
        <span className="period-chip">{loading ? '检查中' : '只读检查'}</span>
      </div>
      {error ? <div className="mock-sync-error">{error}</div> : null}
      <div className="business-capability-grid compact">
        <article className={`business-capability-card ${tone}`}>
          <div className="business-capability-head">
            <strong>检查结果</strong>
            <span>{statusLabel(result)}</span>
          </div>
          <p>{result?.businessMessage || '正在读取店铺成员只读检查结果。'}</p>
          <small>{nextActionText(result)}</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>真实写入</strong>
            <span>未开放</span>
          </div>
          <p>当前不会新增用户、不会分配角色、不会写入店铺成员关系。</p>
          <small>真实成员分配必须另开阶段，并先完成用户、审批、备份和审计边界确认。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>店铺范围</strong>
            <span>{selectedStore?.name || `店铺 ${storeId}`}</span>
          </div>
          <p>只检查当前选中店铺的成员分配条件，不跨店铺自动授权。</p>
          <small>大规模多店铺生产运营仍需要正式登录和成员关系落地后才能开放。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>正式权限系统</strong>
            <span>待落地</span>
          </div>
          <p>角色和成员检查已可展示，但还不是生产登录权限系统。</p>
          <small>用户创建、登录会话、路由鉴权和真实成员分配仍保持关闭。</small>
        </article>
      </div>
      <TechnicalDetails
        title="查看店铺成员检查技术详情"
        description="这里保留只读门禁状态和安全标记，普通运营只需要看上方业务结论。"
        items={[
          { label: 'phase', value: result?.phase || 'ERP-Multistore-1J' },
          { label: 'status', value: result?.status },
          { label: 'skip_reason', value: result?.skipReason },
          { label: 'target_store_id', value: result?.targetStoreId || storeId },
          { label: 'target_role', value: result?.targetRole || TARGET_ROLE },
          { label: 'target_user_hash', value: result?.targetUserKeyHash || TARGET_USER_HASH },
          { label: 'target_user_exists', value: result?.targetUserExists },
          { label: 'target_role_exists', value: result?.targetRoleExists },
          { label: 'duplicate_active_membership', value: result?.duplicateActiveMembership },
          { label: 'membership_would_create', value: result?.membershipWouldCreate },
          { label: 'membership_written', value: result?.membershipWritten ?? false },
          { label: 'real_auth_session_created', value: result?.realAuthSessionCreated ?? false },
          { label: 'real_database_written', value: result?.realDatabaseWritten ?? false },
          { label: 'orders_written', value: result?.ordersWritten ?? false },
          { label: 'products_written', value: result?.productsWritten ?? false },
          { label: 'sync_log_written', value: result?.syncLogWritten ?? false },
          { label: 'tested_success_written', value: result?.capabilityTestedSuccessWritten ?? false },
          { label: 'raw_response_saved', value: result?.rawResponseSaved ?? false },
          { label: 'formal_sync_open', value: result?.formalSyncOpen ?? false },
          { label: 'platform_writes_enabled', value: result?.platformWritesEnabled ?? false },
        ]}
      />
    </section>
  );
}
