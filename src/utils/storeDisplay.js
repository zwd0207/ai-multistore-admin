const TEST_STORE_PATTERNS = [
  /phase/i,
  /credential/i,
  /capability/i,
  /verify/i,
  /preview/i,
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
  const name = String(store.name || store.storeName || '').trim();
  if (!name) return true;
  return !TEST_STORE_PATTERNS.some((pattern) => pattern.test(name));
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
