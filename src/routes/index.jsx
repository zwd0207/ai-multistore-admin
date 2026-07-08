import { Navigate, Route, Routes } from 'react-router-dom';
import AdminLayout from '../layouts/AdminLayout';
import Dashboard from '../pages/Dashboard';
import Stores from '../pages/Stores';
import Products from '../pages/Products';
import InventoryAlerts from '../pages/InventoryAlerts';
import Orders from '../pages/Orders';
import CustomerService from '../pages/CustomerService';
import Sales from '../pages/Sales';
import Devices from '../pages/Devices';
import Emails from '../pages/Emails';
import Appeals from '../pages/Appeals';
import Environment from '../pages/Environment';
import Accounts from '../pages/Accounts';
import Settings from '../pages/Settings';
import Logs from '../pages/Logs';
import ApiCapabilities from '../pages/ApiCapabilities';
import ShippingAssistant from '../pages/ShippingAssistant';

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<Navigate to="/workbench" replace />} />
        <Route path="workbench" element={<Dashboard />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="stores" element={<Stores />} />
        <Route path="products" element={<Products />} />
        <Route path="inventory" element={<InventoryAlerts />} />
        <Route path="orders" element={<Orders />} />
        <Route path="shipping" element={<ShippingAssistant />} />
        <Route path="customer-service" element={<CustomerService />} />
        <Route path="sales" element={<Sales />} />
        <Route path="devices" element={<Devices />} />
        <Route path="emails" element={<Emails />} />
        <Route path="appeals" element={<Appeals />} />
        <Route path="environment" element={<Environment />} />
        <Route path="accounts" element={<Accounts />} />
        <Route path="api-capabilities" element={<ApiCapabilities />} />
        <Route path="settings" element={<Settings />} />
        <Route path="logs" element={<Logs />} />
      </Route>
      <Route path="*" element={<Navigate to="/workbench" replace />} />
    </Routes>
  );
}
