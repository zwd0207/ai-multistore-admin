import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import BackendReadOnlyPage from '../components/common/BackendReadOnlyPage';
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
const providerOptions = ['naver', 'gmail', 'daum', 'outlook', 'custom'];

const initialForm = {
  email: '',
  provider: 'naver',
  label: '',
  credentialInput: '',
  status: 'active',
  remark: '',
};

const accountColumns = [
  { key: 'email', title: '邮箱地址', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'provider', title: '服务商' },
  { key: 'label', title: '账号标签' },
  { key: 'hasCredential', title: '认证配置', render: (value) => (value ? '已配置' : '未配置') },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'lastCheckedAt', title: '最近检查' },
  { key: 'remark', title: '备注' },
];

const importantColumns = [
  { key: 'subject', title: '重要邮件', render: (value, row) => <div><strong>{value}</strong><small className="cell-subtitle">{row.snippet}</small></div> },
  { key: 'platform', title: '平台' },
  { key: 'type', title: '类型' },
  { key: 'sender', title: '发件人' },
  { key: 'priority', title: '优先级', render: (value) => <StatusBadge value={value} /> },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'receivedAt', title: '收件时间' },
];

function cleanError(error) {
  return error?.message || '后端保存失败，请检查 Codex1 后端状态或表单内容';
}

function ImportantEmailsReadOnly() {
  return (
    <BackendReadOnlyPage
      title="重要邮件"
      description="读取当前店铺的重要邮件摘要，本阶段仍保持只读。"
      resourceName="重要邮件"
      loadData={dataProvider.getImportantEmails}
      columns={importantColumns}
    />
  );
}

export default function BackendEmailAccountsPage() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', status: '', page: 1, pageSize: 5 });
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
      setResult(await dataProvider.getEmailAccounts(params));
    } catch (error) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError(error.message || '邮箱账号数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [params, query.page, query.pageSize, selectedStoreId, storeError, storeLoading]);

  useEffect(() => { load(); }, [load]);

  const openModal = (record = null) => {
    setModal({ open: true, record });
    setForm(record ? {
      email: record.email || '',
      provider: record.provider || 'naver',
      label: record.label || '',
      credentialInput: '',
      status: record.status || 'active',
      remark: record.remark || '',
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
    if (!String(form.email || '').trim()) nextErrors.email = '请填写邮箱地址';
    if (!String(form.provider || '').trim()) nextErrors.provider = '请选择服务商';
    if (!String(form.status || '').trim()) nextErrors.status = '请选择状态';
    setErrors(nextErrors);
    return !Object.keys(nextErrors).length;
  };

  const save = async () => {
    if (submitting || !validate()) return;
    setSubmitting(true);
    setSaveError('');
    try {
      const payload = { ...form, storeId: selectedStoreId };
      if (modal.record) await dataProvider.updateEmailAccount(modal.record.id, payload);
      else await dataProvider.createEmailAccount(payload);
      setModal({ open: false, record: null });
      setForm(initialForm);
      await load();
    } catch (error) {
      setForm((current) => ({ ...current, credentialInput: '' }));
      setSaveError(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const showTestNotice = () => {
    setNotice('当前仅保存本地配置，未进行真实邮箱校验');
  };

  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => {
    const clean = { keyword: '', status: '', page: 1, pageSize: 5 };
    setDraftQuery(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="邮箱管理"
        description={storeError || (!selectedStoreId && !storeLoading ? '请先选择店铺' : '维护当前店铺的本地邮箱账号配置，不进行真实邮箱连接校验。')}
        actions={(
          <>
            <button className="button ghost" onClick={load}>刷新</button>
            <span className="period-chip">本地后端写入</span>
            {canWrite && <button className="button primary" onClick={() => openModal()}>新增邮箱账号</button>}
          </>
        )}
      />
      <section className="content-card">
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索邮箱地址或账号标签"
        >
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
        {notice && <div className="form-info">{notice}</div>}
        {loadError ? (
          <EmptyState title="邮箱账号数据加载失败" description={loadError} />
        ) : !selectedStoreId && !storeLoading ? (
          <EmptyState title="暂无店铺数据" description="请先选择店铺后再维护邮箱账号。" />
        ) : (
          <>
            <DataTable
              columns={accountColumns}
              rows={result.data || []}
              loading={loading || storeLoading}
              renderActions={(row) => (
                <>
                  <button onClick={() => openModal(row)} disabled={!canWrite || submitting}>编辑</button>
                  <button onClick={showTestNotice}>测试连接</button>
                </>
              )}
            />
            <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
          </>
        )}
      </section>
      <ImportantEmailsReadOnly />
      <Modal
        open={modal.open}
        title={`${modal.record ? '编辑' : '新增'}邮箱账号`}
        onClose={closeModal}
        onConfirm={save}
        confirmText={submitting ? '保存中...' : '保存'}
        confirmDisabled={submitting}
      >
        {(saveError || errors.form) && <div className="form-error">{saveError || errors.form}</div>}
        <div className="form-grid">
          <FormField label="邮箱地址" required error={errors.email}>
            <input value={form.email} disabled={submitting} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="请输入邮箱地址" />
          </FormField>
          <FormField label="服务商" required error={errors.provider}>
            <select value={form.provider} disabled={submitting} onChange={(event) => setForm({ ...form, provider: event.target.value })}>
              {providerOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="账号标签">
            <input value={form.label} disabled={submitting} onChange={(event) => setForm({ ...form, label: event.target.value })} placeholder="请输入账号标签" />
          </FormField>
          <FormField label="认证值">
            <input type="password" value={form.credentialInput} disabled={submitting} onChange={(event) => setForm({ ...form, credentialInput: event.target.value })} placeholder={modal.record ? '留空则不更新' : '可选填写认证值'} />
          </FormField>
          <FormField label="状态" required error={errors.status}>
            <select value={form.status} disabled={submitting} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="备注">
            <input value={form.remark} disabled={submitting} onChange={(event) => setForm({ ...form, remark: event.target.value })} placeholder="请输入备注" />
          </FormField>
        </div>
      </Modal>
    </>
  );
}
