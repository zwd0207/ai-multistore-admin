import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import { useAuthContext } from '../context/AuthContext';
import backendApi from '../services/backendApi';

function useTenantDirectory(enabled = true) {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await backendApi.getTenants();
      setTenants(Array.isArray(result?.items) ? result.items : []);
    } catch (requestError) {
      setError(requestError.message || '租户列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (enabled) load();
    else setLoading(false);
  }, [enabled]);
  return { tenants, loading, error, reload: load };
}

export function TenantSelectionPage() {
  const {
    isAuthenticated, isPlatformAdmin, selectedTenantId, selectTenant, status,
  } = useAuthContext();
  const navigate = useNavigate();
  const { tenants, loading, error } = useTenantDirectory(isAuthenticated && isPlatformAdmin);
  const [busyId, setBusyId] = useState('');
  const [actionError, setActionError] = useState('');

  if (status === 'checking') return <TenantSelectionShell><p>正在检查登录状态...</p></TenantSelectionShell>;
  if (!isAuthenticated) return <Navigate to="/" replace />;
  if (!isPlatformAdmin) return <Navigate to="/workbench" replace />;
  if (selectedTenantId) return <Navigate to="/workbench" replace />;

  const choose = async (tenantId) => {
    setBusyId(String(tenantId));
    setActionError('');
    try {
      await selectTenant(tenantId);
      navigate('/workbench', { replace: true });
    } catch (requestError) {
      setActionError(requestError.message || '租户选择失败');
    } finally {
      setBusyId('');
    }
  };

  return (
    <TenantSelectionShell>
      <h1>选择管理租户</h1>
      <p>进入业务数据前先明确选择一个租户。切换行为会记录到操作审计。</p>
      {loading ? <div className="table-state"><span className="spinner" />正在加载...</div> : null}
      {!loading && !tenants.length ? <p className="form-error">{error || '当前没有可用租户。'}</p> : null}
      <div className="tenant-selection-list">
        {tenants.map((tenant) => (
          <button className="tenant-selection-row" type="button" key={tenant.id} onClick={() => choose(tenant.id)} disabled={Boolean(busyId) || tenant.status !== 'active'}>
            <span><strong>{tenant.name}</strong><small>{tenant.user_count} 个账号 · {tenant.store_count} 个店铺</small></span>
            <span>{busyId === String(tenant.id) ? '正在进入...' : '进入'}</span>
          </button>
        ))}
      </div>
      {actionError ? <p className="form-error">{actionError}</p> : null}
    </TenantSelectionShell>
  );
}

export function TenantAdminPage() {
  const {
    isPlatformAdmin, selectedTenantId, selectTenant,
  } = useAuthContext();
  const { tenants, loading, error, reload } = useTenantDirectory();
  const [form, setForm] = useState({ email: '', displayName: '', tenantName: '' });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  if (!isPlatformAdmin) return <Navigate to="/workbench" replace />;

  const updateField = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const invite = async (event) => {
    event.preventDefault();
    setBusy(true);
    setNotice('');
    try {
      const result = await backendApi.createTenantInvitation({
        email: form.email.trim(),
        display_name: form.displayName.trim(),
        tenant_name: form.tenantName.trim(),
      });
      setForm({ email: '', displayName: '', tenantName: '' });
      setNotice(result?.delivery_status === 'queued' ? '邀请邮件已进入发送队列。' : '邀请已创建，邮件服务启用后会自动发送。');
      await reload();
    } catch (requestError) {
      setNotice(requestError.errorCode === 'account_already_exists' ? '该邮箱已经注册。' : (requestError.message || '邀请创建失败'));
    } finally {
      setBusy(false);
    }
  };

  const switchTenant = async (tenantId) => {
    if (String(tenantId) === String(selectedTenantId)) return;
    setBusy(true);
    setNotice('');
    try {
      await selectTenant(tenantId);
      setNotice('已切换管理租户。');
    } catch (requestError) {
      setNotice(requestError.message || '租户切换失败');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="租户与邀请" description="管理独立运营账号及其数据范围。" />
      <section className="content-card tenant-invite-section">
        <div className="section-heading"><div><h2>邀请运营人员</h2><p>每位受邀用户会获得独立租户，并在首次登录时强制绑定 MFA。</p></div></div>
        <form className="tenant-invite-form" onSubmit={invite}>
          <label>登录邮箱<input type="email" value={form.email} onChange={updateField('email')} required /></label>
          <label>运营人员姓名<input value={form.displayName} onChange={updateField('displayName')} required /></label>
          <label>租户名称<input value={form.tenantName} onChange={updateField('tenantName')} required /></label>
          <button className="button primary" disabled={busy}>{busy ? '正在处理...' : '发送邀请'}</button>
        </form>
        {notice ? <p className="inline-notice">{notice}</p> : null}
      </section>
      <section className="content-card tenant-directory-section">
        <div className="section-heading"><div><h2>租户目录</h2><p>进入业务数据前必须选择明确的管理租户。</p></div></div>
        {loading ? <div className="table-state"><span className="spinner" />正在加载...</div> : null}
        {error ? <p className="form-error">{error}</p> : null}
        {!loading ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>租户</th><th>状态</th><th>账号</th><th>店铺</th><th>操作</th></tr></thead>
              <tbody>
                {tenants.map((tenant) => (
                  <tr key={tenant.id}>
                    <td>{tenant.name}</td>
                    <td><StatusBadge value={tenant.status} /></td>
                    <td>{tenant.user_count}</td>
                    <td>{tenant.store_count}</td>
                    <td className="table-actions"><button type="button" disabled={busy || String(tenant.id) === String(selectedTenantId)} onClick={() => switchTenant(tenant.id)}>{String(tenant.id) === String(selectedTenantId) ? '当前租户' : '进入管理'}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </>
  );
}

function TenantSelectionShell({ children }) {
  return (
    <main className="auth-shell">
      <section className="auth-panel tenant-selection-panel">
        <div className="auth-brand"><span>ERP</span><strong>平台管理</strong></div>
        {children}
      </section>
    </main>
  );
}
