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
import dataProvider from '../services/dataProvider';

const statusOptions = ['active', 'inactive'];
const platformOptions = [
  { value: 'naver', label: 'Naver' },
  { value: 'coupang', label: 'Coupang' },
];

const initialForm = {
  name: '',
  platform: 'naver',
  status: 'active',
  accessKeyInput: '',
  secretKeyInput: '',
};

const columns = [
  { key: 'name', title: '凭证名称', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'accessKeyStatus', title: '访问配置' },
  { key: 'secretKeyStatus', title: '密钥配置' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '创建时间' },
  { key: 'updatedAt', title: '更新时间' },
];

function cleanError(error) {
  return error?.message || '后端保存失败，请检查 Codex1 后端状态或表单内容';
}

export default function BackendCredentialPage() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', status: '', platform: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [notice, setNotice] = useState('');
  const [modal, setModal] = useState({ open: false, record: null });
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [saveError, setSaveError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const canWrite = Boolean(selectedStoreId) && !storeLoading && !storeError;

  const params = useMemo(() => ({ ...query, storeId: selectedStoreId }), [query, selectedStoreId]);

  const load = useCallback(async () => {
    if (storeLoading) return;
    if (storeError) {
      setLoadError(storeError);
      setLoading(false);
      return;
    }
    if (!selectedStoreId) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError('');
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError('');
    try {
      setResult(await dataProvider.getCredentials(params));
    } catch (error) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError(error.message || 'API 凭证数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [params, query.page, query.pageSize, selectedStoreId, storeError, storeLoading]);

  useEffect(() => { load(); }, [load]);

  const resetSensitiveInputs = (nextForm = form) => ({
    ...nextForm,
    accessKeyInput: '',
    secretKeyInput: '',
  });

  const openModal = (record = null) => {
    setModal({ open: true, record });
    setForm(record ? {
      name: record.name || '',
      platform: String(record.platform || 'naver').toLowerCase(),
      status: record.status || 'active',
      accessKeyInput: '',
      secretKeyInput: '',
    } : initialForm);
    setErrors({});
    setSaveError('');
    setNotice('');
  };

  const closeModal = () => {
    if (submitting) return;
    setModal({ open: false, record: null });
    setForm(initialForm);
    setErrors({});
    setSaveError('');
  };

  const validate = () => {
    const nextErrors = {};
    if (!selectedStoreId) nextErrors.form = '请先选择店铺';
    if (!String(form.name || '').trim()) nextErrors.name = '请填写凭证名称';
    if (!String(form.platform || '').trim()) nextErrors.platform = '请选择平台';
    if (!String(form.status || '').trim()) nextErrors.status = '请选择状态';
    if (!modal.record && !String(form.accessKeyInput || '').trim()) nextErrors.accessKeyInput = '请填写访问配置';
    if (!modal.record && !String(form.secretKeyInput || '').trim()) nextErrors.secretKeyInput = '请填写密钥配置';
    setErrors(nextErrors);
    return !Object.keys(nextErrors).length;
  };

  const save = async () => {
    if (submitting || !validate()) return;
    setSubmitting(true);
    setSaveError('');
    try {
      const payload = { ...form, storeId: selectedStoreId };
      if (modal.record) await dataProvider.updateCredential(modal.record.id, payload);
      else await dataProvider.createCredential(payload);
      setModal({ open: false, record: null });
      setForm(initialForm);
      await load();
    } catch (error) {
      setForm((current) => resetSensitiveInputs(current));
      setSaveError(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const disableCredential = async (record) => {
    if (!canWrite || submitting) return;
    setSubmitting(true);
    setNotice('');
    try {
      await dataProvider.disableCredential(record.id, { storeId: selectedStoreId });
      await load();
      setNotice('凭证已停用，本地列表已刷新');
    } catch (error) {
      setNotice(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const showTestNotice = () => {
    setNotice('当前仅保存本地配置，未进行真实平台校验');
  };

  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => {
    const clean = { keyword: '', status: '', platform: '', page: 1, pageSize: 5 };
    setDraftQuery(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="账号管理"
        description={storeError || (!selectedStoreId && !storeLoading ? '请先选择店铺' : '维护当前店铺的本地 API 凭证配置，不进行真实平台连接校验。')}
        actions={(
          <>
            <button className="button ghost" onClick={load}>刷新</button>
            <span className="period-chip">本地后端写入</span>
            {canWrite && <button className="button primary" onClick={() => openModal()}>新增 API 凭证</button>}
          </>
        )}
      />
      <section className="content-card">
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索凭证名称或平台"
        >
          <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
        {notice && <div className="form-info">{notice}</div>}
        {loadError ? (
          <EmptyState title="API 凭证数据加载失败" description={loadError} />
        ) : !selectedStoreId && !storeLoading ? (
          <EmptyState title="暂无店铺数据" description="请先选择店铺后再维护 API 凭证。" />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={result.data || []}
              loading={loading || storeLoading}
              renderActions={(row) => (
                <>
                  <button onClick={() => openModal(row)} disabled={!canWrite || submitting}>编辑</button>
                  {row.status !== 'inactive' && <button className="danger-text" onClick={() => disableCredential(row)} disabled={!canWrite || submitting}>停用</button>}
                  <button onClick={showTestNotice}>测试连接</button>
                </>
              )}
            />
            <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
          </>
        )}
      </section>
      <Modal
        open={modal.open}
        title={`${modal.record ? '编辑' : '新增'} API 凭证`}
        onClose={closeModal}
        onConfirm={save}
        confirmText={submitting ? '保存中...' : '保存'}
        confirmDisabled={submitting}
      >
        {(saveError || errors.form) && <div className="form-error">{saveError || errors.form}</div>}
        <div className="form-grid">
          <FormField label="凭证名称" required error={errors.name}>
            <input value={form.name} disabled={submitting} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="请输入凭证名称" />
          </FormField>
          <FormField label="平台" required error={errors.platform}>
            <select value={form.platform} disabled={submitting} onChange={(event) => setForm({ ...form, platform: event.target.value })}>
              {platformOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </FormField>
          <FormField label="状态" required error={errors.status}>
            <select value={form.status} disabled={submitting} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="访问配置" required={!modal.record} error={errors.accessKeyInput}>
            <input type="password" value={form.accessKeyInput} disabled={submitting} onChange={(event) => setForm({ ...form, accessKeyInput: event.target.value })} placeholder={modal.record ? '留空则不更新' : '请输入访问配置'} />
          </FormField>
          <FormField label="密钥配置" required={!modal.record} error={errors.secretKeyInput}>
            <input type="password" value={form.secretKeyInput} disabled={submitting} onChange={(event) => setForm({ ...form, secretKeyInput: event.target.value })} placeholder={modal.record ? '留空则不更新' : '请输入密钥配置'} />
          </FormField>
        </div>
      </Modal>
    </>
  );
}
