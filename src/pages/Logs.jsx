import { useEffect, useMemo, useState } from 'react';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import InfoGrid from '../components/common/InfoGrid';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails, { redactTechnicalObject } from '../components/common/TechnicalDetails';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';

const mockModules = ['店铺管理', '商品管理', '订单管理', '客服管理', '销售数据', '设备管理', '邮箱管理', '申诉管理', '账号管理', '系统设置'];
const mockActions = ['新增', '编辑', '删除', '状态变更', '绑定', '解绑', '回复', '提交', '登录', '风险检测', '配置修改'];
const mockStatuses = ['成功', '失败', '待处理', '已忽略', '需复核'];
const mockRisks = ['低', '中', '高', '紧急'];
const mockOperators = ['系统管理员', 'Coupang 申诉处理账号', '韩国本土运营账号', '系统检测器'];

const auditModules = ['操作审计'];
const auditActions = ['本地运营操作', '审计日志只读验证', '本地审计写入验证', '数据库备份', '订单刷新写入'];
const auditStatuses = ['已完成', '失败，需要处理', '已阻断', '已计划', '已跳过', '已回滚'];
const auditRisks = ['低风险', '中风险', '高风险'];
const auditOperators = ['系统', '人工操作', '系统操作', '自动化任务', '验证测试'];

const statusLabels = {
  成功: '已完成',
  失败: '失败，需要处理',
  待处理: '等待处理',
  已忽略: '已忽略',
  需复核: '需要复核',
  success: '已完成',
  failed: '失败，需要处理',
  blocked: '已阻断',
  planned: '已计划',
};

const riskLabels = {
  低: '低风险',
  中: '中风险',
  高: '高风险',
  紧急: '紧急',
};

function readableStatus(value) {
  return statusLabels[value] || value || '待确认';
}

function readableRisk(value) {
  return riskLabels[value] || value || '待确认';
}

function actionNextStep(row) {
  if (row.nextStep) return row.nextStep;
  const risk = readableRisk(row.riskLevel);
  const status = readableStatus(row.status);
  if (risk === '紧急' || risk === '高风险') return '请管理员复核后再继续相关操作。';
  if (status.includes('失败') || status.includes('处理') || status.includes('复核') || status.includes('阻断')) return '请查看详情并确认处理人。';
  return '无需处理，保留记录备查。';
}

function recoveryEvidence(row) {
  if (row.recoveryEvidence) return row.recoveryEvidence;
  if (row.backupEvidence) return row.backupEvidence;
  const module = String(row.module || '');
  if (module.includes('系统设置') || module.includes('设备') || module.includes('账号')) return '可查看变更摘要';
  if (module.includes('商品') || module.includes('订单')) return '后续需关联备份记录';
  return '暂无恢复记录接入';
}

function buildAuditSummary({ rows = [], total = 0, syncTotal = 0, backendMode = false, auditSummary = null }) {
  const attentionCount = auditSummary?.needsAttentionCount ?? rows.filter((row) => {
    const risk = readableRisk(row.riskLevel);
    const status = readableStatus(row.status);
    return ['紧急', '高风险'].includes(risk) || status.includes('处理') || status.includes('复核') || status.includes('阻断');
  }).length;
  const backupEvidenceCount = auditSummary?.backupEvidenceCount ?? rows.filter((row) => String(row.backupEvidence || '').includes('已记录')).length;
  const restoreEvidenceCount = auditSummary?.restoreEvidenceCount ?? rows.filter((row) => String(row.recoveryEvidence || '').includes('恢复')).length;
  const auditTotal = auditSummary?.total ?? total;
  const auditMessage = backendMode
    ? (auditSummary?.businessMessage || (auditTotal ? '已显示安全操作审计记录。' : '当前还没有操作审计记录。'))
    : (total ? '当前显示演示操作记录。' : '当前没有演示操作记录。');

  return [
    {
      title: backendMode ? '操作审计' : '演示操作记录',
      status: `${auditTotal} 条`,
      tone: auditTotal ? 'info' : 'muted',
      message: auditMessage,
      next: backendMode ? '用于回答谁操作了什么、什么时候操作、结果如何。' : '演示数据不代表真实审计表。',
    },
    {
      title: '需要关注',
      status: `${attentionCount} 条`,
      tone: attentionCount ? 'warning' : 'success',
      message: attentionCount ? '当前存在失败、阻断或需要复核的记录。' : '当前没有高风险或待复核记录。',
      next: attentionCount ? '请优先查看处理建议。' : '保持记录备查即可。',
    },
    {
      title: '备份/恢复证据',
      status: `${backupEvidenceCount + restoreEvidenceCount} 条`,
      tone: backupEvidenceCount || restoreEvidenceCount ? 'info' : 'muted',
      message: backupEvidenceCount || restoreEvidenceCount ? '已有记录关联备份或恢复证据。' : '当前暂无备份或恢复证据接入。',
      next: '生产版会把关键写入、备份、恢复串起来。',
    },
    {
      title: '同步记录',
      status: backendMode ? `${syncTotal} 条` : '演示数据',
      tone: backendMode && syncTotal ? 'info' : 'muted',
      message: backendMode ? '同步类任务记录单独展示，不混入普通操作审计。' : 'mock 模式不读取后端同步记录。',
      next: '技术细节默认折叠，主页面只保留结果摘要。',
    },
  ];
}

