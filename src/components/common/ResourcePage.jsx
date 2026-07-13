import {
  useCallback, useEffect, useMemo, useRef, useState,
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
  fields = [],
  statuses = [],
  platforms = [],
  initialForm = {},
  readOnly = false,
  canCreate = !readOnly,
  canEdit = !readOnly,
  canDelete = !readOnly,
  extraParams = {},
  initialQuery = {},
  initialQueryKey = '',
  reloadKey = '',
  onSaved,
  extraActions,
  emptyState,
  renderActions,
  renderExtraActions,
  prepareForm,
  buildSavePayload,
  afterSave,
  renderFormExtra,
  modalWidth,
  openRecordId = '',
  openRecordKey = '',
}) {
  const baseQuery = useMemo(
    () => ({
      keyword: '',
      status: '',
      platform: '',
      page: 1,
      pageSize: 5,
      ...initialQuery,
    }),
    [initialQueryKey],
  );
  const [query, setQuery] = useState(baseQuery);
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState({ open: false, record: null });
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [loadError, setLoadError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const extraParamsKey = JSON.stringify(extraParams);
  const stableExtraParams = useMemo(() => extraParams, [extraParamsKey]);

  useEffect(() => {
    setQuery(baseQuery);
    setDraftQuery(baseQuery);
  }, [baseQuery]);

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

  const openModal = async (record = null) => {
    const baseForm = record ? fields.reduce((value, field) => (
      field.type === 'section' ? value : { ...value, [field.key]: record[field.key] ?? '' }
    ), {}) : initialForm;
    setModal({ open: true, record });
    setForm(baseForm);
    setErrors({});
    setSaveError('');
    if (prepareForm) {
      setFormLoading(true);
      try {
        setForm(await prepareForm({ record, form: baseForm }));
      } catch (error) {
        setSaveError(error.message || '表单数据加载失败');
      } finally {
        setFormLoading(false);
      }
    }
  };

  const save = async () => {
    if (submitting) return;
    const nextErrors = fields.reduce(
      (value, field) => (field.type !== 'section'
        && field.required
        && (!field.showWhen || field.showWhen(form))
        && !String(form[field.key] ?? '').trim()
        ? { ...value, [field.key]: `请填写${field.label}` }
        : value),
      {},
    );
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }
    setSubmitting(true);
    setSaveError('');
    try {
      const payload = buildSavePayload
        ? buildSavePayload({ form, record: modal.record, extraParams: stableExtraParams })
        : { ...form, ...stableExtraParams };
      const saved = modal.record ? await api.update(modal.record.id, payload) : await api.create(payload);
      if (afterSave) await afterSave({ saved, form, record: modal.record, payload });
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
    const name = record.name || record.orderNo || record.id;
    if (!window.confirm(`确认删除“${name}”吗？此操作只影响系统本地记录。`)) return;
    await api.remove(record.id);
    await load();
  };

  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => {
    setDraftQuery(baseQuery);
    setQuery(baseQuery);
  };

  const rows = result.data || [];
  const shouldShowEmptyState = !loading && !loadError && rows.length === 0 && emptyState;

  const handledOpenRecordRef = useRef('');
  useEffect(() => {
    if (!openRecordId || loading || !rows.length) return;
    const requestKey = `${openRecordKey || 'record'}:${openRecordId}`;
    if (handledOpenRecordRef.current === requestKey) return;
    const record = rows.find((item) => String(item.id) === String(openRecordId));
    if (!record) return;
    handledOpenRecordRef.current = requestKey;
    openModal(record);
  }, [openRecordId, openRecordKey, loading, rows]);

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={(
          <>
            <button className="button ghost" type="button" onClick={load}>刷新</button>
            {extraActions}
            {readOnly ? <span className="period-chip">暂不支持在线编辑</span> : null}
            {canCreate ? <button className="button primary" type="button" onClick={() => openModal()}>新增{resourceName}</button> : null}
          </>
        )}
      />
      <section className="content-card">
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder={`搜索${resourceName}名称、编号或负责人`}
        >
          {platforms.length > 0 && (
            <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
              <option value="">全部平台</option>
              {platforms.map((item) => (typeof item === 'object'
                ? <option key={item.value} value={item.value}>{item.label}</option>
                : <option key={item}>{item}</option>))}
            </select>
          )}
          {statuses.length > 0 && (
            <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
              <option value="">全部状态</option>
              {statuses.map((item) => (typeof item === 'object'
                ? <option key={item.value} value={item.value}>{item.label}</option>
                : <option key={item}>{item}</option>))}
            </select>
          )}
        </SearchBar>
        {loadError ? (
          <EmptyState title={`${resourceName}数据加载失败`} description={loadError} />
        ) : shouldShowEmptyState ? (
          <EmptyState title={emptyState.title} description={emptyState.description} actions={emptyState.actions} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={rows}
              loading={loading}
              onEdit={canEdit ? openModal : undefined}
              onDelete={canDelete ? remove : undefined}
              renderActions={renderActions}
              renderExtraActions={renderExtraActions}
            />
            <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
          </>
        )}
      </section>
      {(canCreate || canEdit) && (
        <Modal
          open={modal.open}
          title={`${modal.record ? '编辑' : '新增'}${resourceName}`}
          onClose={() => setModal({ open: false, record: null })}
          onConfirm={save}
          confirmText={submitting ? '保存中...' : '保存'}
          confirmDisabled={submitting || formLoading}
          width={modalWidth}
        >
          {formLoading && <div className="table-state"><span className="spinner" />正在读取表单数据...</div>}
          {saveError && <div className="form-error">{saveError}</div>}
          <div className="form-grid">
            {fields.map((field) => {
              if (field.showWhen && !field.showWhen(form)) return null;
              if (field.type === 'section') {
                return (
                  <div key={field.key} className="form-section-title">
                    <h3>{field.label}</h3>
                    {field.description ? <p>{field.description}</p> : null}
                  </div>
                );
              }
              const help = typeof field.help === 'function' ? field.help(form) : field.help;
              return (
                <FormField key={field.key} label={field.label} required={field.required} error={errors[field.key]}>
                  {field.type === 'select' ? (
                    <select
                      value={form[field.key] ?? ''}
                      disabled={submitting || formLoading || field.disabled}
                      onChange={(event) => setForm({ ...form, [field.key]: event.target.value })}
                    >
                      <option value="">请选择</option>
                      {field.options.map((option) => (typeof option === 'object'
                        ? <option key={option.value} value={option.value}>{option.label}</option>
                        : <option key={option}>{option}</option>))}
                    </select>
                  ) : (
                    <input
                      type={field.type || 'text'}
                      value={form[field.key] ?? ''}
                      disabled={submitting || formLoading || field.disabled}
                      placeholder={field.placeholder || `请输入${field.label}`}
                      onChange={(event) => setForm({
                        ...form,
                        [field.key]: field.type === 'number' ? Number(event.target.value) : event.target.value,
                      })}
                    />
                  )}
                  {help ? <small className="form-help">{help}</small> : null}
                </FormField>
              );
            })}
            {renderFormExtra ? renderFormExtra({
              form, setForm, record: modal.record, submitting, formLoading,
            }) : null}
          </div>
        </Modal>
      )}
    </>
  );
}
