import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import DataTable from './DataTable';
import EmptyState from './EmptyState';
import FormField from './FormField';
import Modal from './Modal';
import PageHeader from './PageHeader';
import Pagination from './Pagination';
import SearchBar from './SearchBar';

export default function ResourcePage({
  title,
  description,
  resourceName,
  api,
  columns,
  fields,
  statuses,
  platforms = [],
  initialForm,
  readOnly = false,
  canCreate = !readOnly,
  canEdit = !readOnly,
  canDelete = !readOnly,
  extraParams = {},
  reloadKey = '',
  onSaved,
}) {
  const [query, setQuery] = useState({ keyword: '', status: '', platform: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState({ open: false, record: null });
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [loadError, setLoadError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const extraParamsKey = JSON.stringify(extraParams);
  const stableExtraParams = useMemo(() => extraParams, [extraParamsKey]);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      setResult(await api.list({ ...query, ...stableExtraParams }));
    } catch (error) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError(error.message || `${resourceName}数据加载失败`);
    } finally {
      setLoading(false);
    }
  }, [api, query, stableExtraParams, reloadKey, resourceName]);
  useEffect(() => { load(); }, [load]);

  const openModal = (record = null) => {
    setModal({ open: true, record });
    setForm(record ? fields.reduce((value, field) => ({ ...value, [field.key]: record[field.key] ?? '' }), {}) : initialForm);
    setErrors({});
    setSaveError('');
  };
  const save = async () => {
    if (submitting) return;
    const nextErrors = fields.reduce((value, field) => field.required && !String(form[field.key] ?? '').trim() ? { ...value, [field.key]: `请填写${field.label}` } : value, {});
    if (Object.keys(nextErrors).length) return setErrors(nextErrors);
    setSubmitting(true);
    setSaveError('');
    try {
      const payload = { ...form, ...stableExtraParams };
      const saved = modal.record ? await api.update(modal.record.id, payload) : await api.create(payload);
      setModal({ open: false, record: null });
      await load();
      if (onSaved) await onSaved(saved);
    } catch (error) {
      setSaveError(error.message || `${resourceName}保存失败`);
    } finally {
      setSubmitting(false);
    }
  };
  const remove = async (record) => {
    if (!window.confirm(`确认删除“${record.name || record.orderNo}”吗？此操作不可撤销。`)) return;
    await api.remove(record.id);
    await load();
  };
  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => { const clean = { keyword: '', status: '', platform: '', page: 1, pageSize: 5 }; setDraftQuery(clean); setQuery(clean); };

  return <>
    <PageHeader title={title} description={description} actions={<><button className="button ghost" onClick={load}>↻ 刷新</button>{readOnly ? <span className="period-chip">后端只读</span> : null}{canCreate ? <button className="button primary" onClick={() => openModal()}>＋ 新增{resourceName}</button> : null}</>} />
    <section className="content-card">
      <SearchBar value={draftQuery.keyword} onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })} onSearch={search} onReset={reset} placeholder={`搜索${resourceName}名称、编号或负责人`}>
        {platforms.length > 0 && <select value={draftQuery.platform} onChange={(e) => setDraftQuery({ ...draftQuery, platform: e.target.value })}><option value="">全部平台</option>{platforms.map((item) => <option key={item}>{item}</option>)}</select>}
        <select value={draftQuery.status} onChange={(e) => setDraftQuery({ ...draftQuery, status: e.target.value })}><option value="">全部状态</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select>
      </SearchBar>
      {loadError ? <EmptyState title={`${resourceName}数据加载失败`} description={loadError} /> : <>
        <DataTable columns={columns} rows={result.data || []} loading={loading} onEdit={canEdit ? openModal : undefined} onDelete={canDelete ? remove : undefined} />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </>}
    </section>
    {(canCreate || canEdit) && <Modal open={modal.open} title={`${modal.record ? '编辑' : '新增'}${resourceName}`} onClose={() => setModal({ open: false, record: null })} onConfirm={save} confirmText={submitting ? '保存中...' : '保存'} confirmDisabled={submitting}>
      {saveError && <div className="form-error">{saveError}</div>}
      <div className="form-grid">{fields.map((field) => <FormField key={field.key} label={field.label} required={field.required} error={errors[field.key]}>
        {field.type === 'select' ? <select value={form[field.key] ?? ''} disabled={submitting || field.disabled} onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}><option value="">请选择</option>{field.options.map((option) => (typeof option === 'object' ? <option key={option.value} value={option.value}>{option.label}</option> : <option key={option}>{option}</option>))}</select> : <input type={field.type || 'text'} value={form[field.key] ?? ''} disabled={submitting || field.disabled} placeholder={field.placeholder || `请输入${field.label}`} onChange={(e) => setForm({ ...form, [field.key]: field.type === 'number' ? Number(e.target.value) : e.target.value })} />}
      </FormField>)}</div>
    </Modal>}
  </>;
}
