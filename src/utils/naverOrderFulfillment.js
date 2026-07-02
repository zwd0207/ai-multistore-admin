const STATUS_PRESENTATIONS = {
  PAYED: {
    label: '已付款 / 新订单',
    bucket: 'newOrders',
    bucketLabel: '新订单',
    nextAction: '需要按店铺流程确认后续发货处理。',
  },
  PLACE_PRODUCT_ORDER: {
    label: '待发货 / 已确认订单',
    bucket: 'pendingDispatch',
    bucketLabel: '待发货',
    nextAction: '需要准备发货，但当前页面不会执行平台发货写入。',
  },
  DISPATCHED: {
    label: '已发货 / 配送中',
    bucket: 'inDelivery',
    bucketLabel: '配送中',
    nextAction: '继续关注配送状态，不执行配送写操作。',
  },
  DELIVERED: {
    label: '配送完成',
    bucket: 'delivered',
    bucketLabel: '配送完成',
    nextAction: '订单已进入配送完成状态。',
  },
  CANCELED: {
    label: '已取消',
    bucket: 'canceled',
    bucketLabel: '已取消',
    nextAction: '仅做只读识别，不执行取消处理。',
  },
  CANCEL_REQUEST: {
    label: '取消请求',
    bucket: 'cancelRequests',
    bucketLabel: '取消请求',
    nextAction: '需要人工查看取消请求，不执行平台取消写操作。',
  },
  RETURN_REQUEST: {
    label: '退货请求',
    bucket: 'returnRequests',
    bucketLabel: '退货请求',
    nextAction: '需要人工查看退货请求，不执行平台退货写操作。',
  },
  EXCHANGE_REQUEST: {
    label: '换货请求',
    bucket: 'exchangeRequests',
    bucketLabel: '换货请求',
    nextAction: '需要人工查看换货请求，不执行平台换货写操作。',
  },
  PURCHASE_DECIDED: {
    label: '已确认购买',
    bucket: 'completed',
    bucketLabel: '已确认购买',
    nextAction: '订单已完成购买确认。',
  },
};

const KOREAN_STATUS_ALIASES = {
  결제완료: 'PAYED',
  발주확인: 'PLACE_PRODUCT_ORDER',
  배송중: 'DISPATCHED',
  배송완료: 'DELIVERED',
  취소: 'CANCELED',
  취소요청: 'CANCEL_REQUEST',
  반품요청: 'RETURN_REQUEST',
  교환요청: 'EXCHANGE_REQUEST',
  구매확정: 'PURCHASE_DECIDED',
};

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function normalizeText(value) {
  return String(value || '').trim();
}

export function normalizeNaverOrderStatus(value) {
  const rawValue = normalizeText(value);
  if (!rawValue) return 'UNKNOWN';
  const upperValue = rawValue.toUpperCase();
  if (upperValue === 'CANCELLED') return 'CANCELED';
  if (STATUS_PRESENTATIONS[upperValue]) return upperValue;
  return KOREAN_STATUS_ALIASES[rawValue] || 'UNKNOWN';
}

export function getNaverOrderStatusPresentation(value) {
  const normalizedStatus = normalizeNaverOrderStatus(value);
  return STATUS_PRESENTATIONS[normalizedStatus] || {
    label: '未识别状态，需人工确认',
    bucket: 'unknown',
    bucketLabel: '异常 / 未识别状态',
    nextAction: '请人工复核订单状态后再处理。',
  };
}

function isNaverOrder(order = {}) {
  return normalizePlatform(order.rawPlatform || order.platform) === 'naver';
}

function isSelectedStoreOrder(order = {}, selectedStore = {}, selectedStoreId = '') {
  const orderStoreId = order.storeId ?? order.store_id;
  if (selectedStoreId && orderStoreId !== undefined && orderStoreId !== null) {
    return String(orderStoreId) === String(selectedStoreId);
  }
  const orderStoreName = normalizeText(order.store || order.store_name);
  const selectedStoreName = normalizeText(selectedStore?.name);
  if (orderStoreName && selectedStoreName) return orderStoreName === selectedStoreName;
  return true;
}

export function filterNaverOrdersForStore(orders = [], selectedStore = {}, selectedStoreId = '') {
  return orders.filter((order) => (
    isNaverOrder(order) && isSelectedStoreOrder(order, selectedStore, selectedStoreId)
  ));
}

function rawStatusOf(order = {}) {
  return order.rawStatus || order.order_status || order.status || '';
}

function createEmptyCounts() {
  return {
    total: 0,
    newOrders: 0,
    pendingDispatch: 0,
    inDelivery: 0,
    delivered: 0,
    cancelRequests: 0,
    returnRequests: 0,
    exchangeRequests: 0,
    canceled: 0,
    completed: 0,
    unknown: 0,
  };
}

export function buildNaverOrderFulfillmentSummary(orders = [], {
  selectedStore = {},
  selectedStoreId = '',
} = {}) {
  const scopedOrders = filterNaverOrdersForStore(orders, selectedStore, selectedStoreId);
  const counts = scopedOrders.reduce((value, order) => {
    const presentation = getNaverOrderStatusPresentation(rawStatusOf(order));
    return {
      ...value,
      total: value.total + 1,
      [presentation.bucket]: value[presentation.bucket] + 1,
    };
  }, createEmptyCounts());

  const claimRequestCount = counts.cancelRequests + counts.returnRequests + counts.exchangeRequests;
  const actionNeededCount = counts.newOrders + counts.pendingDispatch + claimRequestCount + counts.unknown;
  const statusLabel = counts.total === 0
    ? '暂无本地订单'
    : actionNeededCount > 0
      ? '需要关注订单'
      : '订单状态稳定';
  const tone = counts.unknown > 0 || claimRequestCount > 0
    ? 'warning'
    : actionNeededCount > 0
      ? 'info'
      : 'success';
  const businessMessage = counts.total === 0
    ? '当前没有可用于履约 / 售后分类的 Naver 本地订单。'
    : `已只读检查 ${counts.total} 条 Naver 本地订单：新订单 ${counts.newOrders} 条，待发货 ${counts.pendingDispatch} 条，售后请求 ${claimRequestCount} 条，异常订单 ${counts.unknown} 条。`;

  return {
    ...counts,
    claimRequestCount,
    actionNeededCount,
    statusLabel,
    tone,
    businessMessage,
    source: 'local_orders_only',
    platformWritesEnabled: false,
    formalOrderSyncOpen: false,
  };
}
