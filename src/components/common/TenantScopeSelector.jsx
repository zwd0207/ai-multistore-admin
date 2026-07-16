import { useEffect, useState } from 'react';
import { useAuthContext } from '../../context/AuthContext';
import backendApi from '../../services/backendApi';

export default function TenantScopeSelector() {
  const {
    isPlatformAdmin, selectedTenantId, selectTenant,
  } = useAuthContext();
  const [tenants, setTenants] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isPlatformAdmin) return undefined;
    let active = true;
    backendApi.getTenants()
      .then((result) => {
        if (active) setTenants(Array.isArray(result?.items) ? result.items : []);
      })
      .catch(() => {
        if (active) setError('租户列表加载失败');
      });
    return () => { active = false; };
  }, [isPlatformAdmin]);

  if (!isPlatformAdmin) return null;

  const changeTenant = async (event) => {
    const tenantId = event.target.value;
    if (!tenantId || String(tenantId) === String(selectedTenantId) || busy) return;
    setBusy(true);
    setError('');
    try {
      await selectTenant(tenantId);
    } catch (requestError) {
      setError(requestError.message || '租户切换失败');
    } finally {
      setBusy(false);
    }
  };

  return (
    <label className={`tenant-scope-selector ${error ? 'is-error' : ''}`} title={error || '当前管理租户'}>
      <span>管理租户</span>
      <select value={selectedTenantId || ''} onChange={changeTenant} disabled={busy}>
        <option value="">请选择租户</option>
        {tenants.map((tenant) => (
          <option key={tenant.id} value={tenant.id}>{tenant.name}</option>
        ))}
      </select>
    </label>
  );
}
