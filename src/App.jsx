import AppRoutes from './routes';
import { SyncRefreshProvider } from './context/SyncRefreshContext';
import { StoreProvider } from './context/StoreContext';

export default function App() {
  return (
    <StoreProvider>
      <SyncRefreshProvider>
        <AppRoutes />
      </SyncRefreshProvider>
    </StoreProvider>
  );
}
