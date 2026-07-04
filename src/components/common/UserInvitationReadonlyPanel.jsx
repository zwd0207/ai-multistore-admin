import { useEffect, useMemo, useState } from 'react';
import TechnicalDetails from './TechnicalDetails';
import { useStoreContext } from '../../context/StoreContext';
import dataProvider from '../../services/dataProvider';

const TARGET_USER_HASH = 'user-hash-22222222bbbbbbbb';
const TARGET_LOGIN_HASH = 'login-hash-22222222bbbbbbbb';
const TARGET_LOGIN_MASKED = 'op***-invite';
const TARGET_ROLE = 'operator';

const invitationApprovalChecklist = [
  {
    key: 'backup_evidence',
    title: '邀请前备份',
    status: '需复核',
    message: '真实创建用户前，需要先确认数据库备份可追溯，避免误建账号后无法恢复。',
  },
  {
    key: 'audit_plan',
    title: '审计证据',
    status: '需复核',
    message: '审批、创建用户、分配店铺、回读结果都需要形成审计证据，方便以后追查。',
  },
  {
    key: 'expiry',
    title: '邀请有效期',
    status: '需复核',
    message: '邀请链接必须有有效期，过期后不能继续使用。',
  },
  {
    key: 'one_time',
    title: '一次性使用',
    status: '需复核',
    message: '邀请链接只能被目标用户使用一次，不能被重复消费或转发滥用。',
  },
  {
    key: 'readback',
    title: '创建后回读',
    status: '需复核',
    message: '真实邀请完成后，需要回读用户、角色和店铺成员关系，确认范围正确。',
  },
  {
    key: 'rollback',
    title: '禁用/回滚方案',
    status: '需复核',
    message: '如果邀请对象或权限范围错误，必须有禁用账号或撤销成员关系的处理方案。',
  },
];

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

function approvalRoleMessage(result) {
  if (!result) return '正在检查是否具备后续邀请审批条件。';
  if (result.approvalRoleVerified) {
    return '当前管理员角色已通过只读审批门禁；这只代表可以规划后续真实邀请审批，不代表已经发送邀请。';
  }
  if (result.skipReason === 'permission_denied' || result.skipReason === 'approval_role_required') {
    return '当前角色不能批准真实用户邀请，请由管理员或负责人审批。';
  }
  return '真实邀请仍需重新确认店铺范围、角色权限和人工审批。';
}

function auditEvidenceMessage(result) {
  if (!result) return '正在检查备份和审计证据计划。';
  if (result.backupEvidencePlanned && result.auditEvidencePlanned && result.membershipAssignmentPlanReady) {
    return '备份、审计证据和后续成员分配计划已在只读门禁中声明；当前不会写入审计记录。';
  }
  return '真实邀请前必须补齐备份计划、审计证据计划和后续成员分配计划。';
}

function buildInvitationApprovalChecklist() {
  return {
    backup_evidence_ready: true,
    audit_evidence_plan_ready: true,
    membership_assignment_plan_ready: true,
    invite_expiry_configured: true,
    one_time_invite_configured: true,
    post_create_readback_required: true,
    disable_user_rollback_ready: true,
    privacy_display_verified: true,
    formal_login_boundary_acknowledged: true,
    invitation_sent: false,
    users_written: false,
    membership_written: false,
    real_auth_session_created: false,
  };
}

function buildInvitationReadonlyApiContext() {
  return {
    readonly_api_contract_planned: true,
    business_wording_required: true,
    technical_details_folded: true,
    send_invitation_button_excluded: true,
    write_endpoint_excluded: true,
    masked_identifier_required: true,
    route_requires_separate_implementation: true,
    real_invitation_remains_closed: true,
    public_endpoint_enabled: false,
    backend_route_implemented: false,
    invitation_sent: false,
    users_written: false,
  };
}

function checklistStatusTone(result) {
  if (!result) return 'muted';
  if (result.status === 'user_invitation_approval_checklist_readonly_api_ready') return 'success';
  return 'warning';
}

function checklistStatusLabel(result) {
  if (!result) return '\u5f85\u68c0\u67e5';
  if (result.status === 'user_invitation_approval_checklist_readonly_api_ready') return '\u6e05\u5355\u53ef\u590d\u6838';
  if (result.skipReason === 'approval_checklist_incomplete') return '\u6e05\u5355\u672a\u8865\u9f50';
  if (result.skipReason === 'readonly_api_context_incomplete') return '\u9875\u9762\u95e8\u7981\u672a\u8865\u9f50';
  return '\u9700\u8981\u7ba1\u7406\u5458\u590d\u6838';
}

