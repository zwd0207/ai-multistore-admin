import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import { isBackendSource } from '../services/dataSource';
import { filterVisibleBusinessStores } from '../utils/storeDisplay';
import { useAuthContext } from './AuthContext';

const STORAGE_KEY = 'codex2.selectedStoreId';
const StoreContext = createContext(null);

async function getStores(params) {
  const { default: dataProvider } = await import('../services/dataProvider');
  return dataProvider.getStores(params);
}

function readStoredStoreId() {
  try {
    return localStorage.getItem(STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

function writeStoredStoreId(storeId) {
  try {
    if (storeId) localStorage.setItem(STORAGE_KEY, String(storeId));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // localStorage can be unavailable in restricted browser contexts.
  }
}

function pickSelectedStoreId(nextStores, preferredStoreId) {
  const candidateId = preferredStoreId || readStoredStoreId();
  const candidateStore = nextStores.find((store) => String(store.id) === String(candidateId));
  const primaryBusinessStore = nextStores.find((store) => String(store.id) === '8' || String(store.name || '').includes('pxg球包店'));
  const fallbackId = primaryBusinessStore?.id ? String(primaryBusinessStore.id) : (nextStores[0]?.id ? String(nextStores[0].id) : '');
  return candidateStore ? String(candidateStore.id) : fallbackId;
}

export function StoreProvider({ children }) {
  const {
    isAuthenticated, refreshSession, selectedTenantId, status: authStatus,
  } = useAuthContext();
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreIdState] = useState(readStoredStoreId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refreshStores = useCallback(async ({ preferredStoreId, silent = false, forceRefresh = false } = {}) => {
    if (!silent) {
      setLoading(true);
      setError('');
    }

    try {
      const response = await getStores({ page: 1, pageSize: 100, forceRefresh });
      const nextStores = filterVisibleBusinessStores(response.data || response.items || []);
      setStores(nextStores);

      const nextSelectedId = pickSelectedStoreId(nextStores, preferredStoreId);
      setSelectedStoreIdState(nextSelectedId);
      writeStoredStoreId(nextSelectedId);
      return nextStores;
    } catch (requestError) {
      if (!silent) {
        setStores([]);
        setSelectedStoreIdState('');
        setError(requestError.message || '店铺列表加载失败');
      }
      throw requestError;
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isBackendSource && !isAuthenticated) {
      setStores([]);
      setSelectedStoreIdState('');
      setError('');
      setLoading(authStatus === 'checking');
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError('');

    getStores({ page: 1, pageSize: 100 })
      .then((response) => {
        if (cancelled) return;
        const nextStores = filterVisibleBusinessStores(response.data || response.items || []);
        const nextSelectedId = pickSelectedStoreId(nextStores);
        setStores(nextStores);
        setSelectedStoreIdState(nextSelectedId);
        writeStoredStoreId(nextSelectedId);
      })
      .catch((requestError) => {
        if (cancelled) return;
        setStores([]);
        setSelectedStoreIdState('');
        setError(requestError.message || '店铺列表加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [authStatus, isAuthenticated, selectedTenantId]);

  useEffect(() => {
    if (!isBackendSource || !isAuthenticated) return undefined;
    const timer = window.setInterval(() => {
      refreshSession()
        .then(() => refreshStores({ silent: true, forceRefresh: true }))
        .catch(() => {});
    }, 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [isAuthenticated, refreshSession, refreshStores]);

  const setSelectedStoreId = useCallback((storeId) => {
    const nextStoreId = storeId ? String(storeId) : '';
    setSelectedStoreIdState(nextStoreId);
    writeStoredStoreId(nextStoreId);
  }, []);

  const selectedStore = useMemo(
    () => stores.find((store) => String(store.id) === String(selectedStoreId)) || null,
    [stores, selectedStoreId],
  );

  const value = useMemo(() => ({
    stores,
    selectedStore,
    selectedStoreId,
    setSelectedStoreId,
    refreshStores,
    loading,
    error,
    isBackendSource,
  }), [stores, selectedStore, selectedStoreId, setSelectedStoreId, refreshStores, loading, error]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStoreContext() {
  const context = useContext(StoreContext);
  if (!context) throw new Error('useStoreContext must be used inside StoreProvider');
  return context;
}

export default StoreContext;
