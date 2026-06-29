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

export function StoreProvider({ children }) {
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreIdState] = useState(readStoredStoreId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    dataProvider.getStores({ page: 1, pageSize: 100 })
      .then((response) => {
        if (cancelled) return;
        const nextStores = response.data || response.items || [];
        setStores(nextStores);

        const storedId = readStoredStoreId();
        const storedStore = nextStores.find((store) => String(store.id) === String(storedId));
        const fallbackId = nextStores[0]?.id ? String(nextStores[0].id) : '';
        const nextSelectedId = storedStore ? String(storedStore.id) : fallbackId;
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
    loading,
    error,
    isBackendSource,
  }), [stores, selectedStore, selectedStoreId, setSelectedStoreId, loading, error]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStoreContext() {
  const context = useContext(StoreContext);
  if (!context) throw new Error('useStoreContext must be used inside StoreProvider');
  return context;
}

export default StoreContext;
