import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import ManualStoreSyncButton from '../components/common/ManualStoreSyncButton';
import StoreSelector from '../components/common/StoreSelector';
import { BUSINESS_TIME_LABEL } from '../utils/time';

const menuItems = [
  ['⌂', '首页工作台', '/workbench'],
  ['⇄', '订单管理', '/orders'],
  ['▣', '发货辅助', '/shipping'],
  ['◇', '商品管理', '/products'],
  ['!', '库存预警', '/inventory'],
  ['□', '店铺管理', '/stores'],
  ['✉', '平台消息', '/customer-service'],
  ['§', '申诉中心', '/appeals'],
  ['@', '邮箱中心', '/emails'],
  ['⚙', '系统设置', '/settings'],
];

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`admin-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">ERP</span>
          {!collapsed && (
            <span>
              <strong>多店铺电商管理后台</strong>
              <small>韩国平台日常运营</small>
            </span>
          )}
        </div>
        <nav className="sidebar-nav" aria-label="主导航">
          {menuItems.map(([icon, label, path]) => (
            <NavLink key={path} to={path} className={({ isActive }) => (isActive ? 'active' : '')} title={label}>
              <span className="menu-icon">{icon}</span>
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>
        <button className="collapse-button" type="button" onClick={() => setCollapsed((value) => !value)}>
          {collapsed ? '展开' : '收起菜单'}
        </button>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div>
            <strong>多店铺电商管理后台</strong>
            <span className="environment-chip">内部试用</span>
            <span className="environment-chip">时间 {BUSINESS_TIME_LABEL}</span>
            <StoreSelector />
            <ManualStoreSyncButton />
          </div>
          <div className="topbar-actions">
            <span className="notification">3</span>
            <span className="avatar">运</span>
            <span>
              <strong>运营管理员</strong>
              <small>普通运营视图</small>
            </span>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
      </section>
    </div>
  );
}
