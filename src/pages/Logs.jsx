import { useEffect, useState } from 'react';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import InfoGrid from '../components/common/InfoGrid';
import MockSyncPanel from '../components/common/MockSyncPanel';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails, { redactTechnicalObject } from '../components/common/TechnicalDetails';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';

const modules = ['店铺管理', '商品管理', '订单管理', '客服管理', '销售数据', '设备管理', '邮箱管理', '申诉管理', '账号管理', '系统设置'];
const actionTypes = ['新增', '编辑', '删除', '状态变更', '绑定', '解绑', '回复', '提交', '登录', '风险检测', '配置修改'];
const statuses = ['成功', '失败', '待处理', '已忽略', '需复核'];
const riskLevels = ['低', '中', '高', '紧急'];
const operators = ['系统管理员', 'Coupang 申诉处理账号', '韩国本土运营账号', '系统检测器'];

const statusLabels = {
  成功: '已完成',
  失败: '失败，需要处理',
  待处理: '等待处理',
  已忽略: '已忽略',
  需复核: '需要复核',
  성공: '已完成',
  실패: '失败，需要处理',
  대기: '等待处理',
  위험: '需要处理',
  경고: '需要复核',
};

const riskLabels = {
  低: '低风险',
  中: '中风险',
  高: '高风险',
  紧急: '紧急',
  낮음: '低风险',
  보통: '中风险',
  높음: '高风险',
  긴급: '紧急',
};

function readableStatus(value) {
  return statusLabels[value] || value || '待确认';
}
function readableRisk(value) {
  return riskLabels[value] || value || '待确认';
}

function actionNextStep(row) {
  const risk = readableRisk(row.riskLevel);
  const status = readableStatus(row.status);
  if (risk === '紧急' || risk === '高风险') return '请管理员复核后再继续相关操作。';
  if (status.includes('失败') || status.includes('处理') || status.includes('复核')) return '请查看详情并确认处理人。';
  return '无需处理，保留记录备查。';
}

function recoveryEvidence(row) {
  const module = String(row.module || '');
  if (module.includes('系统设置') || module.includes('设备') || module.includes('账号')) return '可查看变更摘要';
  if (module.includes('商品') || module.includes('订单')) return '后续需关联备份记录';
  return '暂无恢复记录接入';
}

function buildAuditSummary({ rows = [], total = 0, syncTotal = 0, backendMode = false }) {
  const attentionCount = rows.filter((row) => ['紧急', '高风险'].includes(readableRisk(row.riskLevel)) || readableStatus(row.status).includes('处理') || readableStatus(row.status).includes('复核')).length;
  const writeLikeCount = rows.filter((row) => ['新增', '编辑', '删除', '状态变更', '绑定', '解绑', '配置修改'].includes(row.actionType)).length;
  return [
    {
      title: '操作记录',
      status: `${total} 条`,
      tone: total ? 'info' : 'muted',
      message: total ? '当前可查看本地操作、账号、商品、设备和设置变更记录。' : '当前没有可展示的操作记录。',
      next: '用于回答谁做了什么、什么时候做、结果如何。',
    },
    {
      title: '需要关注',
      status: `${attentionCount} 条`,
      tone: attentionCount ? 'warning' : 'success',
      message: attentionCount ? '当前页存在高风险或需要复核的记录。' : '当前页没有高风险或待复核记录。',
      next: attentionCount ? '请优先查看风险说明和处理建议。' : '保持记录备查即可。',
    },
    {
      title: '写入类操作',
      status: `${writeLikeCount} 条`,
      tone: writeLikeCount ? 'info' : 'muted',
      message: writeLikeCount ? '当前页包含配置、绑定、编辑或状态变更记录。' : '当前页暂无写入类操作。',
      next: '生产版后续会关联审批、备份和恢复证据。',
    },
    {
      title: '同步记录',
      status: backendMode ? `${syncTotal} 条` : '演示数据',
      tone: backendMode && syncTotal ? 'info' : 'muted',
      message: backendMode ? '同步类任务记录单独展示，不混入普通操作记录。' : 'mock 模式不读取后端同步记录。',
      next: '技术细节默认折叠，主页面只保留结果摘要。',
    },
  ];
}

