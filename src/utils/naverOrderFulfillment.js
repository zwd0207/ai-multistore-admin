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
  READY: {
    label: '待发货',
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
  DELIVERING: {
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
  RETURNED: {
    label: '退货完成',
    bucket: 'completed',
    bucketLabel: '退货完成',
    nextAction: '退货状态已完成；当前仅展示本地只读状态。',
  },
  RETURN_DONE: {
    label: '退货完成',
    bucket: 'completed',
    bucketLabel: '退货完成',
    nextAction: '退货状态已完成；当前仅展示本地只读状态。',
  },
  EXCHANGE_REQUEST: {
    label: '换货请求',
    bucket: 'exchangeRequests',
    bucketLabel: '换货请求',
    nextAction: '需要人工查看换货请求，不执行平台换货写操作。',
  },
  EXCHANGED: {
    label: '换货完成',
    bucket: 'completed',
    bucketLabel: '换货完成',
    nextAction: '换货状态已完成；当前仅展示本地只读状态。',
  },
  EXCHANGE_DONE: {
    label: '换货完成',
    bucket: 'completed',
    bucketLabel: '换货完成',
    nextAction: '换货状态已完成；当前仅展示本地只读状态。',
  },
  COLLECT_REQUEST: {
    label: '售后取件请求',
    bucket: 'returnRequests',
    bucketLabel: '售后取件请求',
    nextAction: '需要人工关注售后取件请求；当前不执行平台售后写操作。',
  },
  COLLECTING: {
    label: '售后取件中',
    bucket: 'returnRequests',
    bucketLabel: '售后取件中',
    nextAction: '继续关注售后取件进度；当前不执行平台售后写操作。',
  },
  COLLECT_DONE: {
    label: '售后取件完成',
    bucket: 'completed',
    bucketLabel: '售后取件完成',
    nextAction: '售后取件已完成；当前仅展示本地只读状态。',
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

function sourceTypeOf(order = {}) {
  return normalizeText(
    order.sourceType
      || order.source_type
      || order.rawData?.source_type
      || order.raw_data?.source_type,
  ).toLowerCase();
}

export function isNaverMockSyncOrder(order = {}) {
  const sourceType = sourceTypeOf(order);
  return sourceType === 'mock_sync' || sourceType === 'local_frontend_mock';
}

export function isNaverOperationalOrder(order = {}) {
  return !isNaverMockSyncOrder(order);
}

export function normalizeNaverOrderStatus(value) {
  const rawValue = normalizeText(value);
  if (!rawValue) return 'UNKNOWN';
  const upperValue = rawValue.toUpperCase();
  if (upperValue === 'CANCELLED') return 'CANCELED';
  if (['DELIVERY_READY'].includes(upperValue)) return 'READY';
  if (['SHIPPING', 'IN_DELIVERY'].includes(upperValue)) return 'DELIVERING';
  if (['DELIVERY_COMPLETION', 'DELIVERY_COMPLETED', 'DELIVERY_COMPLETE', 'COMPLETED_DELIVERY', 'SHIPPING_COMPLETED'].includes(upperValue)) return 'DELIVERED';
  if (upperValue === 'RETURN_DONE') return 'RETURN_DONE';
  if (upperValue === 'EXCHANGE_DONE') return 'EXCHANGE_DONE';
  if (['COLLECT_REQUEST', 'COLLECTING', 'COLLECT_DONE'].includes(upperValue)) return upperValue;
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

export function filterNaverOrdersForStore(orders = [], selectedStore = {}, selectedStoreId = '', {
  includeMockSync = false,
} = {}) {
  return orders.filter((order) => (
    isNaverOrder(order)
    && isSelectedStoreOrder(order, selectedStore, selectedStoreId)
    && (includeMockSync || isNaverOperationalOrder(order))
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
  const allScopedOrders = filterNaverOrdersForStore(orders, selectedStore, selectedStoreId, { includeMockSync: true });
  const scopedOrders = allScopedOrders.filter(isNaverOperationalOrder);
  const excludedMockSyncCount = allScopedOrders.length - scopedOrders.length;
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
    : `已只读检查 ${counts.total} 条 Naver 运营订单：新订单 ${counts.newOrders} 条，待发货 ${counts.pendingDispatch} 条，售后请求 ${claimRequestCount} 条，异常订单 ${counts.unknown} 条。`;

  return {
    ...counts,
    excludedMockSyncCount,
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

export function buildNaverDeliveryStatusSummary(fulfillmentSummary = {}) {
  const total = fulfillmentSummary.total ?? 0;
  const pendingDelivery = (fulfillmentSummary.newOrders ?? 0) + (fulfillmentSummary.pendingDispatch ?? 0);
  const inDelivery = fulfillmentSummary.inDelivery ?? 0;
  const delivered = fulfillmentSummary.delivered ?? 0;
  const unknown = fulfillmentSummary.unknown ?? 0;
  const canceled = fulfillmentSummary.canceled ?? 0;
  const deliveryAttentionCount = pendingDelivery + inDelivery + unknown;
  const statusLabel = total === 0
    ? '暂无配送订单'
    : unknown > 0
      ? '配送状态需复核'
      : pendingDelivery > 0
        ? '有待发货订单'
        : inDelivery > 0
          ? '配送中'
          : '配送状态稳定';
  const tone = unknown > 0
    ? 'warning'
    : pendingDelivery > 0 || inDelivery > 0
      ? 'info'
      : total > 0
        ? 'success'
        : 'muted';
  const businessMessage = total === 0
    ? '当前没有可用于配送状态汇总的 Naver 运营订单。'
    : `已只读汇总 ${total} 条 Naver 运营订单：待发货 ${pendingDelivery} 条，配送中 ${inDelivery} 条，配送完成 ${delivered} 条，配送异常 / 未识别 ${unknown} 条。`;
  const nextAction = unknown > 0
    ? '先人工复核未识别订单状态；当前不执行发货、取消、退货或换货写操作。'
    : pendingDelivery > 0
      ? '优先处理待发货订单；发货写入 Naver 仍未开放。'
      : inDelivery > 0
        ? '继续关注配送中订单；当前只做只读展示。'
        : '配送状态暂无阻断；继续按本地订单摘要观察。';

  return {
    total,
    pendingDelivery,
    inDelivery,
    delivered,
    unknown,
    canceled,
    deliveryAttentionCount,
    statusLabel,
    tone,
    businessMessage,
    nextAction,
    source: 'local_orders_only',
    platformDeliveryWriteEnabled: false,
    formalOrderSyncOpen: false,
  };
}

export function buildNaverClaimReadonlySummary(fulfillmentSummary = {}) {
  const cancelRequests = fulfillmentSummary.cancelRequests ?? 0;
  const returnRequests = fulfillmentSummary.returnRequests ?? 0;
  const exchangeRequests = fulfillmentSummary.exchangeRequests ?? 0;
  const canceled = fulfillmentSummary.canceled ?? 0;
  const unknown = fulfillmentSummary.unknown ?? 0;
  const activeClaimRequestCount = cancelRequests + returnRequests + exchangeRequests;
  const claimAttentionCount = activeClaimRequestCount + unknown;
  const statusLabel = unknown > 0
    ? '售后状态需复核'
    : activeClaimRequestCount > 0
      ? '有售后请求'
      : canceled > 0
        ? '有已取消订单'
        : '暂无售后请求';
  const tone = unknown > 0 || activeClaimRequestCount > 0
    ? 'warning'
    : canceled > 0
      ? 'info'
      : 'success';
  const businessMessage = `已只读分类 Naver 售后状态：取消请求 ${cancelRequests} 条，退货请求 ${returnRequests} 条，换货请求 ${exchangeRequests} 条，已取消 ${canceled} 条，未识别 ${unknown} 条。`;
  const nextAction = unknown > 0
    ? '先人工复核未识别售后状态；当前不执行取消、退货或换货写操作。'
    : activeClaimRequestCount > 0
      ? '请人工查看售后请求；当前只做待办识别，不自动处理平台售后。'
      : '当前暂无需要处理的售后请求；继续按本地订单状态观察。';

  return {
    cancelRequests,
    returnRequests,
    exchangeRequests,
    canceled,
    unknown,
    activeClaimRequestCount,
    claimAttentionCount,
    statusLabel,
    tone,
    businessMessage,
    nextAction,
    source: 'local_orders_only',
    platformClaimWriteEnabled: false,
    formalOrderSyncOpen: false,
  };
}
