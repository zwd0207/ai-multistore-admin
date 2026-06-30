import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { formatKstDateTimeWithLabel } from '../utils/time';

const platformOptions = ['naver', 'coupang'];
const categoryOptions = ['products', 'orders', 'inquiries', 'sales', 'settlements', 'seller', 'logistics', 'auth'];
const statusOptions = ['not_tested', 'planned', 'tested_success', 'tested_failed', 'unavailable', 'permission_required'];
const capabilityModeOptions = ['docs_only', 'manual'];
const resultModeOptions = ['manual', 'docs_only', 'mock', 'sandbox'];
const supportedOptions = ['unknown', 'yes', 'no'];
const usefulnessOptions = ['high', 'medium', 'low', 'not_useful', 'unknown'];
const salesSourceOptions = ['order-derived', 'platform-stat-api', 'settlement-api', 'manual', 'not_applicable'];
const methodOptions = ['', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];

const initialCapabilityForm = {
  platform: 'naver',
  capabilityKey: '',
  capabilityName: '',
  apiCategory: 'products',
  endpointPath: '',
  method: 'GET',
  requiredCredentialType: '',
  requiredPermission: '',
  ordinaryStoreSupported: 'unknown',
  testStatus: 'planned',
  testMode: 'docs_only',
  requestParamsSummary: '',
  responseFieldsSummary: '',
  errorCodesSummary: '',
  dataUsefulness: 'unknown',
  firstPhaseCandidate: false,
  salesSourceType: 'not_applicable',
  officialDocUrl: '',
  docCheckedAt: '',
  notes: '',
  lastCheckedAt: '',
};

const initialResultForm = {
  capabilityId: '',
  credentialId: '',
  testMode: 'manual',
  testStatus: 'planned',
  httpStatus: '',
  errorCode: '',
  permissionResult: '',
  rateLimitSummary: '',
  responseFieldsObserved: '',
  testedAt: '',
  notes: '',
};

