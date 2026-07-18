import { useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import ManualStoreSyncButton from '../components/common/ManualStoreSyncButton';
import OpenStoreBackendButton from '../components/common/OpenStoreBackendButton';
import StoreSelector from '../components/common/StoreSelector';
import TenantScopeSelector from '../components/common/TenantScopeSelector';
import { BUSINESS_TIME_LABEL } from '../utils/time';
import { useAuthContext } from '../context/AuthContext';
import { useStoreContext } from '../context/StoreContext';
import { filterMenuGroupsForStore } from './menuPermissions';
import { isBackendSource } from '../services/dataSource';

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
      ['租', '租户与邀请', '/tenants', null, false],
      ['□', '店铺与平台连接', '/stores', ['store_membership.assign', 'store.manage'], false],
      ['@', '邮箱与平台通知', '/emails', ['store_membership.assign', 'store.manage']],
      ['⚙', '管理员设置', '/settings', ['store_membership.assign', 'store.manage']],
    ],
  },
];

export default function AdminLayout() {
  const location = useLocation();
  const {
    user, canAccessStore, logout, isPlatformAdmin, crossTenantMode,
  } = useAuthContext();
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [collapsed, setCollapsed] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  useEffect(() => {
    setMoreOpen(false);
  }, [location.pathname]);

  const visibleMenuGroups = useMemo(
    () => filterMenuGroupsForStore(
      menuGroups.map((group) => ({
        ...group,
        items: group.items.filter((item) => item[2] !== '/tenants' || isPlatformAdmin),
      })),
      selectedStoreId,
      canAccessStore,
    ),
    [selectedStoreId, canAccessStore, isPlatformAdmin],
  );
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
            <span className={`environment-chip data-source-chip ${isBackendSource ? 'backend' : 'mock'}`}>
              {isBackendSource ? '正式 Backend' : 'Demo / Mock 数据'}
            </span>
            <TenantScopeSelector />
            <StoreSelector />
            <OpenStoreBackendButton store={selectedStore} compact />
            <ManualStoreSyncButton />
          </div>
          <div className="topbar-actions">
            <span className="avatar">运</span>
            <span>
              <strong>{user?.display_name || user?.name || user?.login_identifier_masked || '运营人员'}</strong>
              <small>{isPlatformAdmin ? (crossTenantMode ? '平台管理员 · 跨租户管理' : '平台管理员') : '租户负责人'}</small>
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
