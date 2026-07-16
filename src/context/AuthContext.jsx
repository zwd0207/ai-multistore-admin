import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import backendApi from '../services/backendApi';
import { clearCsrfToken, setCsrfToken, setSessionFailureHandler } from '../services/http';


const AuthContext = createContext(null);

function sessionStateFromError(error) {
  if (error?.status !== 401 && error?.status !== 403) return 'unavailable';
  if (error.errorCode === 'session_expired') return 'expired';
  if (error.errorCode === 'reauthentication_required') return 'reauthentication_required';
  if (error.errorCode === 'permission_forbidden' || error.errorCode === 'store_scope_forbidden') return 'forbidden';
  return 'unauthenticated';
}

function normalizeSession(session) {
  return {
    user: session?.user || null,
    tenant: session?.tenant || null,
    administration: session?.administration || {
      is_platform_admin: false,
      selected_tenant_id: null,
      cross_tenant_mode: false,
    },
    stores: Array.isArray(session?.stores) ? session.stores : [],
    authnLevel: session?.authn_level || null,
    expiresAt: session?.absolute_expires_at || null,
  };
}

export function AuthProvider({ children }) {
  const [status, setStatus] = useState('checking');
  const [session, setSession] = useState(() => normalizeSession(null));

  const applySession = useCallback((nextSession) => {
    setCsrfToken(nextSession?.csrf_token);
    setSession(normalizeSession(nextSession));
    setStatus('authenticated');
  }, []);

  const clearSession = useCallback((nextStatus = 'unauthenticated', force = false) => {
    clearCsrfToken();
    setSession(normalizeSession(null));
    setStatus((currentStatus) => {
      const explanatoryStates = ['expired', 'forbidden', 'reauthentication_required'];
      if (!force && nextStatus === 'unauthenticated' && explanatoryStates.includes(currentStatus)) {
        return currentStatus;
      }
      return nextStatus;
    });
  }, []);

  const refreshSession = useCallback(async () => {
    try {
      const nextSession = await backendApi.getSession();
      applySession(nextSession);
      return nextSession;
    } catch (error) {
      clearSession(sessionStateFromError(error));
      throw error;
    }
  }, [applySession, clearSession]);

  useEffect(() => {
    let active = true;
    refreshSession().catch(() => {
      if (!active) return;
    });
    return () => { active = false; };
  }, [refreshSession]);

  useEffect(() => setSessionFailureHandler(({ status, errorCode }) => {
    clearSession(sessionStateFromError({ status, errorCode }));
  }), [clearSession]);

  const login = useCallback(async ({ loginIdentifier, password }) => {
    clearSession('unauthenticated', true);
    const result = await backendApi.login({ login_identifier: loginIdentifier, password });
    setStatus('mfa_required');
    return result;
  }, [clearSession]);

  const verifyMfa = useCallback(async (code) => {
    const result = await backendApi.verifyMfa({ code });
    await refreshSession();
    return result;
  }, [refreshSession]);

  const logout = useCallback(async () => {
    try {
      await backendApi.logout();
    } finally {
      clearSession('unauthenticated', true);
    }
  }, [clearSession]);

  const selectTenant = useCallback(async (tenantId) => {
    await backendApi.selectTenant(tenantId);
    return refreshSession();
  }, [refreshSession]);

  const canAccessStore = useCallback((storeId, permissionKey) => {
    const store = session.stores.find((item) => String(item.store_id) === String(storeId));
    if (!store) return false;
    const requiredPermissions = Array.isArray(permissionKey) ? permissionKey : [permissionKey];
    return !permissionKey || store.permissions?.includes('*') || requiredPermissions.some((key) => store.permissions?.includes(key));
  }, [session.stores]);

  const value = useMemo(() => ({
    status,
    isAuthenticated: status === 'authenticated',
    isChecking: status === 'checking',
    user: session.user,
    tenant: session.tenant,
    administration: session.administration,
    isPlatformAdmin: session.administration.is_platform_admin === true,
    selectedTenantId: session.administration.selected_tenant_id,
    crossTenantMode: session.administration.cross_tenant_mode === true,
    stores: session.stores,
    authnLevel: session.authnLevel,
    expiresAt: session.expiresAt,
    canAccessStore,
    getRequestState: sessionStateFromError,
    login,
    verifyMfa,
    refreshSession,
    selectTenant,
    logout,
  }), [status, session, canAccessStore, login, verifyMfa, refreshSession, selectTenant, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuthContext must be used inside AuthProvider');
  return context;
}

export default AuthContext;