function buildBackupSummary({ report = {}, summary = null }) {
  const backupCount = summary?.backupCount ?? report.backupCount ?? 0;
  const manifestCount = summary?.manifestCount ?? report.manifestCount ?? 0;
  const needsAttentionCount = summary?.needsAttentionCount ?? report.summary?.needs_attention_count ?? 0;
  const latestBackup = summary?.latestBackup || report.latestBackup || null;
  const allSafe = Boolean((summary?.allManifestsValid ?? report.allManifestsValid) && (summary?.allSensitiveScansPassed ?? report.allSensitiveScansPassed));

  return [
    {
      title: '本地备份',
      status: `${backupCount} 个`,
      tone: backupCount ? 'info' : 'muted',
      message: summary?.businessMessage || report.businessMessage || (backupCount ? '已读取本地备份报告。' : '当前还没有可读取的本地备份记录。'),
      next: '这里只展示备份证据，不提供恢复或删除操作。',
    },
    {
      title: '备份清单',
      status: `${manifestCount} 个`,
      tone: allSafe ? 'success' : (manifestCount ? 'warning' : 'muted'),
      message: allSafe ? '备份清单和安全检查通过。' : '存在需要管理员复核的备份清单或安全检查。',
      next: '恢复数据库仍需要单独审批和 dry-run。',
    },
    {
      title: '需要复核',
      status: `${needsAttentionCount} 个`,
      tone: needsAttentionCount ? 'warning' : 'success',
      message: needsAttentionCount ? '有备份记录需要检查。' : '当前备份报告没有复核项。',
      next: needsAttentionCount ? '请查看折叠详情中的安全状态。' : '保留备份证据即可。',
    },
    {
      title: '最近备份',
      status: latestBackup?.createdAt ? latestBackup.createdAt.slice(0, 10) : '暂无',
      tone: latestBackup ? 'info' : 'muted',
      message: latestBackup ? `${latestBackup.phase} · ${latestBackup.status}` : '尚无本地备份记录。',
      next: latestBackup ? latestBackup.nextStep : '后续写库或迁移前应先创建备份。',
    },
  ];
}

const auditColumns = [
  { key: 'time', title: '时间' },
  { key: 'objectName', title: '业务对象', render: (value, row) => <><strong>{value}</strong><br /><small>{row.module}</small></> },
  { key: 'actionType', title: '操作' },
  { key: 'operator', title: '操作人' },
  { key: 'status', title: '结果', render: (value) => <StatusBadge value={readableStatus(value)} /> },
  { key: 'riskLevel', title: '关注度', render: (value) => <StatusBadge value={readableRisk(value)} /> },
  { key: 'summary', title: '摘要' },
  { key: 'nextStep', title: '下一步', render: (_value, row) => actionNextStep(row) },
];