const capabilityColumns = [
  { key: 'platform', title: '平台' },
  { key: 'capabilityKey', title: '能力 Key', render: (value, row) => <div><strong>{value}</strong><small className="cell-subtitle">{row.capabilityName}</small></div> },
  { key: 'apiCategory', title: '类别' },
  { key: 'endpointPath', title: '接口路径' },
  { key: 'method', title: '方法' },
  { key: 'testStatus', title: '记录状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'testMode', title: '记录模式' },
  { key: 'salesSourceType', title: '销售额来源' },
  { key: 'officialDocUrl', title: '官方文档', render: (value) => (value ? <a href={value} target="_blank" rel="noreferrer">文档链接</a> : '-') },
  { key: 'notes', title: '备注' },
  { key: 'docCheckedAt', title: '文档确认时间' },
  { key: 'lastCheckedAt', title: '最近确认时间' },
  { key: 'updatedAt', title: '更新时间' },
];

const resultColumns = [
  { key: 'storeLabel', title: '当前店铺' },
  { key: 'credentialLabel', title: 'API 凭证（脱敏）' },
  { key: 'capabilityLabel', title: '能力记录' },
  { key: 'capabilityPlatform', title: '能力平台' },
  { key: 'capabilityCategory', title: '能力类别' },
  { key: 'testMode', title: '记录模式' },
  { key: 'testStatus', title: '记录状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'httpStatus', title: 'HTTP 状态' },
  { key: 'errorCode', title: '错误码' },
  { key: 'permissionResult', title: '权限结果' },
  { key: 'rateLimitSummary', title: '限流摘要' },
  { key: 'responseFieldsObserved', title: '响应字段观察摘要' },
  { key: 'testedAt', title: '记录时间' },
  { key: 'notes', title: '备注' },
  { key: 'createdAt', title: '创建时间' },
];

function cleanError(error) {
  return error?.message || '后端 API 能力记录请求失败，请检查 Codex1 状态或表单内容';
}

function toDatetimeLocalValue(value) {
  if (!value) return '';
  return String(value).slice(0, 16);
}

function statusLabel(value) {
  if (value === 'tested_success') return '人工记录：测试通过（非真实接入）';
  return value;
}

function capabilityOptionLabel(item) {
  return `${item.platform} · ${item.capabilityKey} · ${item.capabilityName || item.apiCategory}`;
}

function credentialOptionLabel(item) {
  const identity = item.rawPlatform === 'coupang' ? item.vendorId : item.clientId;
  const keyState = [
    item.hasAccessKey ? 'key' : null,
    item.hasSecretKey ? 'secret' : null,
    item.hasAccessToken ? 'access token' : null,
    item.hasRefreshToken ? 'refresh token' : null,
  ].filter(Boolean).join('/');
  return `${item.platform} · ${item.name || `Credential #${item.id}`} · ${identity || '无平台标识'} · ${item.authStatus || 'not_configured'} · ${keyState || '未配置密钥状态'}`;
}

function enrichResults(rows, capabilities, credentials, selectedStoreId, stores = []) {
  const capabilityMap = new Map(capabilities.map((item) => [String(item.id), item]));
  const credentialMap = new Map(credentials.map((item) => [String(item.id), item]));
  const store = stores.find((item) => String(item.id) === String(selectedStoreId));
  return rows.map((row) => {
    const capability = capabilityMap.get(String(row.capabilityId));
    const credential = row.credentialId ? credentialMap.get(String(row.credentialId)) : null;
    return {
      ...row,
      storeLabel: store?.name || `Store #${row.storeId || selectedStoreId}`,
      credentialLabel: credential ? credentialOptionLabel(credential) : '未绑定凭证',
      capabilityLabel: capability ? capabilityOptionLabel(capability) : `Capability #${row.capabilityId}`,
      capabilityPlatform: capability?.platform || '-',
      capabilityCategory: capability?.apiCategory || '-',
    };
  });
}

export default function ApiCapabilities() {
  const {
    selectedStoreId, stores, loading: storeLoading, error: storeError,
  } = useStoreContext();
  const [capabilityQuery, setCapabilityQuery] = useState({ keyword: '', platform: '', apiCategory: '', testStatus: '', testMode: '', firstPhaseCandidate: '', salesSourceType: '', page: 1, pageSize: 8 });
  const [capabilityDraft, setCapabilityDraft] = useState(capabilityQuery);
  const [capabilities, setCapabilities] = useState({ data: [], total: 0, page: 1, pageSize: 8 });
  const [capabilityLoading, setCapabilityLoading] = useState(true);
  const [capabilityError, setCapabilityError] = useState('');
  const [capabilityModal, setCapabilityModal] = useState({ open: false, record: null });
  const [capabilityForm, setCapabilityForm] = useState(initialCapabilityForm);
  const [capabilityFormError, setCapabilityFormError] = useState('');
  const [resultQuery, setResultQuery] = useState({ testStatus: '', testMode: '', capabilityId: '', credentialId: '', page: 1, pageSize: 8 });
  const [results, setResults] = useState({ data: [], total: 0, page: 1, pageSize: 8 });
  const [resultLoading, setResultLoading] = useState(true);
  const [resultError, setResultError] = useState('');
  const [resultModalOpen, setResultModalOpen] = useState(false);
  const [resultForm, setResultForm] = useState(initialResultForm);
  const [resultFormError, setResultFormError] = useState('');
  const [credentials, setCredentials] = useState([]);
  const [credentialError, setCredentialError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const selectedStore = useMemo(
    () => stores.find((item) => String(item.id) === String(selectedStoreId)),
    [selectedStoreId, stores],
  );

  const selectedCapability = useMemo(
    () => capabilities.data.find((item) => String(item.id) === String(resultForm.capabilityId)),
    [capabilities.data, resultForm.capabilityId],
  );

  const matchingCredentials = useMemo(() => {
    if (!selectedCapability) return credentials;
    return credentials.filter((item) => String(item.rawPlatform || '').toLowerCase() === String(selectedCapability.rawPlatform || '').toLowerCase());
  }, [credentials, selectedCapability]);

  const loadCapabilities = useCallback(async () => {
    setCapabilityLoading(true);
    setCapabilityError('');
    try {
      const params = {
        ...capabilityQuery,
        api_category: capabilityQuery.apiCategory || undefined,
        test_status: capabilityQuery.testStatus || undefined,
        test_mode: capabilityQuery.testMode || undefined,
        first_phase_candidate: capabilityQuery.firstPhaseCandidate === '' ? undefined : capabilityQuery.firstPhaseCandidate === 'true',
        sales_source_type: capabilityQuery.salesSourceType || undefined,
      };
      setCapabilities(await dataProvider.getApiCapabilities(params));
    } catch (error) {
      setCapabilities({ data: [], total: 0, page: capabilityQuery.page, pageSize: capabilityQuery.pageSize });
      setCapabilityError(cleanError(error));
    } finally {
      setCapabilityLoading(false);
    }
  }, [capabilityQuery]);

  const loadCredentials = useCallback(async () => {
    if (!isBackendSource || !selectedStoreId || storeLoading || storeError) {
      setCredentials([]);
      setCredentialError('');
      return [];
    }
    try {
      const response = await dataProvider.getCredentials({ storeId: selectedStoreId, page: 1, pageSize: 100 });
      const rows = response.data || response.items || [];
      setCredentials(rows);
      setCredentialError('');
      return rows;
    } catch (error) {
      setCredentials([]);
      setCredentialError(cleanError(error));
      return [];
    }
  }, [selectedStoreId, storeError, storeLoading]);

  const loadResults = useCallback(async () => {
    if (storeLoading) return;
    if (!isBackendSource || storeError || !selectedStoreId) {
      setResults({ data: [], total: 0, page: resultQuery.page, pageSize: resultQuery.pageSize });
      setResultError(storeError || '');
      setResultLoading(false);
      return;
    }
    setResultLoading(true);
    setResultError('');
    try {
      const [credentialRows, resultResponse] = await Promise.all([
        loadCredentials(),
        dataProvider.getApiCapabilityResults({
          storeId: selectedStoreId,
          credential_id: resultQuery.credentialId || undefined,
          capability_id: resultQuery.capabilityId || undefined,
          test_status: resultQuery.testStatus || undefined,
          test_mode: resultQuery.testMode || undefined,
          page: resultQuery.page,
          pageSize: resultQuery.pageSize,
        }),
      ]);
      setResults({
        ...resultResponse,
        data: enrichResults(resultResponse.data || [], capabilities.data, credentialRows, selectedStoreId, stores),
      });
    } catch (error) {
      setResults({ data: [], total: 0, page: resultQuery.page, pageSize: resultQuery.pageSize });
      setResultError(cleanError(error));
    } finally {
      setResultLoading(false);
    }
  }, [capabilities.data, loadCredentials, resultQuery, selectedStoreId, storeError, storeLoading, stores]);

  useEffect(() => { loadCapabilities(); }, [loadCapabilities]);
  useEffect(() => { loadCredentials(); }, [loadCredentials]);
  useEffect(() => { loadResults(); }, [loadResults]);

  const openCapabilityModal = (record = null) => {
    setCapabilityModal({ open: true, record });
    setCapabilityForm(record ? {
      platform: record.rawPlatform || 'naver',
      capabilityKey: record.capabilityKey || '',
      capabilityName: record.capabilityName || '',
      apiCategory: record.apiCategory || 'products',
      endpointPath: record.endpointPath || '',
      method: record.method || 'GET',
      requiredCredentialType: record.requiredCredentialType || '',
      requiredPermission: record.requiredPermission || '',
      ordinaryStoreSupported: record.ordinaryStoreSupported || 'unknown',
      testStatus: record.testStatus || 'planned',
      testMode: capabilityModeOptions.includes(record.testMode) ? record.testMode : 'docs_only',
      requestParamsSummary: record.requestParamsSummary || '',
      responseFieldsSummary: record.responseFieldsSummary || '',
      errorCodesSummary: record.errorCodesSummary || '',
      dataUsefulness: record.dataUsefulness || 'unknown',
      firstPhaseCandidate: Boolean(record.firstPhaseCandidate),
      salesSourceType: record.salesSourceType || 'not_applicable',
      officialDocUrl: record.officialDocUrl || '',
      docCheckedAt: toDatetimeLocalValue(record.docCheckedAt),
      notes: record.notes || '',
      lastCheckedAt: toDatetimeLocalValue(record.lastCheckedAt),
    } : initialCapabilityForm);
    setCapabilityFormError('');
  };

  const saveCapability = async () => {
    if (!isBackendSource) {
      setCapabilityFormError('mock 模式不维护后端 API 能力矩阵，请切换 backend 模式查看/写入 Codex1 记录。');
      return;
    }
    if (!capabilityForm.capabilityKey.trim() || !capabilityForm.capabilityName.trim()) {
      setCapabilityFormError('请填写能力 Key 与能力名称');
      return;
    }
    setSubmitting(true);
    setCapabilityFormError('');
    try {
      if (capabilityModal.record) await dataProvider.updateApiCapability(capabilityModal.record.id, capabilityForm);
      else await dataProvider.createApiCapability(capabilityForm);
      setCapabilityModal({ open: false, record: null });
      await loadCapabilities();
    } catch (error) {
      setCapabilityFormError(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const openResultModal = () => {
    if (!selectedStoreId) return;
    setResultForm(initialResultForm);
    setResultFormError('');
    setResultModalOpen(true);
  };

  const saveResult = async () => {
    if (!selectedStoreId) {
      setResultFormError('请先选择店铺');
      return;
    }
    if (!resultForm.capabilityId) {
      setResultFormError('请选择能力记录');
      return;
    }
    setSubmitting(true);
    setResultFormError('');
    try {
      await dataProvider.createApiCapabilityResult({ ...resultForm, storeId: selectedStoreId });
      setResultModalOpen(false);
      await loadResults();
    } catch (error) {
      setResultFormError(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const mockNotice = !isBackendSource
    ? 'mock 模式不维护后端 API 能力矩阵，请切换 backend 模式查看/写入 Codex1 记录。'
    : '';

  return (
    <>
      <PageHeader
        title="API 能力确认"
        description="记录 Naver / Coupang API 能力确认情况与当前店铺级人工结果。"
        actions={<span className="period-chip">时间显示：KST</span>}
      />

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h2>接口能力确认工作台</h2>
            <p>docs-only / manual 仅表示文档确认或人工记录，不代表当前店铺凭证已通过真实平台验证。本阶段不会调用 Naver / Coupang API。真实只读 API 测试将在后续阶段单独授权执行。</p>
          </div>
          {mockNotice && <span className="period-chip">{mockNotice}</span>}
        </div>
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h2>平台级能力定义</h2>
            <p>平台级 docs-only/manual 记录用于判断接口可能提供什么数据，不代表任何店铺凭证已完成验证。</p>
          </div>
          <div className="page-actions">
            <button className="button ghost" onClick={loadCapabilities}>刷新</button>
            <button className="button primary" onClick={() => openCapabilityModal()} disabled={!isBackendSource}>新增文档/人工记录</button>
          </div>
        </div>
        <SearchBar
          value={capabilityDraft.keyword}
          onChange={(keyword) => setCapabilityDraft({ ...capabilityDraft, keyword })}
          onSearch={() => setCapabilityQuery({ ...capabilityDraft, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', platform: '', apiCategory: '', testStatus: '', testMode: '', firstPhaseCandidate: '', salesSourceType: '', page: 1, pageSize: 8 };
            setCapabilityDraft(clean);
            setCapabilityQuery(clean);
          }}
          placeholder="搜索能力 Key、名称、路径或备注"
        >
          <select value={capabilityDraft.platform} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={capabilityDraft.apiCategory} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, apiCategory: event.target.value })}>
            <option value="">全部类别</option>
            {categoryOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={capabilityDraft.testStatus} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, testStatus: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}
          </select>
          <select value={capabilityDraft.testMode} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, testMode: event.target.value })}>
            <option value="">全部模式</option>
            {capabilityModeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={capabilityDraft.firstPhaseCandidate} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, firstPhaseCandidate: event.target.value })}>
            <option value="">首阶段候选</option>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
          <select value={capabilityDraft.salesSourceType} onChange={(event) => setCapabilityDraft({ ...capabilityDraft, salesSourceType: event.target.value })}>
            <option value="">全部销售来源</option>
            {salesSourceOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
        {capabilityError ? <EmptyState title="平台级能力加载失败" description={capabilityError} /> : (
          <>
            <DataTable
              columns={capabilityColumns}
              rows={capabilities.data || []}
              loading={capabilityLoading}
              renderActions={(row) => <button onClick={() => openCapabilityModal(row)} disabled={!isBackendSource}>编辑</button>}
            />
            <Pagination page={capabilityQuery.page} pageSize={capabilityQuery.pageSize} total={capabilities.total} onChange={(page) => setCapabilityQuery({ ...capabilityQuery, page })} />
          </>
        )}
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h2>当前店铺级结果</h2>
            <p>{selectedStoreId ? `当前店铺：${selectedStore?.name || `Store #${selectedStoreId}`}。结果记录只代表当前店铺级人工/文档记录，不等于平台通用能力。` : '请先选择店铺。'}</p>
          </div>
          <div className="page-actions">
            <button className="button ghost" onClick={loadResults} disabled={!selectedStoreId}>刷新</button>
            <button className="button primary" onClick={openResultModal} disabled={!isBackendSource || !selectedStoreId}>新增店铺级人工结果</button>
          </div>
        </div>
        {credentialError && <div className="form-info">{credentialError}</div>}
        {!selectedStoreId && !storeLoading ? (
          <EmptyState title="请先选择店铺" description="店铺级 API 能力结果必须绑定当前 StoreContext 中的 selectedStoreId。" />
        ) : resultError ? (
          <EmptyState title="店铺级结果加载失败" description={resultError} />
        ) : (
          <>
            <SearchBar
              value=""
              onChange={() => {}}
              onSearch={() => loadResults()}
              onReset={() => setResultQuery({ testStatus: '', testMode: '', capabilityId: '', credentialId: '', page: 1, pageSize: 8 })}
              placeholder="店铺级结果通过下方筛选"
            >
              <select value={resultQuery.capabilityId} onChange={(event) => setResultQuery({ ...resultQuery, capabilityId: event.target.value, page: 1 })}>
                <option value="">全部能力</option>
                {(capabilities.data || []).map((item) => <option key={item.id} value={item.id}>{capabilityOptionLabel(item)}</option>)}
              </select>
              <select value={resultQuery.credentialId} onChange={(event) => setResultQuery({ ...resultQuery, credentialId: event.target.value, page: 1 })}>
                <option value="">全部凭证</option>
                {credentials.map((item) => <option key={item.id} value={item.id}>{credentialOptionLabel(item)}</option>)}
              </select>
              <select value={resultQuery.testStatus} onChange={(event) => setResultQuery({ ...resultQuery, testStatus: event.target.value, page: 1 })}>
                <option value="">全部状态</option>
                {statusOptions.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}
              </select>
              <select value={resultQuery.testMode} onChange={(event) => setResultQuery({ ...resultQuery, testMode: event.target.value, page: 1 })}>
                <option value="">全部模式</option>
                {resultModeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </SearchBar>
            <DataTable columns={resultColumns} rows={results.data || []} loading={resultLoading || storeLoading} />
            <Pagination page={resultQuery.page} pageSize={resultQuery.pageSize} total={results.total} onChange={(page) => setResultQuery({ ...resultQuery, page })} />
          </>
        )}
      </section>

      <Modal
        open={capabilityModal.open}
        title={capabilityModal.record ? '编辑文档/人工能力记录' : '新增文档/人工能力记录'}
        onClose={() => setCapabilityModal({ open: false, record: null })}
        onConfirm={saveCapability}
        confirmText={submitting ? '保存中...' : '保存记录'}
        confirmDisabled={submitting}
        width="min(1040px, 94vw)"
      >
        {capabilityFormError && <div className="form-error">{capabilityFormError}</div>}
        <div className="form-info">此表单仅维护文档/人工记录，不会调用真实平台 API。</div>
        <div className="form-grid">
          <FormField label="平台" required>
            <select value={capabilityForm.platform} onChange={(event) => setCapabilityForm({ ...capabilityForm, platform: event.target.value })}>{platformOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="能力 Key" required><input value={capabilityForm.capabilityKey} onChange={(event) => setCapabilityForm({ ...capabilityForm, capabilityKey: event.target.value })} /></FormField>
          <FormField label="能力名称" required><input value={capabilityForm.capabilityName} onChange={(event) => setCapabilityForm({ ...capabilityForm, capabilityName: event.target.value })} /></FormField>
          <FormField label="类别" required><select value={capabilityForm.apiCategory} onChange={(event) => setCapabilityForm({ ...capabilityForm, apiCategory: event.target.value })}>{categoryOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></FormField>
          <FormField label="接口路径"><input value={capabilityForm.endpointPath} onChange={(event) => setCapabilityForm({ ...capabilityForm, endpointPath: event.target.value })} /></FormField>
          <FormField label="方法"><select value={capabilityForm.method} onChange={(event) => setCapabilityForm({ ...capabilityForm, method: event.target.value })}>{methodOptions.map((item) => <option key={item || 'blank'} value={item}>{item || '未记录'}</option>)}</select></FormField>
          <FormField label="凭证类型"><input value={capabilityForm.requiredCredentialType} onChange={(event) => setCapabilityForm({ ...capabilityForm, requiredCredentialType: event.target.value })} /></FormField>
          <FormField label="普通店铺支持"><select value={capabilityForm.ordinaryStoreSupported} onChange={(event) => setCapabilityForm({ ...capabilityForm, ordinaryStoreSupported: event.target.value })}>{supportedOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></FormField>
          <FormField label="记录状态"><select value={capabilityForm.testStatus} onChange={(event) => setCapabilityForm({ ...capabilityForm, testStatus: event.target.value })}>{statusOptions.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}</select></FormField>
          <FormField label="记录模式"><select value={capabilityForm.testMode} onChange={(event) => setCapabilityForm({ ...capabilityForm, testMode: event.target.value })}>{capabilityModeOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></FormField>
          <FormField label="数据价值"><select value={capabilityForm.dataUsefulness} onChange={(event) => setCapabilityForm({ ...capabilityForm, dataUsefulness: event.target.value })}>{usefulnessOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></FormField>
          <FormField label="销售额来源"><select value={capabilityForm.salesSourceType} onChange={(event) => setCapabilityForm({ ...capabilityForm, salesSourceType: event.target.value })}>{salesSourceOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></FormField>
          <FormField label="官方文档 URL"><input value={capabilityForm.officialDocUrl} onChange={(event) => setCapabilityForm({ ...capabilityForm, officialDocUrl: event.target.value })} /></FormField>
          <FormField label="文档确认时间"><input type="datetime-local" value={capabilityForm.docCheckedAt} onChange={(event) => setCapabilityForm({ ...capabilityForm, docCheckedAt: event.target.value })} /></FormField>
          <FormField label="最近确认时间"><input type="datetime-local" value={capabilityForm.lastCheckedAt} onChange={(event) => setCapabilityForm({ ...capabilityForm, lastCheckedAt: event.target.value })} /></FormField>
          <FormField label="首阶段候选"><input type="checkbox" checked={capabilityForm.firstPhaseCandidate} onChange={(event) => setCapabilityForm({ ...capabilityForm, firstPhaseCandidate: event.target.checked })} /></FormField>
        </div>
        <FormField label="权限说明"><textarea value={capabilityForm.requiredPermission} onChange={(event) => setCapabilityForm({ ...capabilityForm, requiredPermission: event.target.value })} /></FormField>
        <FormField label="请求参数摘要"><textarea value={capabilityForm.requestParamsSummary} onChange={(event) => setCapabilityForm({ ...capabilityForm, requestParamsSummary: event.target.value })} /></FormField>
        <FormField label="返回字段摘要"><textarea value={capabilityForm.responseFieldsSummary} onChange={(event) => setCapabilityForm({ ...capabilityForm, responseFieldsSummary: event.target.value })} /></FormField>
        <FormField label="错误码摘要"><textarea value={capabilityForm.errorCodesSummary} onChange={(event) => setCapabilityForm({ ...capabilityForm, errorCodesSummary: event.target.value })} /></FormField>
        <FormField label="备注"><textarea value={capabilityForm.notes} onChange={(event) => setCapabilityForm({ ...capabilityForm, notes: event.target.value })} /></FormField>
      </Modal>

      <Modal
        open={resultModalOpen}
        title="新增店铺级人工结果"
        onClose={() => setResultModalOpen(false)}
        onConfirm={saveResult}
        confirmText={submitting ? '保存中...' : '保存记录'}
        confirmDisabled={submitting}
        width="min(980px, 94vw)"
      >
        {resultFormError && <div className="form-error">{resultFormError}</div>}
        <div className="form-info">店铺级结果仅记录 manual/docs/mock/sandbox 情况，不会调用真实平台 API，也不会读取凭证明文。</div>
        <div className="form-grid">
          <FormField label="能力记录" required>
            <select value={resultForm.capabilityId} onChange={(event) => setResultForm({ ...resultForm, capabilityId: event.target.value, credentialId: '' })}>
              <option value="">请选择能力记录</option>
              {(capabilities.data || []).map((item) => <option key={item.id} value={item.id}>{capabilityOptionLabel(item)}</option>)}
            </select>
          </FormField>
          <FormField label="API 凭证（脱敏）">
            <select value={resultForm.credentialId} onChange={(event) => setResultForm({ ...resultForm, credentialId: event.target.value })}>
              <option value="">不绑定凭证</option>
              {matchingCredentials.map((item) => <option key={item.id} value={item.id}>{credentialOptionLabel(item)}</option>)}
            </select>
          </FormField>
          <FormField label="记录模式"><select value={resultForm.testMode} onChange={(event) => setResultForm({ ...resultForm, testMode: event.target.value })}>{resultModeOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></FormField>
          <FormField label="记录状态"><select value={resultForm.testStatus} onChange={(event) => setResultForm({ ...resultForm, testStatus: event.target.value })}>{statusOptions.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}</select></FormField>
          <FormField label="HTTP 状态"><input type="number" min="100" max="599" value={resultForm.httpStatus} onChange={(event) => setResultForm({ ...resultForm, httpStatus: event.target.value })} /></FormField>
          <FormField label="错误码"><input value={resultForm.errorCode} onChange={(event) => setResultForm({ ...resultForm, errorCode: event.target.value })} /></FormField>
          <FormField label="记录时间"><input type="datetime-local" value={resultForm.testedAt} onChange={(event) => setResultForm({ ...resultForm, testedAt: event.target.value })} /></FormField>
        </div>
        <FormField label="权限结果"><textarea value={resultForm.permissionResult} onChange={(event) => setResultForm({ ...resultForm, permissionResult: event.target.value })} /></FormField>
        <FormField label="限流摘要"><textarea value={resultForm.rateLimitSummary} onChange={(event) => setResultForm({ ...resultForm, rateLimitSummary: event.target.value })} /></FormField>
        <FormField label="响应字段观察摘要"><textarea value={resultForm.responseFieldsObserved} onChange={(event) => setResultForm({ ...resultForm, responseFieldsObserved: event.target.value })} /></FormField>
        <FormField label="备注"><textarea value={resultForm.notes} onChange={(event) => setResultForm({ ...resultForm, notes: event.target.value })} /></FormField>
      </Modal>
    </>
  );
}
