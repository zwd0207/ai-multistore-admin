import { useMemo, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import ManualStoreSyncButton from '../components/common/ManualStoreSyncButton';
import StoreSelector from '../components/common/StoreSelector';
import { BUSINESS_TIME_LABEL } from '../utils/time';
import { useAuthContext } from '../context/AuthContext';

const menuGroups = [
  {
    label: '每日运营',
    items: [
      ['⌂', '今日工作台', '/workbench', 'dashboard.read'],
      ['⇄', '订单处理', '/orders', 'orders.read'],
      ['▣', '仓库发货', '/shipping', 'shipping.batch.manage'],
      ['✉', '客户咨询', '/customer-service'],
      ['§', '售后异常', '/appeals'],
    ],
  },
  {
    label: '经营管理',
    items: [
      ['◇', '商品管理', '/products', 'products.read'],
      ['!', '库存预警', '/inventory', 'products.read'],
    ],
  },
  {
    label: '管理员',
    items: [
      ['□', '店铺与平台连接', '/stores', 'store_membership.assign'],
      ['@', '邮箱与平台通知', '/emails', 'store_membership.assign'],
      ['⚙', '管理员设置', '/settings', 'store_membership.assign'],
    ],
  },
];

export default function AdminLayout() {
  const { user, stores, canAccessStore, logout } = useAuthContext();
  const [collapsed, setCollapsed] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  const canAccessItem = (item) => {
    const permission = item[3];
    if (!stores.length) return false;
    return stores.some((store) => canAccessStore(store.store_id, permission));
  };

  const visibleMenuGroups = useMemo(() => menuGroups
    .map((group) => ({ ...group, items: group.items.filter(canAccessItem) }))
    .filter((group) => group.items.length), [stores, canAccessStore]);
  const primaryItems = visibleMenuGroups
    .find((group) => group.label === '每日运营')?.items.slice(0, 4) || [];
  const moreItems = visibleMenuGroups.flatMap((group) => group.items)
    .filter((item) => !primaryItems.some((primary) => primary[2] === item[2]));

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
          {visibleMenuGroups.map((group) => (
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
        <nav className="mobile-nav" aria-label="移动端主导航">
          {primaryItems.map(([icon, label, path]) => (
            <NavLink key={path} to={path} className={({ isActive }) => (isActive ? 'active' : '')}>
              <span className="mobile-nav-icon">{icon}</span><span>{label}</span>
            </NavLink>
          ))}
          <button className={`mobile-nav-more ${moreOpen ? 'active' : ''}`} type="button" aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}>
            <span className="mobile-nav-icon">⋯</span><span>更多</span>
          </button>
        </nav>
        {moreOpen ? (
          <div className="mobile-more-menu" role="menu" aria-label="更多运营功能">
            {moreItems.map(([icon, label, path]) => (
              <NavLink key={path} to={path} role="menuitem" onClick={() => setMoreOpen(false)}>
                <span className="menu-icon">{icon}</span><span>{label}</span>
              </NavLink>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