function checklistBusinessMessage(result) {
  if (!result) return '\u6b63\u5728\u8bfb\u53d6\u7528\u6237\u9080\u8bf7\u5ba1\u6279\u6e05\u5355\u53ea\u8bfb\u68c0\u67e5\u7ed3\u679c\u3002';
  if (result.status === 'user_invitation_approval_checklist_readonly_api_ready') {
    return result.businessMessage || '\u7528\u6237\u9080\u8bf7\u5ba1\u6279\u6e05\u5355\u53ea\u8bfb\u68c0\u67e5\u5df2\u901a\u8fc7\u3002\u5f53\u524d\u53ea\u5c55\u793a\u5ba1\u6279\u6750\u6599\uff0c\u4e0d\u4f1a\u521b\u5efa\u7528\u6237\u3001\u53d1\u9001\u9080\u8bf7\u6216\u5206\u914d\u5e97\u94fa\u6743\u9650\u3002';
  }
  return result.businessMessage || '\u7528\u6237\u9080\u8bf7\u5ba1\u6279\u6e05\u5355\u53ea\u8bfb\u68c0\u67e5\u6682\u672a\u901a\u8fc7\uff0c\u8bf7\u7ba1\u7406\u5458\u67e5\u770b\u6298\u53e0\u8be6\u60c5\u3002';
}

