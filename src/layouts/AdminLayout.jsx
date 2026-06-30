import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import StoreSelector from '../components/common/StoreSelector';
import { BUSINESS_TIME_LABEL } from '../utils/time';

const menuItems = [
  ['总', '总览', '/dashboard'],
  ['店', '店铺管理', '/stores'],
  ['品', '商品管理', '/products'],
  ['单', '订单管理', '/orders'],
  ['客', '客服管理', '/customer-service'],
  ['销', '销售数据', '/sales'],
  ['设', '设备管理', '/devices'],
  ['邮', '邮箱管理', '/emails'],
  ['诉', '申诉管理', '/appeals'],
  ['境', '环境管理', '/environment'],
  ['账', '账号管理', '/accounts'],
  ['API', 'API 能力确认', '/api-capabilities'],
  ['配', '系统设置', '/settings'],
  ['记', '操作日志', '/logs'],
];

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`admin-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">AI</span>
          {!collapsed && <span><strong>StorePilot</strong><small>智能运营中心</small></span>}
        </div>
        <nav className="sidebar-nav" aria-label="主导航">
          {menuItems.map(([icon, label, path]) => (
            <NavLink key={path} to={path} className={({ isActive }) => (isActive ? 'active' : '')} title={label}>
              <span className="menu-icon">{icon}</span>{!collapsed && <span>{label}</span>}
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
            <strong>AI 多店铺运营与环境管理系统</strong>
            <span className="environment-chip">演示环境</span>
            <span className="environment-chip">时间显示：{BUSINESS_TIME_LABEL}</span>
            <StoreSelector />
          </div>
          <div className="topbar-actions">
            <span className="notification">3</span>
            <span className="avatar">管</span>
            <span><strong>管理员</strong><small>系统管理员</small></span>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
      </section>
    </div>
  );
}
