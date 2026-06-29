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
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';

const modules = ['店铺管理', '商品管理', '订单管理', '客服管理', '销售数据', '设备管理', '邮箱管理', '申诉管理', '环境管理', '账号管理', '系统设置'];
const actionTypes = ['新增', '编辑', '删除', '状态变更', '绑定', '解绑', '回复', '提交', '登录', '风险检测', '配置修改'];
const statuses = ['성공', '실패', '대기', '경고', '위험'];
const riskLevels = ['낮음', '보통', '높음', '긴급'];
const operators = ['系统管理员', 'Coupang 申诉处理账号', '韩国本土运营账号', '系统检测器'];

const columns = [
  { key: 'logNo', title: '日志编号', render: (value) => <strong>{value}</strong> },
  { key: 'time', title: '操作时间' },
  { key: 'module', title: '操作模块' },
  { key: 'actionType', title: '操作类型' },
  { key: 'operator', title: '操作人' },
  { key: 'objectName', title: '关联对象' },
  { key: 'summary', title: '操作摘要' },
  { key: 'ipAddress', title: 'IP 地址' },
  { key: 'device', title: '设备' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'riskLevel', title: '风险等级', render: (value) => <StatusBadge value={value} /> },
];

const syncColumns = [
  { key: 'logNo', title: '同步日志编号', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'type', title: '同步类型' },
  { key: 'message', title: '同步消息' },
  { key: 'startedAt', title: '开始时间' },
  { key: 'finishedAt', title: '结束时间' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
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
  const [syncLogs, setSyncLogs] = useState({ data: [], total: 0 });
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

  const loadSyncLogs = async () => {
    if (!isBackendSource) return;
    if (storeLoading) return;
    setSyncLoading(true);
    setSyncError('');
    try {
      if (storeError) throw new Error(storeError);
      if (!selectedStoreId) {
        setSyncLogs({ data: [], total: 0 });
        return;
      }
      setSyncLogs(await dataProvider.getSyncLogs({ storeId: selectedStoreId, page: 1, pageSize: 10 }));
    } catch (error) {
      setSyncLogs({ data: [], total: 0 });
      setSyncError(error.message || '同步日志加载失败');
    } finally {
      setSyncLoading(false);
    }
  };

  useEffect(() => {
    loadSyncLogs();
  }, [selectedStoreId, storeLoading, storeError, versions.syncLogs]);

  const openDetail = async (row) => {
    setDetail(await mockApi.getOperationLogDetail(row.id));
    setDetailOpen(true);
  };

  const markRisk = async (row) => {
    await mockApi.markLogRisk(row.id, { riskLevel: '긴급', status: '위험', riskNote: '人工标记为重点风险日志' });
    if (detail?.id === row.id) setDetail(await mockApi.getOperationLogDetail(row.id));
    await load();
  };

  return (
    <>
      <PageHeader title="操作日志" description="审计后台操作、配置修改、绑定行为和风险检测记录。" actions={isBackendSource ? <button className="button ghost" onClick={loadSyncLogs}>刷新同步日志</button> : null} />

      {isBackendSource && <section className="content-card">
        <div className="card-title">
          <div><h2>Codex1 同步日志</h2><p>读取 `/api/v1/sync-logs`，原操作审计日志继续保留。</p></div>
          <span className="period-chip">共 {syncLogs.total} 条</span>
        </div>
        <MockSyncPanel onSynced={loadSyncLogs} />
        {syncError ? <EmptyState title="同步日志加载失败" description={syncError} /> : <DataTable columns={syncColumns} rows={syncLogs.data || []} loading={syncLoading} />}
      </section>}

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
        <DataTable
          columns={columns}
          rows={result.data}
          loading={loading}
          renderActions={(row) => (
            <>
              <button onClick={() => openDetail(row)}>详情</button>
              <button onClick={() => openDetail(row)}>关联对象</button>
              <button onClick={() => markRisk(row)}>风险标记</button>
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </section>

      <DetailModal open={detailOpen} title={detail ? `日志详情 · ${detail.logNo}` : '日志详情'} onClose={() => setDetailOpen(false)} width="min(980px, 94vw)">
        {detail ? (
          <>
            <section className="detail-section">
              <h3>基础日志信息</h3>
              <InfoGrid items={[
                { label: '操作时间', value: detail.time },
                { label: '操作模块', value: detail.module },
                { label: '操作类型', value: detail.actionType },
                { label: '操作人', value: detail.operator },
                { label: '状态', value: <StatusBadge value={detail.status} /> },
                { label: '风险等级', value: <StatusBadge value={detail.riskLevel} /> },
              ]} />
            </section>
            <section className="detail-section">
              <h3>操作前数据</h3>
              <pre>{JSON.stringify(detail.beforeData, null, 2)}</pre>
            </section>
            <section className="detail-section">
              <h3>操作后数据</h3>
              <pre>{JSON.stringify(detail.afterData, null, 2)}</pre>
            </section>
            <section className="detail-section">
              <h3>操作来源</h3>
              <InfoGrid items={[
                { label: '来源', value: detail.source },
                { label: '关联对象', value: detail.objectName },
                { label: 'IP 地址', value: detail.ipAddress },
                { label: '设备', value: detail.device },
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
          </>
        ) : <EmptyState title="暂无日志详情" description="请选择一条日志记录查看完整内容。" />}
      </DetailModal>
    </>
  );
}
