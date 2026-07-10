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
    clearSession('mfa_required', true);
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

  const canAccessStore = useCallback((storeId, permissionKey) => {
    const store = session.stores.find((item) => String(item.store_id) === String(storeId));
    if (!store) return false;
    return !permissionKey || store.permissions?.includes('*') || store.permissions?.includes(permissionKey);
  }, [session.stores]);

  const value = useMemo(() => ({
    status,
    isAuthenticated: status === 'authenticated',
    isChecking: status === 'checking',
    user: session.user,
    stores: session.stores,
    authnLevel: session.authnLevel,
    expiresAt: session.expiresAt,
    canAccessStore,
    getRequestState: sessionStateFromError,
    login,
    verifyMfa,
    refreshSession,
    logout,
  }), [status, session, canAccessStore, login, verifyMfa, refreshSession, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuthContext must be used inside AuthProvider');
  return context;
}

export default AuthContext;
