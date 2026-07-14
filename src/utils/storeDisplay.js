const TEST_STORE_PATTERNS = [
  /phase/i,
  /credential/i,
  /capability/i,
  /verify/i,
  /preview/i,
  /测试/i,
  /테스트/i,
  /환경/i,
  /环境/i,
];

const STATUS_LABELS = {
  active: '正常运营',
  normal: '正常运营',
  '정상': '正常运营',
  '정상 운영': '正常运营',
  '판매중': '正常运营',
  '订单受控写入测试完成': '正常运营',
  '审核中': '审核中',
  '심사중': '审核中',
  '申诉中': '申诉中',
  '판매중지': '暂停使用',
};

const REGION_LABELS = {
  KR: '韩国',
  'ko-KR': '韩国',
  Korea: '韩国',
  korea: '韩国',
};

export function isVisibleBusinessStore(store = {}) {
  if (String(store.ziniaoDirectoryStatus || store.ziniao_directory_status || '') === 'removed') return false;
  const name = String(store.name || store.storeName || '').trim();
  const manager = String(store.manager || store.ownerName || store.owner_name || store.managerName || '').trim();
  const visibleText = `${name} ${manager}`.trim();
  if (!visibleText) return true;
  return !TEST_STORE_PATTERNS.some((pattern) => pattern.test(visibleText));
}

export function normalizeStoreDisplay(store = {}) {
  const status = store.status || store.statusLabel || '';
  const region = store.region || store.country || '';
  return {
    ...store,
    status: STATUS_LABELS[status] || status || '正常运营',
    region: REGION_LABELS[region] || region || '韩国',
  };
}

export function filterVisibleBusinessStores(stores = []) {
  return stores.filter(isVisibleBusinessStore).map(normalizeStoreDisplay);
}
