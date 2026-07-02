import { filterNaverOrdersForStore } from './naverOrderFulfillment';
import { getKstTodayString } from './time';

function numberValue(value) {
  const numericValue = Number(value || 0);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

function orderAmount(order = {}) {
  return numberValue(order.amount ?? order.order_amount);
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
    scope: 'local_order_amount_from_orders',
    settlementAmountAvailable: false,
    profitAvailable: false,
    withdrawableBalanceAvailable: false,
    businessMessage: scopedOrders.length
      ? `当前本地 Naver 订单 ${scopedOrders.length} 条，订单金额合计 ${totalOrderAmount.toLocaleString()} KRW。`
      : '当前没有可用于金额统计的 Naver 本地订单。',
  };
}