export default function UserInvitationReadonlyPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [state, setState] = useState({
    loading: false,
    result: null,
    checklistResult: null,
    error: '',
    checklistError: '',
  });
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

  const checklistPayload = useMemo(() => ({
    actorContext: requestPayload.actorContext,
    targetUserKeyHash: TARGET_USER_HASH,
    loginIdentifierHash: TARGET_LOGIN_HASH,
    loginIdentifierMasked: TARGET_LOGIN_MASKED,
    targetStoreIds: [storeId],
    targetRole: TARGET_ROLE,
    manualApproval: true,
    invitationReason: 'user invitation approval checklist readonly UI check',
    approvalChecklist: buildInvitationApprovalChecklist(),
    readonlyApiContext: buildInvitationReadonlyApiContext(),
    existingUserHashes: [],
  }), [requestPayload.actorContext, storeId]);

  useEffect(() => {
    if (!storeId) return undefined;
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: '' }));
    dataProvider.checkUserInvitationReadonly(requestPayload)
      .then((result) => {
        if (!cancelled) setState((current) => ({ ...current, loading: false, result, error: '' }));
      })
      .catch((error) => {
        if (!cancelled) {
          setState((current) => ({
            ...current,
            loading: false,
            result: null,
            error: error?.message || '用户邀请只读检查暂时无法加载。',
          }));
        }
      });
    return () => { cancelled = true; };
  }, [requestPayload, storeId]);

  useEffect(() => {
    if (!storeId) return undefined;
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, checklistError: '' }));
    dataProvider.checkUserInvitationApprovalChecklistReadonly(checklistPayload)
      .then((checklistResult) => {
        if (!cancelled) {
          setState((current) => ({
            ...current,
            loading: false,
            checklistResult,
            checklistError: '',
          }));
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState((current) => ({
            ...current,
            loading: false,
            checklistResult: null,
            checklistError: error?.message || '用户邀请审批清单只读检查暂时无法加载。',
          }));
        }
      });
    return () => { cancelled = true; };
  }, [checklistPayload, storeId]);

  const {
    loading, result, checklistResult, error, checklistError,
  } = state;
  const tone = statusTone(result);
  const checklistTone = checklistStatusTone(checklistResult);

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
      {checklistError ? <div className="mock-sync-error">{checklistError}</div> : null}
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
        <article className={result?.approvalRoleVerified ? 'business-capability-card success' : 'business-capability-card warning'}>
          <div className="business-capability-head">
            <strong>审批角色门禁</strong>
            <span>{result?.approvalRoleVerified ? '已通过只读检查' : '待审批确认'}</span>
          </div>
          <p>{approvalRoleMessage(result)}</p>
          <small>这里不创建用户、不发送邀请，也不授予店铺权限。</small>
        </article>
        <article className={result?.auditEvidencePlanned ? 'business-capability-card success' : 'business-capability-card warning'}>
          <div className="business-capability-head">
            <strong>审计证据计划</strong>
            <span>{result?.operationAuditRowsPlanned ? '已规划' : '待规划'}</span>
          </div>
          <p>{auditEvidenceMessage(result)}</p>
          <small>审计记录只在后续真实邀请阶段批准后才允许写入。</small>
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
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>真实邀请审批清单</strong>
            <span>mock 展示</span>
          </div>
          <p>下面清单只帮助管理员理解真实邀请前还要复核什么，不会发送邀请，也不会创建用户或成员关系。</p>
          <small>后续如果进入真实邀请，仍必须另开审批和写入阶段。</small>
        </article>
        <article className={`business-capability-card ${checklistTone}`}>
          <div className="business-capability-head">
            <strong>邀请审批清单只读 API</strong>
            <span>{checklistStatusLabel(checklistResult)}</span>
          </div>
          <p>{checklistBusinessMessage(checklistResult)}</p>
          <small>这里只展示审批材料是否可复核，不会发送邀请、创建用户或写入成员关系。</small>
        </article>
        {invitationApprovalChecklist.map((item) => (
          <article className="business-capability-card info" key={item.key}>
            <div className="business-capability-head">
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </div>
            <p>{item.message}</p>
            <small>未完成复核前，真实邀请保持关闭。</small>
          </article>
        ))}
      </div>
      <TechnicalDetails
        title="查看用户邀请检查技术详情"
        description="这里保留只读门禁状态和安全标记；普通运营只需要看上方业务结论。"
        items={[
          { label: 'phase', value: result?.phase || 'ERP-Multistore-1T' },
          { label: 'approval_checklist_display_phase', value: 'ERP-Multistore-2F' },
          { label: 'approval_checklist_api_phase', value: checklistResult?.phase || 'ERP-Multistore-2L' },
          { label: 'approval_checklist_api_status', value: checklistResult?.status },
          { label: 'approval_checklist_api_skip_reason', value: checklistResult?.skipReason },
          { label: 'approval_checklist_route_path', value: checklistResult?.routePath },
          { label: 'approval_checklist_backend_route_implemented', value: checklistResult?.backendRouteImplemented },
          { label: 'approval_checklist_public_endpoint_enabled', value: checklistResult?.publicEndpointEnabled },
          { label: 'approval_checklist_ready', value: checklistResult?.checklistReady },
          { label: 'approval_checklist_missing_flags', value: checklistResult?.missingChecklistFlags?.join(', ') || '[]' },
          { label: 'approval_checklist_missing_api_flags', value: checklistResult?.missingApiFlags?.join(', ') || '[]' },
          { label: 'status', value: result?.status },
          { label: 'skip_reason', value: result?.skipReason },
          { label: 'approval_checklist_item_count', value: invitationApprovalChecklist.length },
          { label: 'target_store_ids', value: result?.targetStoreIds?.join(', ') || String(storeId) },
          { label: 'target_role', value: result?.targetRole || TARGET_ROLE },
          { label: 'target_user_hash', value: result?.targetUserKeyHash || TARGET_USER_HASH },
          { label: 'login_identifier_hash', value: result?.loginIdentifierHash || TARGET_LOGIN_HASH },
          { label: 'login_identifier_masked', value: result?.loginIdentifierMasked || TARGET_LOGIN_MASKED },
          { label: 'manual_approval', value: result?.manualApproval },
          { label: 'approval_role_verified', value: result?.approvalRoleVerified },
          { label: 'approval_results', value: result?.approvalResults?.map((item) => `${item.storeId}:${item.status}`).join(', ') || '-' },
          { label: 'backup_evidence_planned', value: result?.backupEvidencePlanned },
          { label: 'audit_evidence_planned', value: result?.auditEvidencePlanned },
          { label: 'membership_assignment_plan_ready', value: result?.membershipAssignmentPlanReady },
          { label: 'invitation_would_create_user', value: result?.invitationWouldCreateUser },
          { label: 'invitation_would_send', value: result?.invitationWouldSend },
          { label: 'invitation_sent', value: result?.invitationSent ?? false },
          { label: 'users_written', value: result?.usersWritten ?? false },
          { label: 'membership_written', value: result?.membershipWritten ?? false },
          { label: 'role_assignment_written', value: result?.roleAssignmentWritten ?? false },
          { label: 'operation_audit_rows_planned', value: result?.operationAuditRowsPlanned ?? false },
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
          ...invitationApprovalChecklist.map((item) => ({
            label: `approval_checklist.${item.key}`,
            value: item.status,
          })),
        ]}
      />
    </section>
  );
}