const columns = [
  { key: 'time', title: '时间' },
  { key: 'objectName', title: '业务对象', render: (value, row) => <><strong>{value}</strong><br /><small>{row.module}</small></> },
  { key: 'actionType', title: '操作' },
  { key: 'operator', title: '操作人' },
  { key: 'status', title: '结果', render: (value) => <StatusBadge value={readableStatus(value)} /> },
  { key: 'riskLevel', title: '风险', render: (value) => <StatusBadge value={readableRisk(value)} /> },
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

export default function Logs() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const { versions } = useSyncRefresh();
  const [query, setQuery] = useState({ keyword: '', module: '', actionType: '', operator: '', status: '', riskLevel: '', startDate: '', endDate: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [syncRecords, setSyncRecords] = useState({ data: [], total: 0 });
  const [syncLoading, setSyncLoading] = useState(isBackendSource);
  const [syncError, setSyncError] = useState('');

  const load = async (nextQuery = query) => {
    setLoading(true);
    try {
      setResult(await mockApi.getOperationLogs(nextQuery));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query]);

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

  const openDetail = async (row) => {
    setDetail(await mockApi.getOperationLogDetail(row.id));
    setDetailOpen(true);
  };

  const markRisk = async (row) => {
    await mockApi.markLogRisk(row.id, { riskLevel: '紧急', status: '需复核', riskNote: '人工标记为重点风险日志。' });
    if (detail?.id === row.id) setDetail(await mockApi.getOperationLogDetail(row.id));
    await load();
  };

  const summaryCards = buildAuditSummary({
    rows: result.data || [],
    total: result.total || 0,
    syncTotal: syncRecords.total || 0,
    backendMode: isBackendSource,
  });

  return (
    <>
      <PageHeader
        title="高级日志与审计"
        description="用可读方式查看操作记录、同步记录和恢复证据。普通运营页面不展示这些技术细节。"
        actions={isBackendSource ? <button className="button ghost" onClick={loadSyncRecords}>刷新同步记录</button> : null}
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
              <h2>同步记录</h2>
              <p>展示同步类任务的业务摘要；内部编号和技术统计默认折叠。</p>
            </div>
            <span className="period-chip">共 {syncRecords.total} 条</span>
          </div>
          <MockSyncPanel onSynced={loadSyncRecords} />
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

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', module: '', actionType: '', operator: '', status: '', riskLevel: '', startDate: '', endDate: '', page: 1, pageSize: 5 };
            setDraftQuery(clean);
            setQuery(clean);
          }}
          placeholder="搜索日志编号、模块、对象或摘要"
        >
          <select value={draftQuery.module} onChange={(event) => setDraftQuery({ ...draftQuery, module: event.target.value })}>
            <option value="">全部模块</option>
            {modules.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.actionType} onChange={(event) => setDraftQuery({ ...draftQuery, actionType: event.target.value })}>
            <option value="">全部操作类型</option>
            {actionTypes.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.operator} onChange={(event) => setDraftQuery({ ...draftQuery, operator: event.target.value })}>
            <option value="">全部操作人</option>
            {operators.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {statuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.riskLevel} onChange={(event) => setDraftQuery({ ...draftQuery, riskLevel: event.target.value })}>
            <option value="">全部风险等级</option>
            {riskLevels.map((item) => <option key={item}>{item}</option>)}
          </select>
          <input type="date" value={draftQuery.startDate} onChange={(event) => setDraftQuery({ ...draftQuery, startDate: event.target.value })} />
          <input type="date" value={draftQuery.endDate} onChange={(event) => setDraftQuery({ ...draftQuery, endDate: event.target.value })} />
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>操作记录</h2>
            <p>按业务对象、操作人、结果、风险和下一步查看，不需要先理解内部编号。</p>
          </div>
          <span className="period-chip">共 {result.total} 条</span>
        </div>
        <DataTable
          columns={columns}
          rows={result.data}
          loading={loading}
          renderActions={(row) => (
            <>
              <button onClick={() => openDetail(row)}>详情</button>
              <button onClick={() => markRisk(row)}>风险标记</button>
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </section>

      <DetailModal open={detailOpen} title={detail ? `操作记录详情 · ${detail.objectName}` : '操作记录详情'} onClose={() => setDetailOpen(false)} width="min(980px, 94vw)">
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
                { label: '风险', value: <StatusBadge value={readableRisk(detail.riskLevel)} /> },
              ]} />
            </section>
            <section className="detail-section">
              <h3>处理建议</h3>
              <InfoGrid items={[
                { label: '下一步', value: actionNextStep(detail) },
                { label: '恢复证据', value: recoveryEvidence(detail) },
              ]} />
            </section>
            <section className="detail-section">
              <h3>风险说明</h3>
              <p>{detail.riskNote || '暂无风险说明'}</p>
            </section>
            <section className="detail-section">
              <h3>备注</h3>
              <p>{detail.remarks || '暂无备注'}</p>
            </section>
            <TechnicalDetails
              title="查看高级详情"
              description="内部编号、来源、设备、IP 与 JSON 变更摘要只在管理员详情中保留，默认折叠。"
              items={[
                { label: 'log_no', value: detail.logNo },
                { label: 'source', value: detail.source },
                { label: 'ip_address', value: detail.ipAddress },
                { label: 'device', value: detail.device },
                { label: 'raw_status', value: detail.status },
                { label: 'raw_risk_level', value: detail.riskLevel },
              ]}
            >
              <section className="detail-section">
                <h3>操作前数据</h3>
                <pre>{JSON.stringify(redactTechnicalObject(detail.beforeData), null, 2)}</pre>
              </section>
              <section className="detail-section">
                <h3>操作后数据</h3>
                <pre>{JSON.stringify(redactTechnicalObject(detail.afterData), null, 2)}</pre>
              </section>
            </TechnicalDetails>
          </>
        ) : <EmptyState title="暂无日志详情" description="请选择一条日志记录查看完整内容。" />}
      </DetailModal>
    </>
  );
}
