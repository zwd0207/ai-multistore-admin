import assert from 'node:assert/strict';
import { filterMenuGroupsForStore } from '../src/layouts/menuPermissions.js';

const menuGroups = [
  {
    label: '每日运营',
    items: [['⌂', '今日工作台', '/workbench', 'dashboard.read']],
  },
  {
    label: '管理员',
    items: [['⚙', '管理员设置', '/settings', 'store_membership.assign']],
  },
];

const permissionByStore = {
  storeA: ['dashboard.read', 'store_membership.assign'],
  storeB: ['dashboard.read'],
};
const canAccessStore = (storeId, permission) => permissionByStore[storeId]?.includes(permission);

const desktopMenu = filterMenuGroupsForStore(menuGroups, 'storeA', canAccessStore);
assert.equal(desktopMenu.some((group) => group.label === '管理员'), true, '店铺A应显示管理员菜单');

const switchedMenu = filterMenuGroupsForStore(menuGroups, 'storeB', canAccessStore);
assert.equal(switchedMenu.some((group) => group.label === '管理员'), false, '切换到店铺B后应立即隐藏管理员菜单');

const mobileMenu = filterMenuGroupsForStore(menuGroups, 'storeB', canAccessStore);
assert.deepEqual(mobileMenu, switchedMenu, '桌面和手机必须使用相同的当前店铺权限结果');

console.log('mobile-navigation-permission contract passed');
