import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import dataProvider, { isBackendSource } from '../services/dataProvider';

const STORAGE_KEY = 'codex2.selectedStoreId';
const StoreContext = createContext(null);

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
  const fallbackId = nextStores[0]?.id ? String(nextStores[0].id) : '';
  return candidateStore ? String(candidateStore.id) : fallbackId;
}

export function StoreProvider({ children }) {
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreIdState] = useState(readStoredStoreId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refreshStores = useCallback(async ({ preferredStoreId } = {}) => {
    setLoading(true);
    setError('');

    try {
      const response = await dataProvider.getStores({ page: 1, pageSize: 100 });
      const nextStores = response.data || response.items || [];
      setStores(nextStores);

      const nextSelectedId = pickSelectedStoreId(nextStores, preferredStoreId);
      setSelectedStoreIdState(nextSelectedId);
      writeStoredStoreId(nextSelectedId);
      return nextStores;
    } catch (requestError) {
      setStores([]);
      setSelectedStoreIdState('');
      setError(requestError.message || '店铺列表加载失败');
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    dataProvider.getStores({ page: 1, pageSize: 100 })
      .then((response) => {
        if (cancelled) return;
        const nextStores = response.data || response.items || [];
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
  }, []);

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
