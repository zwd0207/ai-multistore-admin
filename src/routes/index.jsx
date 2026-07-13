import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthPage, AuthStatePage } from '../pages/AuthPages';
import { useAuthContext } from '../context/AuthContext';

const AdminLayout = lazy(() => import('../layouts/AdminLayout'));
const Dashboard = lazy(() => import('../pages/Dashboard'));
const Stores = lazy(() => import('../pages/Stores'));
const Products = lazy(() => import('../pages/Products'));
const InventoryAlerts = lazy(() => import('../pages/InventoryAlerts'));
const Orders = lazy(() => import('../pages/Orders'));
const CustomerService = lazy(() => import('../pages/CustomerService'));
const Sales = lazy(() => import('../pages/Sales'));
const Devices = lazy(() => import('../pages/Devices'));
const Emails = lazy(() => import('../pages/Emails'));
const Appeals = lazy(() => import('../pages/Appeals'));
const Environment = lazy(() => import('../pages/Environment'));
const Accounts = lazy(() => import('../pages/Accounts'));
const Settings = lazy(() => import('../pages/Settings'));
const Logs = lazy(() => import('../pages/Logs'));
const ApiCapabilities = lazy(() => import('../pages/ApiCapabilities'));
const ShippingAssistant = lazy(() => import('../pages/ShippingAssistant'));

function DeferredPage({ children }) {
  return (
    <Suspense fallback={<div className="table-state"><span className="spinner" />正在加载页面...</div>}>
      {children}
    </Suspense>
  );
}

function RequireAuth({ children }) {
  const { status, isAuthenticated, stores } = useAuthContext();
  if (['unauthenticated', 'mfa_required'].includes(status)) return <AuthPage />;
  if (status === 'checking') return <AuthPage />;
  if (status === 'unavailable') return <AuthStatePage type="unavailable" />;
  if (status === 'expired') return <AuthStatePage type="expired" />;
  if (status === 'reauthentication_required') return <AuthStatePage type="reauthentication_required" />;
  if (status === 'forbidden' || (isAuthenticated && !stores.length)) return <AuthStatePage type="forbidden" />;
  return isAuthenticated ? children : <AuthPage />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<RequireAuth><DeferredPage><AdminLayout /></DeferredPage></RequireAuth>}>
        <Route index element={<Navigate to="/workbench" replace />} />
        <Route path="workbench" element={<DeferredPage><Dashboard /></DeferredPage>} />
        <Route path="dashboard" element={<DeferredPage><Dashboard /></DeferredPage>} />
        <Route path="stores" element={<DeferredPage><Stores /></DeferredPage>} />
        <Route path="products" element={<DeferredPage><Products /></DeferredPage>} />
        <Route path="inventory" element={<DeferredPage><InventoryAlerts /></DeferredPage>} />
        <Route path="orders" element={<DeferredPage><Orders /></DeferredPage>} />
        <Route path="shipping" element={<DeferredPage><ShippingAssistant /></DeferredPage>} />
        <Route path="customer-service" element={<DeferredPage><CustomerService /></DeferredPage>} />
        <Route path="sales" element={<DeferredPage><Sales /></DeferredPage>} />
        <Route path="devices" element={<DeferredPage><Devices /></DeferredPage>} />
        <Route path="emails" element={<DeferredPage><Emails /></DeferredPage>} />
        <Route path="appeals" element={<DeferredPage><Appeals /></DeferredPage>} />
        <Route path="environment" element={<DeferredPage><Environment /></DeferredPage>} />
        <Route path="accounts" element={<DeferredPage><Accounts /></DeferredPage>} />
        <Route path="api-capabilities" element={<DeferredPage><ApiCapabilities /></DeferredPage>} />
        <Route path="settings" element={<DeferredPage><Settings /></DeferredPage>} />
        <Route path="logs" element={<DeferredPage><Logs /></DeferredPage>} />
      </Route>
      <Route path="*" element={<Navigate to="/workbench" replace />} />
    </Routes>
  );
}
