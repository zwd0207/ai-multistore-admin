import { filterNaverOrdersForStore, normalizeNaverOrderStatus } from './naverOrderFulfillment';
import { getKstTodayString } from './time';

function numberValue(value) {
  const numericValue = Number(value || 0);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

function orderAmount(order = {}) {
  return numberValue(order.amount ?? order.order_amount);
}

function orderQuantity(order = {}) {
  return numberValue(order.quantity);
}

function orderDate(order = {}) {
  return String(
    order.orderedAt
      || order.ordered_at
      || order.paidAt
      || order.paid_at
      || order.createdAt
      || order.created_at
      || '',
  ).slice(0, 10);
}

function textValue(...values) {
  return values.map((value) => String(value || '').trim()).find(Boolean) || '';
}

function productName(order = {}) {
  return textValue(order.productName, order.product_name, order.product, '未命名商品');
}

function storeName(order = {}) {
  return textValue(order.store, order.store_name, '当前店铺');
}

function rawStatus(order = {}) {
  return order.rawStatus || order.order_status || order.status || '';
}

function weekStart(dateText) {
  const date = new Date(`${dateText}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return dateText;
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() - day + 1);
  return date.toISOString().slice(0, 10);
}

function sumOrders(orders = []) {
  return orders.reduce((sum, order) => sum + orderAmount(order), 0);
}

function summarizeBy(orders = [], keyOf, { limit = 3 } = {}) {
  return Object.values(orders.reduce((summary, order) => {
    const key = keyOf(order);
    const current = summary[key] || {
      name: key,
      orders: 0,
      amount: 0,
      quantity: 0,
    };
    current.orders += 1;
    current.amount += orderAmount(order);
    current.quantity += orderQuantity(order);
    summary[key] = current;
    return summary;
  }, {}))
    .sort((left, right) => right.amount - left.amount || right.orders - left.orders)
    .slice(0, limit);
}

export function buildNaverOrderSalesSummary(orders = [], {
  selectedStore = {},
  selectedStoreId = '',
  today = getKstTodayString(),
} = {}) {
  const scopedOrders = filterNaverOrdersForStore(orders, selectedStore, selectedStoreId);
  const currentWeekStart = weekStart(today);
  const currentMonth = today.slice(0, 7);
  const todayOrders = scopedOrders.filter((order) => orderDate(order) === today);
  const weekOrders = scopedOrders.filter((order) => {
    const date = orderDate(order);
    return date >= currentWeekStart && date <= today;
  });
  const monthOrders = scopedOrders.filter((order) => orderDate(order).slice(0, 7) === currentMonth);
  const latestOrderedAt = scopedOrders
    .map((order) => order.orderedAt || order.ordered_at || order.createdAt || order.created_at)
    .filter(Boolean)
    .sort()
    .at(-1) || null;
  const totalOrderAmount = sumOrders(scopedOrders);
  const canceledOrders = scopedOrders.filter((order) => normalizeNaverOrderStatus(rawStatus(order)) === 'CANCELED');
  const canceledOrderAmountObserved = sumOrders(canceledOrders);
  const storeBreakdown = summarizeBy(scopedOrders, storeName);
  const productBreakdown = summarizeBy(scopedOrders, productName);

  return {
    totalOrders: scopedOrders.length,
    totalOrderAmount,
    todayOrders: todayOrders.length,
    todayOrderAmount: sumOrders(todayOrders),
    weekOrders: weekOrders.length,
    weekOrderAmount: sumOrders(weekOrders),
    monthOrders: monthOrders.length,
    monthOrderAmount: sumOrders(monthOrders),
    currency: 'KRW',
    latestOrderedAt,
    storeBreakdown,
    productBreakdown,
    canceledOrders: canceledOrders.length,
    canceledOrderAmountObserved,
    refundAmount: 0,
    cancelAmountAvailable: false,
    refundAmountAvailable: false,
    netSalesAvailable: false,
    scope: 'local_order_amount_from_orders',
    settlementAmountAvailable: false,
    profitAvailable: false,
    withdrawableBalanceAvailable: false,
    source: 'local_orders_only',
    platformSalesApiCalled: false,
    platformSettlementApiCalled: false,
    formalOrderSyncOpen: false,
    businessMessage: scopedOrders.length
      ? `当前本地 Naver 运营订单 ${scopedOrders.length} 条，订单金额合计 ${totalOrderAmount.toLocaleString()} KRW。`
      : '当前没有可用于金额统计的 Naver 运营订单。',
    refundBusinessMessage: canceledOrders.length
      ? `已观察到 ${canceledOrders.length} 条已取消订单，关联订单金额 ${canceledOrderAmountObserved.toLocaleString()} KRW；该金额不能代表退款已经确认。`
      : '当前没有已取消订单金额可观察；退款金额字段仍待后续接入。',
    boundaryMessage: '该金额只来自本地订单，不是 Naver 结算金额、利润或账户可提取资金；取消和退款金额暂不从订单金额中自动扣减。',
  };
}
