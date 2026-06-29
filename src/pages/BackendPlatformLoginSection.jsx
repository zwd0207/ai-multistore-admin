import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider from '../services/dataProvider';

const platformOptions = [
  { value: 'naver', label: 'Naver SmartStore' },
  { value: 'coupang', label: 'Coupang Wing' },
];
const statusOptions = ['active', 'inactive', 'unknown', 'needs_check'];

const initialForm = {
  platform: 'naver',
  label: '',
  account: '',
  passwordInput: '',
  emailAccountId: '',
  deviceEnvironmentId: '',
  loginStatus: 'unknown',
  remark: '',
};

const columns = [
  { key: 'platform', title: '平台' },
  { key: 'label', title: '登录配置名称', render: (value) => <strong>{value}</strong> },
  { key: 'account', title: '登录账号' },
  { key: 'passwordStatus', title: '密码状态' },
  { key: 'emailAccountLabel', title: '验证码邮箱' },
  { key: 'deviceEnvironmentLabel', title: '绑定设备环境' },
  { key: 'status', title: '本地配置状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'remark', title: '备注' },
  { key: 'updatedAt', title: '更新时间' },
];

function cleanError(error) {
  return error?.message || '后端保存失败，请检查 Codex1 后端状态或表单内容';
}

function makeEmailLabel(item) {
  if (!item) return '未绑定';
  return item.label ? `${item.email} · ${item.label}` : item.email;
}

function makeDeviceLabel(item) {
  if (!item) return '未绑定';
  return [item.name, item.deviceType, item.status].filter(Boolean).join(' · ');
}

function withBindingLabels(rows, emailAccounts, deviceEnvironments) {
  const emailMap = new Map(emailAccounts.map((item) => [String(item.id), makeEmailLabel(item)]));
  const deviceMap = new Map(deviceEnvironments.map((item) => [String(item.id), makeDeviceLabel(item)]));
  return rows.map((row) => ({
    ...row,
    emailAccountLabel: row.emailAccountId ? emailMap.get(String(row.emailAccountId)) || `邮箱 #${row.emailAccountId}` : '未绑定',
    deviceEnvironmentLabel: row.deviceEnvironmentId ? deviceMap.get(String(row.deviceEnvironmentId)) || `设备 #${row.deviceEnvironmentId}` : '未绑定',
  }));
}

export default function BackendPlatformLoginSection() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', platform: '', status: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [bindingOptions, setBindingOptions] = useState({ emails: [], devices: [] });
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

  const loadBindings = useCallback(async () => {
    if (!selectedStoreId || storeLoading || storeError) {
      setBindingOptions({ emails: [], devices: [] });
      return { emails: [], devices: [] };
    }
    const [emails, devices] = await Promise.all([
      dataProvider.getEmailAccounts({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
      dataProvider.getDeviceEnvironments({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
    ]);
    const next = {
      emails: emails.data || emails.items || [],
      devices: devices.data || devices.items || [],
    };
    setBindingOptions(next);
    return next;
  }, [selectedStoreId, storeError, storeLoading]);

  const load = useCallback(async () => {
    if (storeLoading) return;
    if (storeError) {
      setLoadError(storeError);
      setLoading(false);
      return;
    }
    if (!selectedStoreId) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setBindingOptions({ emails: [], devices: [] });
      setLoadError('');
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError('');
    try {
      const [bindings, logins] = await Promise.all([
        loadBindings(),
        dataProvider.getPlatformLogins(params),
      ]);
      setResult({
        ...logins,
        data: withBindingLabels(logins.data || [], bindings.emails, bindings.devices),
      });
    } catch (error) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError(error.message || '平台登录信息加载失败');
    } finally {
      setLoading(false);
    }
  }, [loadBindings, params, query.page, query.pageSize, selectedStoreId, storeError, storeLoading]);

  useEffect(() => { load(); }, [load]);

  const resetSensitiveInputs = (nextForm = form) => ({
    ...nextForm,
    passwordInput: '',
  });

  const openModal = async (record = null) => {
    if (!canWrite) return;
    setModal({ open: true, record });
    setForm(record ? {
      platform: String(record.rawPlatform || record.platform || 'naver').toLowerCase(),
      label: record.label || '',
      account: record.account || '',
      passwordInput: '',
      emailAccountId: record.emailAccountId || '',
      deviceEnvironmentId: record.deviceEnvironmentId || '',
      loginStatus: record.loginStatus || 'unknown',
      remark: record.remark || '',
    } : initialForm);
    setErrors({});
    setSaveError('');
    setNotice('');
    try {
      await loadBindings();
    } catch (error) {
      setSaveError(error.message || '绑定选项加载失败');
    }
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
    if (!String(form.platform || '').trim()) nextErrors.platform = '请选择平台';
    if (!String(form.label || '').trim()) nextErrors.label = '请填写登录配置名称';
    if (!String(form.loginStatus || '').trim()) nextErrors.loginStatus = '请选择本地配置状态';
    setErrors(nextErrors);
    return !Object.keys(nextErrors).length;
  };

  const save = async () => {
    if (submitting || !validate()) return;
    setSubmitting(true);
    setSaveError('');
    try {
      const payload = { ...form, storeId: selectedStoreId };
      if (modal.record) await dataProvider.updatePlatformLogin(modal.record.id, payload);
      else await dataProvider.createPlatformLogin(payload);
      setModal({ open: false, record: null });
      setForm(initialForm);
      await load();
      setNotice('平台登录信息已保存，本地列表已刷新');
    } catch (error) {
      setForm((current) => resetSensitiveInputs(current));
      setSaveError(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const deactivate = async (record) => {
    if (!canWrite || submitting) return;
    setSubmitting(true);
    setNotice('');
    try {
      await dataProvider.deactivatePlatformLogin(record.id, { storeId: selectedStoreId });
      await load();
      setNotice('平台登录信息已停用，本地列表已刷新');
    } catch (error) {
      setNotice(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => {
    const clean = { keyword: '', platform: '', status: '', page: 1, pageSize: 5 };
    setDraftQuery(clean);
    setQuery(clean);
  };

  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>平台登录信息</h2>
          <p>用于人工登录 Naver SmartStore / Coupang Wing 后台。当前仅保存本地配置，未进行真实平台登录校验。</p>
        </div>
        <div className="page-actions">
          <button className="button ghost" onClick={load}>刷新</button>
          {canWrite && <button className="button primary" onClick={() => openModal()}>新增平台登录信息</button>}
        </div>
      </div>
      <SearchBar
        value={draftQuery.keyword}
        onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
        onSearch={search}
        onReset={reset}
        placeholder="搜索登录配置名称、账号或备注"
      >
        <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
          <option value="">全部平台</option>
          {platformOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
          <option value="">全部本地配置状态</option>
          {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </SearchBar>
      {notice && <div className="form-info">{notice}</div>}
      {loadError ? (
        <EmptyState title="平台登录信息加载失败" description={loadError} />
      ) : !selectedStoreId && !storeLoading ? (
        <EmptyState title="暂无店铺数据" description="请先选择店铺后再维护平台登录信息。" />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={result.data || []}
            loading={loading || storeLoading}
            renderActions={(row) => (
              <>
                <button onClick={() => openModal(row)} disabled={!canWrite || submitting}>编辑</button>
                {row.loginStatus !== 'inactive' && <button className="danger-text" onClick={() => deactivate(row)} disabled={!canWrite || submitting}>停用</button>}
              </>
            )}
          />
          <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
        </>
      )}
      <Modal
        open={modal.open}
        title={`${modal.record ? '编辑' : '新增'}平台登录信息`}
        onClose={closeModal}
        onConfirm={save}
        confirmText={submitting ? '保存中...' : '保存'}
        confirmDisabled={submitting}
      >
        {(saveError || errors.form) && <div className="form-error">{saveError || errors.form}</div>}
        <div className="form-grid">
          <FormField label="平台" required error={errors.platform}>
            <select value={form.platform} disabled={submitting} onChange={(event) => setForm({ ...form, platform: event.target.value })}>
              {platformOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </FormField>
          <FormField label="登录配置名称" required error={errors.label}>
            <input value={form.label} disabled={submitting} onChange={(event) => setForm({ ...form, label: event.target.value })} placeholder="例如 Naver SmartStore 主账号" />
          </FormField>
          <FormField label="登录账号">
            <input value={form.account} disabled={submitting} onChange={(event) => setForm({ ...form, account: event.target.value })} placeholder="请输入后台登录账号" />
          </FormField>
          <FormField label="登录密码">
            <input type="password" value={form.passwordInput} disabled={submitting} onChange={(event) => setForm({ ...form, passwordInput: event.target.value })} placeholder={modal.record ? '留空则不更新' : '可选填写登录密码'} />
          </FormField>
          <FormField label="验证码邮箱">
            <select value={form.emailAccountId} disabled={submitting} onChange={(event) => setForm({ ...form, emailAccountId: event.target.value })}>
              <option value="">不绑定邮箱</option>
              {bindingOptions.emails.map((item) => <option key={item.id} value={item.id}>{makeEmailLabel(item)}</option>)}
            </select>
            {!bindingOptions.emails.length && <small>当前店铺尚未绑定邮箱，可先到邮箱账户区添加。</small>}
          </FormField>
          <FormField label="登录设备">
            <select value={form.deviceEnvironmentId} disabled={submitting} onChange={(event) => setForm({ ...form, deviceEnvironmentId: event.target.value })}>
              <option value="">不绑定设备</option>
              {bindingOptions.devices.map((item) => <option key={item.id} value={item.id}>{makeDeviceLabel(item)}</option>)}
            </select>
            {!bindingOptions.devices.length && <small>当前店铺尚未绑定设备，可先到设备环境页面添加。</small>}
          </FormField>
          <FormField label="本地配置状态" required error={errors.loginStatus}>
            <select value={form.loginStatus} disabled={submitting} onChange={(event) => setForm({ ...form, loginStatus: event.target.value })}>
              {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="备注">
            <input value={form.remark} disabled={submitting} onChange={(event) => setForm({ ...form, remark: event.target.value })} placeholder="请输入备注" />
          </FormField>
        </div>
      </Modal>
    </section>
  );
}
