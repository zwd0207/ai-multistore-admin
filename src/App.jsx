import AppRoutes from './routes';
import { AuthProvider } from './context/AuthContext';
import { SyncRefreshProvider } from './context/SyncRefreshContext';
import { StoreProvider } from './context/StoreContext';

export default function App() {
  return (
    <AuthProvider>
      <StoreProvider>
        <SyncRefreshProvider>
          <AppRoutes />
        </SyncRefreshProvider>
      </StoreProvider>
    </AuthProvider>
  );
}
