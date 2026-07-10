import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import ManualStoreSyncButton from '../components/common/ManualStoreSyncButton';
import StoreSelector from '../components/common/StoreSelector';
import { BUSINESS_TIME_LABEL } from '../utils/time';
import { useAuthContext } from '../context/AuthContext';

const menuGroups = [
  {
    label: '每日运营',
    items: [
      ['⌂', '今日工作台', '/workbench'],
      ['⇄', '订单处理', '/orders'],
      ['▣', '仓库发货', '/shipping'],
      ['✉', '客户咨询', '/customer-service'],
      ['§', '售后异常', '/appeals'],
    ],
  },
  {
    label: '经营管理',
    items: [
      ['◇', '商品管理', '/products'],
      ['!', '库存预警', '/inventory'],
    ],
  },
  {
    label: '管理员',
    items: [
      ['□', '店铺与平台连接', '/stores'],
      ['@', '邮箱与平台通知', '/emails'],
      ['⚙', '管理员设置', '/settings'],
    ],
  },
];

export default function AdminLayout() {
  const { user, logout } = useAuthContext();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`admin-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">ERP</span>
          {!collapsed && (
            <span>
              <strong>多店铺运营中心</strong>
              <small>订单、仓库和客户服务</small>
            </span>
          )}
        </div>
        <nav className="sidebar-nav" aria-label="主导航">
          {menuGroups.map((group) => (
            <section className="nav-group" key={group.label}>
              {!collapsed && <h2>{group.label}</h2>}
              {group.items.map(([icon, label, path]) => (
                <NavLink key={path} to={path} className={({ isActive }) => (isActive ? 'active' : '')} title={label}>
                  <span className="menu-icon">{icon}</span>
                  {!collapsed && <span>{label}</span>}
                </NavLink>
              ))}
            </section>
          ))}
        </nav>
        <button className="collapse-button" type="button" onClick={() => setCollapsed((value) => !value)}>
          {collapsed ? '展开' : '收起菜单'}
        </button>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div>
            <strong>多店铺运营中心</strong>
            <span className="environment-chip">韩国时间 {BUSINESS_TIME_LABEL}</span>
            <StoreSelector />
            <ManualStoreSyncButton />
          </div>
          <div className="topbar-actions">
            <span className="notification">3</span>
            <span className="avatar">运</span>
            <span>
              <strong>{user?.display_name || user?.name || user?.login_identifier_masked || '运营人员'}</strong>
              <small>日常运营</small>
            </span>
            <button className="button ghost compact" type="button" onClick={logout}>退出</button>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
      </section>
    </div>
  );
}
