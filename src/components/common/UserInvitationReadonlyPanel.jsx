import { useEffect, useMemo, useState } from 'react';
import TechnicalDetails from './TechnicalDetails';
import { useStoreContext } from '../../context/StoreContext';
import dataProvider from '../../services/dataProvider';

const TARGET_USER_HASH = 'user-hash-22222222bbbbbbbb';
const TARGET_LOGIN_HASH = 'login-hash-22222222bbbbbbbb';
const TARGET_LOGIN_MASKED = 'op***-invite';
const TARGET_ROLE = 'operator';

function statusTone(result) {
  if (!result) return 'muted';
  if (result.status === 'user_invitation_mock_ready') return 'success';
  if (result.skipReason === 'target_user_already_exists') return 'info';
  return 'warning';
}

function statusLabel(result) {
  if (!result) return '待检查';
  if (result.status === 'user_invitation_mock_ready') return '可进入后续审批';
  if (result.skipReason === 'target_user_already_exists') return '无需重复邀请';
  if (result.skipReason === 'login_identifier_must_be_masked') return '登录标识需脱敏';
  if (result.skipReason === 'manual_approval_required') return '需要管理员批准';
  return '需要管理员复核';
}

function nextActionText(result) {
  if (!result) return '正在读取用户邀请只读检查结果。';
  if (result.status === 'user_invitation_mock_ready') {
    return '可以规划后续真实用户邀请阶段，但当前页面不会创建用户、发送邀请或分配店铺成员。';
  }
  if (result.skipReason === 'target_user_already_exists') {
    return '目标用户已存在，不需要重复创建邀请；如需店铺权限，请走成员分配审批。';
  }
  if (result.skipReason === 'login_identifier_must_be_masked') {
    return '请只展示脱敏后的登录标识，不要在页面、日志或测试截图中放完整邮箱或手机号。';
  }
  return '请管理员查看折叠详情中的阻断原因；当前不进入真实邀请或写入阶段。';
}

export default function UserInvitationReadonlyPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [state, setState] = useState({ loading: false, result: null, error: '' });
  const storeId = Number(selectedStoreId || selectedStore?.id || 8);

  const requestPayload = useMemo(() => ({
    actorContext: { actor_id: 'local-admin', role: 'admin', store_ids: [storeId] },
    targetUserKeyHash: TARGET_USER_HASH,
    loginIdentifierHash: TARGET_LOGIN_HASH,
    loginIdentifierMasked: TARGET_LOGIN_MASKED,
    targetStoreIds: [storeId],
    targetRole: TARGET_ROLE,
    manualApproval: true,
    invitationReason: 'user invitation readonly UI check',
    backupEvidencePlanned: true,
    auditEvidencePlanned: true,
    membershipAssignmentPlanReady: true,
    existingUserHashes: [],
  }), [storeId]);

  useEffect(() => {
    if (!storeId) return undefined;
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: '' }));
    dataProvider.checkUserInvitationReadonly(requestPayload)
      .then((result) => {
        if (!cancelled) setState({ loading: false, result, error: '' });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            loading: false,
            result: null,
            error: error?.message || '用户邀请只读检查暂时无法加载。',
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
          <h2>用户邀请只读检查</h2>
          <p>这里只检查后续邀请新运营用户的准备条件，不会创建用户、发送邀请或分配店铺成员。</p>
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
          <p>{result?.businessMessage || '正在读取用户邀请只读检查结果。'}</p>
          <small>{nextActionText(result)}</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>真实邀请</strong>
            <span>未开放</span>
          </div>
          <p>当前不会发送邀请、不会创建登录会话，也不会写入真实成员关系。</p>
          <small>真实邀请必须另开阶段，并先确认备份、权限、审计和回读校验。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>目标店铺</strong>
            <span>{selectedStore?.name || `店铺 ${storeId}`}</span>
          </div>
          <p>本检查只针对当前选中店铺，不会跨店铺自动授权。</p>
          <small>多店铺生产邀请仍需要正式登录、角色、成员关系和审计链落地。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>登录标识</strong>
            <span>已脱敏</span>
          </div>
          <p>页面只展示脱敏后的登录标识，不展示完整邮箱或手机号。</p>
          <small>完整登录标识、密码、token、签名和请求头不会展示。</small>
        </article>
      </div>
      <TechnicalDetails
        title="查看用户邀请检查技术详情"
        description="这里保留只读门禁状态和安全标记；普通运营只需要看上方业务结论。"
        items={[
          { label: 'phase', value: result?.phase || 'ERP-Multistore-1T' },
          { label: 'status', value: result?.status },
          { label: 'skip_reason', value: result?.skipReason },
          { label: 'target_store_ids', value: result?.targetStoreIds?.join(', ') || String(storeId) },
          { label: 'target_role', value: result?.targetRole || TARGET_ROLE },
          { label: 'target_user_hash', value: result?.targetUserKeyHash || TARGET_USER_HASH },
          { label: 'login_identifier_hash', value: result?.loginIdentifierHash || TARGET_LOGIN_HASH },
          { label: 'login_identifier_masked', value: result?.loginIdentifierMasked || TARGET_LOGIN_MASKED },
          { label: 'manual_approval', value: result?.manualApproval },
          { label: 'backup_evidence_planned', value: result?.backupEvidencePlanned },
          { label: 'audit_evidence_planned', value: result?.auditEvidencePlanned },
          { label: 'membership_assignment_plan_ready', value: result?.membershipAssignmentPlanReady },
          { label: 'invitation_would_create_user', value: result?.invitationWouldCreateUser },
          { label: 'invitation_would_send', value: result?.invitationWouldSend },
          { label: 'invitation_sent', value: result?.invitationSent ?? false },
          { label: 'users_written', value: result?.usersWritten ?? false },
          { label: 'membership_written', value: result?.membershipWritten ?? false },
          { label: 'role_assignment_written', value: result?.roleAssignmentWritten ?? false },
          { label: 'operation_audit_rows_written', value: result?.operationAuditRowsWritten ?? false },
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
