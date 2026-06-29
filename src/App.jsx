import AppRoutes from './routes';
import { StoreProvider } from './context/StoreContext';

export default function App() {
  return (
    <StoreProvider>
      <AppRoutes />
    </StoreProvider>
  );
}
