import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import StoreSelector from '../components/common/StoreSelector';
import { BUSINESS_TIME_LABEL } from '../utils/time';

const menuItems = [
  ['首', '首页工作台', '/workbench'],
  ['发', '发货辅助', '/shipping'],
  ['单', '订单管理', '/orders'],
  ['品', '商品管理', '/products'],
  ['库', '库存预警', '/inventory'],
  ['店', '店铺管理', '/stores'],
  ['消', '平台消息', '/customer-service'],
  ['诉', '申诉中心', '/appeals'],
  ['邮', '邮箱中心', '/emails'],
  ['设', '系统设置', '/settings'],
];

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`admin-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">AI</span>
          {!collapsed && (
            <span>
              <strong>AI 多店铺运营工作台</strong>
              <small>跨境电商日常运营</small>
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
        <button className="collapse-button" onClick={() => setCollapsed((value) => !value)}>
          {collapsed ? '展开' : '收起菜单'}
        </button>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div>
            <strong>AI 多店铺运营工作台</strong>
            <span className="environment-chip">内部使用</span>
            <span className="environment-chip">时间显示：{BUSINESS_TIME_LABEL}</span>
            <StoreSelector />
          </div>
          <div className="topbar-actions">
            <span className="notification">3</span>
            <span className="avatar">管</span>
            <span>
              <strong>管理员</strong>
              <small>内部运营</small>
            </span>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
      </section>
    </div>
  );
}
