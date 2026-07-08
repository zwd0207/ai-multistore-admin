import {
  createContext, useCallback, useContext, useMemo, useState,
} from 'react';

const SyncRefreshContext = createContext(null);

const initialVersions = {
  products: 0,
  orders: 0,
  customerInquiries: 0,
  syncLogs: 0,
  dashboard: 0,
  aiDailyContext: 0,
};

const refreshMap = {
  products: ['products', 'syncLogs', 'dashboard'],
  orders: ['orders', 'syncLogs', 'dashboard', 'aiDailyContext'],
  customerInquiries: ['customerInquiries', 'syncLogs', 'dashboard', 'aiDailyContext'],
  manualSync: ['products', 'orders', 'customerInquiries', 'syncLogs', 'dashboard', 'aiDailyContext'],
};

export function SyncRefreshProvider({ children }) {
  const [versions, setVersions] = useState(initialVersions);

  const markSynced = useCallback((type) => {
    const targets = refreshMap[type] || [];
    setVersions((current) => targets.reduce(
      (next, key) => ({ ...next, [key]: (next[key] || 0) + 1 }),
      current,
    ));
  }, []);

  const value = useMemo(() => ({ versions, markSynced }), [versions, markSynced]);

  return <SyncRefreshContext.Provider value={value}>{children}</SyncRefreshContext.Provider>;
}

export function useSyncRefresh() {
  const context = useContext(SyncRefreshContext);
  if (!context) throw new Error('useSyncRefresh must be used inside SyncRefreshProvider');
  return context;
}

export default SyncRefreshContext;