const syncColumns = [
  { key: 'startedAt', title: '开始时间' },
  { key: 'platform', title: '平台' },
  { key: 'type', title: '同步内容' },
  { key: 'message', title: '摘要' },
  { key: 'status', title: '结果', render: (value) => <StatusBadge value={readableStatus(value)} /> },
  { key: 'nextStep', title: '下一步', render: (_value, row) => (readableStatus(row.status).includes('失败') ? '请管理员查看高级详情。' : '无需处理，保留记录备查。') },
];

const backupColumns = [
  { key: 'createdAt', title: '创建时间' },
  { key: 'phase', title: '阶段' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'backupSizeLabel', title: '大小' },
  { key: 'evidence', title: '证据' },
  { key: 'retentionUntil', title: '保留到期' },
  { key: 'nextStep', title: '下一步' },
];

const initialQuery = {
  keyword: '',
  module: '',
  actionType: '',
  operator: '',
  status: '',
  riskLevel: '',
  startDate: '',
  endDate: '',
  page: 1,
  pageSize: 5,
};

export default function Logs() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const { versions } = useSyncRefresh();
  const [query, setQuery] = useState(initialQuery);
  const [draftQuery, setDraftQuery] = useState(initialQuery);
  const [result, setResult] = useState({ data: [], total: 0 });
  const [auditSummary, setAuditSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [auditError, setAuditError] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [syncRecords, setSyncRecords] = useState({ data: [], total: 0 });
  const [syncLoading, setSyncLoading] = useState(isBackendSource);
  const [syncError, setSyncError] = useState('');
  const [backupReport, setBackupReport] = useState({ items: [], backupCount: 0, manifestCount: 0 });
  const [backupSummary, setBackupSummary] = useState(null);
  const [backupLoading, setBackupLoading] = useState(isBackendSource);
  const [backupError, setBackupError] = useState('');

  const options = useMemo(() => ({
    modules: isBackendSource ? auditModules : mockModules,
    actions: isBackendSource ? auditActions : mockActions,
    statuses: isBackendSource ? auditStatuses : mockStatuses,
    risks: isBackendSource ? auditRisks : mockRisks,
    operators: isBackendSource ? auditOperators : mockOperators,
  }), []);

  const loadAuditRecords = async (nextQuery = query) => {
    if (isBackendSource && storeLoading) return;
    setLoading(true);
    setAuditError('');
    try {
      if (storeError) throw new Error(storeError);
      if (isBackendSource && !selectedStoreId) {
        setResult({ data: [], total: 0, businessMessage: '请选择店铺后查看操作审计。' });
        setAuditSummary({ total: 0, needsAttentionCount: 0, backupEvidenceCount: 0, restoreEvidenceCount: 0, businessMessage: '请选择店铺后查看操作审计。' });
        return;
      }
      const params = { ...nextQuery, storeId: selectedStoreId };
      const [nextResult, nextSummary] = await Promise.all([
        dataProvider.getOperationAuditLogs(params),
        dataProvider.getOperationAuditLogSummary(params),
      ]);
      setResult(nextResult);
      setAuditSummary(nextSummary);
    } catch (error) {
      setResult({ data: [], total: 0 });
      setAuditSummary(null);
      setAuditError(error?.detail?.business_message || error.message || '操作审计暂时无法加载，请稍后重试或联系管理员。');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditRecords(query);
  }, [query, selectedStoreId, storeLoading, storeError]);

  const loadSyncRecords = async () => {
    if (!isBackendSource) return;
    if (storeLoading) return;
    setSyncLoading(true);
    setSyncError('');
    try {
      if (storeError) throw new Error(storeError);
      if (!selectedStoreId) {
        setSyncRecords({ data: [], total: 0 });
        return;
      }
      setSyncRecords(await dataProvider.getSyncLogs({ storeId: selectedStoreId, page: 1, pageSize: 10 }));
    } catch (error) {
      setSyncRecords({ data: [], total: 0 });
      setSyncError(error.message || '同步记录加载失败。');
    } finally {
      setSyncLoading(false);
    }
  };

  useEffect(() => {
    loadSyncRecords();
  }, [selectedStoreId, storeLoading, storeError, versions.syncLogs]);

  const loadBackupReport = async () => {
    if (!isBackendSource) return;
    setBackupLoading(true);
    setBackupError('');
    try {
      const [nextReport, nextSummary] = await Promise.all([
        dataProvider.getBackupLocalReport({ limit: 20 }),
        dataProvider.getBackupLocalReportSummary({ limit: 20 }),
      ]);
      setBackupReport(nextReport);
      setBackupSummary(nextSummary);
    } catch (error) {
      setBackupReport({ items: [], backupCount: 0, manifestCount: 0 });
      setBackupSummary(null);
      setBackupError(error?.detail?.business_message || error.message || '本地备份报告加载失败，请稍后重试。');
    } finally {
      setBackupLoading(false);
    }
  };

  useEffect(() => {
    loadBackupReport();
  }, []);

  const refreshAll = async () => {
    await Promise.all([loadAuditRecords(query), loadSyncRecords(), loadBackupReport()]);
  };

  const openDetail = async (row) => {
    if (isBackendSource) {
      setDetail(row);
    } else {
      setDetail(await mockApi.getOperationLogDetail(row.id));
    }
    setDetailOpen(true);
  };

  const markRisk = async (row) => {
    if (isBackendSource) return;
    await mockApi.markLogRisk(row.id, { riskLevel: '紧急', status: '需复核', riskNote: '人工标记为重点风险日志。' });
    if (detail?.id === row.id) setDetail(await mockApi.getOperationLogDetail(row.id));
    await loadAuditRecords(query);
  };

  const summaryCards = buildAuditSummary({
    rows: result.data || [],
    total: result.total || 0,
    syncTotal: syncRecords.total || 0,
    backendMode: isBackendSource,
    auditSummary,
  });
  const backupCards = buildBackupSummary({ report: backupReport, summary: backupSummary });

  const businessEmptyMessage = result.businessMessage || auditSummary?.businessMessage || (isBackendSource
    ? '当前还没有操作审计记录。后续受控写入、备份、恢复等操作接入后，会在这里显示谁操作了什么、什么时候操作、结果如何。'
    : '当前没有可展示的演示操作记录。');

  return (
    <>
      <PageHeader
        title="高级日志与审计"
        description="用可读方式查看操作审计、同步记录和恢复证据。普通运营页面不展示这些技术细节。"
        actions={isBackendSource ? <button className="button ghost" onClick={refreshAll}>刷新只读记录</button> : null}
      />

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>审计可读性摘要</h2>
            <p>先看业务结果和下一步；内部编号、原始变更和诊断字段默认折叠。</p>
          </div>
          <span className="period-chip">管理员视图</span>
        </div>
        <div className="business-capability-grid compact">
          {summaryCards.map((card) => (
            <article className={`business-capability-card ${card.tone}`} key={card.title}>
              <div className="business-capability-head">
                <strong>{card.title}</strong>
                <span>{card.status}</span>
              </div>
              <p>{card.message}</p>
              <small>{card.next}</small>
            </article>
          ))}
        </div>
      </section>

      {isBackendSource && (
        <section className="content-card">
          <div className="card-title">
            <div>
              <h2>本地备份报告</h2>
              <p>展示本机备份清单、安全检查和最近备份证据；恢复、删除和清理操作仍需单独审批。</p>
            </div>
            <span className="period-chip">只读</span>
          </div>
          <div className="business-capability-grid compact">
            {backupCards.map((card) => (
              <article className={`business-capability-card ${card.tone}`} key={card.title}>
                <div className="business-capability-head">
                  <strong>{card.title}</strong>
                  <span>{card.status}</span>
                </div>
                <p>{card.message}</p>
                <small>{card.next}</small>
              </article>
            ))}
          </div>
          {backupError ? <EmptyState title="备份报告加载失败" description={backupError} /> : null}
          {!backupError && !backupLoading && !(backupReport.items || []).length ? (
            <EmptyState title="当前还没有本地备份记录" description="创建受控备份后，这里会显示备份清单和安全检查结果。" />
          ) : null}
          <DataTable columns={backupColumns} rows={backupReport.items || []} loading={backupLoading} />
          <TechnicalDetails
            title="查看备份报告诊断"
            description="这里只保留只读接口、安全计数和最近备份的安全摘要，不提供恢复或删除入口。"
            items={[
              { label: 'backup_report_route', value: 'GET /api/v1/backups/local-report' },
              { label: 'backup_report_summary_route', value: 'GET /api/v1/backups/local-report/summary' },
              { label: 'backup_count', value: backupSummary?.backupCount ?? backupReport.backupCount ?? 0 },
              { label: 'manifest_count', value: backupSummary?.manifestCount ?? backupReport.manifestCount ?? 0 },
              { label: 'needs_attention_count', value: backupSummary?.needsAttentionCount ?? 0 },
              { label: 'all_manifests_valid', value: backupSummary?.allManifestsValid ?? backupReport.allManifestsValid },
              { label: 'all_sensitive_scans_passed', value: backupSummary?.allSensitiveScansPassed ?? backupReport.allSensitiveScansPassed },
              { label: 'backup_deleted', value: backupReport.backupDeleted },
              { label: 'real_restore_executed', value: backupReport.realRestoreExecuted },
              { label: 'production_db_touched', value: backupReport.productionDbTouched },
              { label: 'rows_written', value: backupReport.rowsWritten },
              { label: 'latest_backup', value: backupSummary?.latestBackup?.advancedDetails || backupReport.latestBackup?.advancedDetails || {} },
            ]}
          />
        </section>
      )}

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            setDraftQuery(initialQuery);
            setQuery(initialQuery);
          }}
          placeholder={isBackendSource ? '搜索操作对象、操作人、摘要或下一步' : '搜索日志编号、模块、对象或摘要'}
        >
          <select value={draftQuery.module} onChange={(event) => setDraftQuery({ ...draftQuery, module: event.target.value })}>
            <option value="">全部模块</option>
            {options.modules.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.actionType} onChange={(event) => setDraftQuery({ ...draftQuery, actionType: event.target.value })}>
            <option value="">全部操作类型</option>
            {options.actions.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.operator} onChange={(event) => setDraftQuery({ ...draftQuery, operator: event.target.value })}>
            <option value="">全部操作人</option>
            {options.operators.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {options.statuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.riskLevel} onChange={(event) => setDraftQuery({ ...draftQuery, riskLevel: event.target.value })}>
            <option value="">全部关注度</option>
            {options.risks.map((item) => <option key={item}>{item}</option>)}
          </select>
          <input type="date" value={draftQuery.startDate} onChange={(event) => setDraftQuery({ ...draftQuery, startDate: event.target.value })} />
          <input type="date" value={draftQuery.endDate} onChange={(event) => setDraftQuery({ ...draftQuery, endDate: event.target.value })} />
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>{isBackendSource ? '操作审计' : '演示操作记录'}</h2>
            <p>{isBackendSource ? '读取 Codex1 本地审计表的安全摘要，不显示原始 JSON、完整哈希或平台敏感编号。' : 'mock 模式下展示演示操作记录，不代表真实审计表。'}</p>
          </div>
          <span className="period-chip">共 {result.total || 0} 条</span>
        </div>
        {auditError ? <EmptyState title="操作审计加载失败" description={auditError} /> : null}
        {!auditError && !loading && !(result.data || []).length ? <EmptyState title={isBackendSource ? '当前还没有操作审计记录' : '暂无演示操作记录'} description={businessEmptyMessage} /> : null}
        <DataTable
          columns={auditColumns}
          rows={result.data || []}
          loading={loading}
          renderActions={(row) => (
            <>
              <button onClick={() => openDetail(row)}>详情</button>
              {!isBackendSource && <button onClick={() => markRisk(row)}>风险标记</button>}
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total || 0} onChange={(page) => setQuery({ ...query, page })} />
        {isBackendSource && (
          <TechnicalDetails
            title="查看审计 API 诊断"
            description="这里只显示只读接口、安全计数和页面状态，具体审计行诊断在详情中折叠展示。"
            items={[
              { label: 'audit_api_list_route', value: 'GET /api/v1/operation-audit-logs' },
              { label: 'audit_api_summary_route', value: 'GET /api/v1/operation-audit-logs/summary' },
              { label: 'public_endpoint_enabled', value: result.publicEndpointEnabled },
              { label: 'readonly_local_route', value: result.readonlyLocalRoute },
              { label: 'audit_runtime_status', value: auditSummary?.runtimeStatus || result.auditRuntimeStatus || '-' },
              { label: 'audit_total', value: auditSummary?.total ?? result.total ?? 0 },
            ]}
          />
        )}
      </section>

      {isBackendSource && (
        <section className="content-card">
          <div className="card-title">
            <div>
              <h2>同步记录</h2>
              <p>展示同步类任务的业务摘要；内部编号和技术统计默认折叠。</p>
            </div>
            <span className="period-chip">共 {syncRecords.total} 条</span>
          </div>
          {syncError ? <EmptyState title="同步记录加载失败" description={syncError} /> : <DataTable columns={syncColumns} rows={syncRecords.data || []} loading={syncLoading} />}
          <TechnicalDetails
            description="这里保留同步记录的管理员诊断字段，不放到普通运营页面。"
            items={[
              { label: 'selected_store_id', value: selectedStoreId || '-' },
              { label: 'sync_record_total', value: syncRecords.total },
              { label: 'administrator_view', value: true },
            ]}
          />
        </section>
      )}

      <DetailModal open={detailOpen} title={detail ? `${isBackendSource ? '操作审计详情' : '操作记录详情'} · ${detail.objectName}` : '操作记录详情'} onClose={() => setDetailOpen(false)} width="min(980px, 94vw)">
        {detail ? (
          <>
            <section className="detail-section">
              <h3>发生了什么</h3>
              <InfoGrid items={[
                { label: '操作时间', value: detail.time },
                { label: '业务对象', value: detail.objectName },
                { label: '所属模块', value: detail.module },
                { label: '操作', value: detail.actionType },
                { label: '操作人', value: detail.operator },
                { label: '结果', value: <StatusBadge value={readableStatus(detail.status)} /> },
                { label: '关注度', value: <StatusBadge value={readableRisk(detail.riskLevel)} /> },
              ]} />
            </section>
            <section className="detail-section">
              <h3>处理建议</h3>
              <InfoGrid items={[
                { label: '下一步', value: actionNextStep(detail) },
                { label: '备份/恢复证据', value: recoveryEvidence(detail) },
                { label: '安全边界', value: detail.safetyLabel || '未返回敏感原文' },
              ]} />
            </section>
            <section className="detail-section">
              <h3>风险说明</h3>
              <p>{detail.riskNote || detail.reasonLabel || '暂无风险说明'}</p>
            </section>
            <section className="detail-section">
              <h3>备注</h3>
              <p>{detail.remarks || detail.summary || '暂无备注'}</p>
            </section>
            <TechnicalDetails
              title="查看高级详情"
              description="内部编号、来源、设备、IP 与安全诊断只在管理员详情中保留，默认折叠。"
              items={[
                { label: 'audit_id', value: detail.auditId },
                { label: 'source', value: detail.source },
                { label: 'audit_runtime_source', value: detail.auditRuntimeSource },
                { label: 'raw_status', value: detail.rawStatus || detail.status },
                { label: 'changed_fields', value: detail.changedFields || [] },
                { label: 'advanced_details', value: detail.advancedDetails || {} },
                { label: 'log_no', value: detail.logNo },
                { label: 'ip_address', value: detail.ipAddress },
                { label: 'device', value: detail.device },
              ]}
            >
              {!isBackendSource && (
                <>
                  <section className="detail-section">
                    <h3>操作前数据</h3>
                    <pre>{JSON.stringify(redactTechnicalObject(detail.beforeData), null, 2)}</pre>
                  </section>
                  <section className="detail-section">
                    <h3>操作后数据</h3>
                    <pre>{JSON.stringify(redactTechnicalObject(detail.afterData), null, 2)}</pre>
                  </section>
                </>
              )}
            </TechnicalDetails>
          </>
        ) : <EmptyState title="暂无日志详情" description="请选择一条日志记录查看完整内容。" />}
      </DetailModal>
    </>
  );
}
