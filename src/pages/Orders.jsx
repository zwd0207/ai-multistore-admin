import { useEffect, useMemo, useState } from 'react';
import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import TechnicalDetails from '../components/common/TechnicalDetails';
import Timeline from '../components/common/Timeline';
import { useSyncRefresh } from '../context/SyncRefreshContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
import { getNaverOrderPreviewStatus } from '../utils/capabilityStatusMapper';
import {
  buildNaverClaimReadonlySummary,
  buildNaverOrderFulfillmentSummary,
  filterNaverOrdersForStore,
  getNaverOrderStatusPresentation,
  isNaverMockSyncOrder,
} from '../utils/naverOrderFulfillment';
import { formatKstDateTimeWithLabel, getKstDateOffsetString, getKstTodayString } from '../utils/time';

const api = {
  list: dataProvider.getOrders,
  create: mockApi.createOrder,
  update: mockApi.updateOrder,
  remove: mockApi.deleteOrder,
};

const statusOptions = ['待发货', '配送中', '已完成', '取消/退款'];

const columns = [
  { key: 'orderNo', title: '订单编号', render: (value) => <strong>{value}</strong> },
  { key: 'product', title: '商品' },
  { key: 'store', title: '店铺' },
  { key: 'sourceType', title: '数据来源', render: (value, row) => sourceTypeLabel(row) },
  { key: 'customer', title: '买家' },
  { key: 'phone', title: '联系电话' },
  { key: 'amount', title: '订单金额', render: (value, row) => formatMoney(value, row.currency) },
  { key: 'status', title: '订单状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '下单时间' },
];

const fields = [
  { key: 'orderNo', label: '订单编号', required: true },
  { key: 'product', label: '商品名称', required: true },
  { key: 'store', label: '店铺', required: true },
  { key: 'customer', label: '买家', required: true },
  { key: 'amount', label: '订单金额（KRW）', type: 'number', required: true },
  { key: 'status', label: '订单状态', type: 'select', required: true, options: statusOptions },
  { key: 'createdAt', label: '下单时间', required: true, placeholder: '2026-06-29 15:00' },
];

const naverCompletePreviewWindows = [
  { value: '24h', label: '最近 24 小时' },
  { value: '3d', label: '最近 3 天' },
  { value: '7d', label: '最近 7 天' },
];

function getNaverCompletePreviewWindowLabel(value) {
  return naverCompletePreviewWindows.find((item) => item.value === value)?.label || '最近 24 小时';
}

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function firstText(...values) {
  const value = values
    .map((item) => {
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        return item.label_zh ?? item.label ?? item.name ?? item.raw ?? item.value ?? '';
      }
      if (Array.isArray(item)) return item.filter(Boolean).join(', ');
      return item;
    })
    .find((item) => item !== undefined && item !== null && String(item).trim() !== '');
  return value === undefined ? '' : String(value).trim();
}

function displayText(...values) {
  return firstText(...values) || '待接入';
}

function statusRawValue(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value.raw ?? value.value ?? '';
  }
  return value ?? '';
}

function statusLabelValue(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value.label_zh ?? value.label ?? value.name ?? '';
  }
  return value ?? '';
}

function businessStatusDisplay(...values) {
  const raw = values
    .map(statusRawValue)
    .find((item) => item !== undefined && item !== null && String(item).trim() !== '');
  const presentation = raw ? getNaverOrderStatusPresentation(raw) : null;
  if (presentation && presentation.bucket !== 'unknown') return presentation.label;
  const label = values
    .map(statusLabelValue)
    .find((item) => item !== undefined && item !== null && String(item).trim() !== '');
  return label ? String(label).trim() : '待接入';
}

function isUnknownStatusDisplay(value) {
  const text = String(value || '');
  return text.includes('未识别') || text.toLowerCase().includes('unknown');
}

function safeDateTime(value) {
  return value ? formatKstDateTimeWithLabel(value) : '待接入';
}

function formatMoney(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function paymentStatusLabel(value) {
  const normalized = String(value || '').trim().toUpperCase();
  const labels = {
    PAID: '已付款',
    PAYED: '已付款',
    PAYMENT_WAITING: '待付款',
    CANCELED: '已取消',
    CANCELLED: '已取消',
    REFUNDED: '已退款',
  };
  return labels[normalized] || value;
}

function sourceTypeLabel(order = {}) {
  if (isNaverMockSyncOrder(order)) return '测试数据';
  const sourceType = firstText(order.sourceType, order.source_type, order.rawData?.source_type, order.raw_data?.source_type);
  if (sourceType === 'naver_real_order_sync') return '运营订单';
  return sourceType || '本地订单';
}

function businessReadableSummary(value = '') {
  return String(value)
    .replace('已只读检查', '已汇总')
    .replace('已只读汇总', '已汇总')
    .replace('已只读分类', '已整理')
    .replace('当前只做只读展示', '当前仅展示状态')
    .replace('继续按本地订单状态观察', '继续关注本地订单状态');
}

function paginateRows(rows = [], page = 1, pageSize = 5) {
  const safePage = Math.max(Number(page) || 1, 1);
  const safePageSize = Math.max(Number(pageSize) || 5, 1);
  const start = (safePage - 1) * safePageSize;
  return rows.slice(start, start + safePageSize);
}

function getDeliveryDisplayText(complete = {}, order = {}) {
  const directLabel = businessStatusDisplay(
    complete.deliveryStatus,
    complete.delivery_status,
    order.deliveryStatus,
    order.delivery_status,
    complete.deliveryStatusLabelZh,
    complete.delivery_status_label_zh,
    order.deliveryStatusLabelZh,
    order.delivery_status_label_zh,
  );
  if (directLabel && directLabel !== '待接入' && !isUnknownStatusDisplay(directLabel)) {
    return directLabel;
  }
  return businessStatusDisplay(
    complete.orderStatus,
    complete.order_status,
    order.rawStatus,
    order.order_status,
    complete.orderStatusLabelZh,
    complete.order_status_label_zh,
    order.status,
    directLabel,
  );
}

function getCompleteOrderFields(order = {}, previewFields = {}) {
  const rawData = order.rawData || order.raw_data || {};
  const complete = previewFields || {};
  return {
    orderNo: displayText(complete.externalOrderId, complete.external_order_id, order.fullOrderNo, order.orderNo, order.external_order_id),
    productOrderNo: displayText(complete.externalProductOrderId, complete.external_product_order_id, order.productOrderNo, order.external_product_order_id, rawData.external_product_order_id),
    platformProductId: displayText(complete.platformProductId, complete.platform_product_id, order.platformProductId, order.platform_product_id, rawData.platform_product_id),
    productName: displayText(complete.productName, complete.product_name, order.productName, order.product, order.product_name),
    optionName: displayText(complete.optionName, complete.option_name, order.optionName, order.option_name, rawData.option_name),
    quantity: displayText(complete.quantity, order.quantity),
    amount: formatMoney(complete.orderAmount ?? complete.order_amount ?? order.amount ?? order.order_amount, complete.currency || order.currency),
    orderStatus: businessStatusDisplay(complete.orderStatus, complete.order_status, order.rawStatus, order.order_status, complete.orderStatusLabelZh, complete.order_status_label_zh, order.status),
    paymentStatus: displayText(paymentStatusLabel(complete.paymentStatus || complete.payment_status || order.paymentStatus || order.payment_status)),
    deliveryStatus: getDeliveryDisplayText(complete, order),
    claimStatus: businessStatusDisplay(complete.claimStatus, complete.claim_status, order.claimStatus, order.claim_status, complete.claimStatusLabelZh, complete.claim_status_label_zh, order.claimStatusLabelZh, order.claim_status_label_zh),
    buyerName: displayText(complete.buyerName, complete.buyer_name, order.buyerName, order.buyer_name, order.customerName, order.customer),
    buyerPhone: displayText(complete.buyerPhone, complete.buyer_phone, order.buyerPhone, order.buyer_phone, order.phone),
    receiverName: displayText(complete.receiverName, complete.receiver_name, order.receiverName, order.receiver_name),
    receiverPhone: displayText(complete.receiverPhone, complete.receiver_phone, order.receiverPhone, order.receiver_phone),
    receiverAddress: displayText(complete.receiverAddress, complete.receiver_address, order.receiverAddress, order.receiver_address),
    zipCode: displayText(complete.zipCode, complete.zip_code, order.zipCode, order.zip_code),
    orderedAt: safeDateTime(complete.orderedAt || complete.ordered_at || order.ordered_at || order.createdAt || order.created_at),
    paidAt: safeDateTime(complete.paidAt || complete.paid_at || order.paid_at || order.paidAt),
    sourceType: sourceTypeLabel(order),
    mappingVersion: displayText(complete.mappingVersion, complete.mapping_version, order.mappingVersion, rawData.mapping_version),
    rawResponseSaved: complete.rawResponseSaved ?? complete.raw_response_saved ?? order.rawResponseSaved ?? rawData.raw_response_saved ?? false,
  };
}

function getOrderTimelineSource(order = {}) {
  const rawData = order.rawData || order.raw_data || {};
  const candidates = [
    order.statusEvents,
    order.status_events,
    order.orderStatusEvents,
    order.order_status_events,
    order.timelineEvents,
    order.timeline_events,
    rawData.status_events,
    rawData.order_status_events,
    rawData.timeline_events,
    rawData.timeline,
  ];
  const source = candidates.find((item) => Array.isArray(item) && item.length)
    || candidates.find((item) => Array.isArray(item));
  return Array.isArray(source) ? source : [];
}

function buildTimelineDescription(event = {}) {
  const orderLabel = businessStatusDisplay(event.order_status, event.order_status_raw, event.status_raw, event.order_status_label_zh, event.status_label_zh, event.statusLabelZh, event.status);
  const deliveryLabel = businessStatusDisplay(event.delivery_status, event.delivery_status_raw, event.delivery_status_label_zh, event.deliveryStatusLabelZh);
  const claimLabel = businessStatusDisplay(event.claim_status, event.claim_status_raw, event.claim_status_label_zh, event.claimStatusLabelZh);
  const parts = [
    orderLabel && `订单状态：${orderLabel}`,
    deliveryLabel && `配送：${deliveryLabel}`,
    claimLabel && `售后：${claimLabel}`,
  ].filter(Boolean);
  return firstText(event.description, event.business_message, event.message, parts.join('；')) || '已记录一条订单状态变化。';
}

function normalizeOrderStatusTimelineEvents(order = {}) {
  return getOrderTimelineSource(order).map((event, index) => ({
    id: firstText(event.id, event.event_id, event.dedupe_key, event.dedupeKey, `order-status-event-${index}`),
    title: firstText(
      event.title,
      event.event_label_zh,
      event.eventLabelZh,
      event.order_status_label_zh,
      event.status_label_zh,
      event.statusLabelZh,
      '订单状态记录',
    ),
    status: businessStatusDisplay(event.status, event.order_status, event.status_raw, event.order_status_raw, event.status_label_zh, event.order_status_label_zh, event.statusLabelZh),
    description: buildTimelineDescription(event),
    time: firstText(event.observed_at, event.observedAt, event.event_time, event.eventTime, event.created_at, event.time),
    technical: {
      eventType: firstText(event.event_type, event.eventType),
      orderStatusRaw: firstText(event.order_status_raw, event.orderStatusRaw, event.order_status, event.status_raw, event.statusRaw),
      deliveryStatusRaw: firstText(event.delivery_status_raw, event.deliveryStatusRaw, event.delivery_status),
      claimStatusRaw: firstText(event.claim_status_raw, event.claimStatusRaw, event.claim_status),
      observedAt: firstText(event.observed_at, event.observedAt, event.event_time, event.eventTime, event.created_at, event.time),
      sourcePhase: firstText(event.source_phase, event.sourcePhase),
      sourceType: firstText(event.source_type, event.sourceType),
      mappingVersion: firstText(event.mapping_version, event.mappingVersion),
      dedupeKey: firstText(event.dedupe_key, event.dedupeKey),
      rawResponseSaved: event.raw_response_saved ?? event.rawResponseSaved ?? false,
      privacyFieldsRedacted: event.privacy_fields_redacted ?? event.privacyFieldsRedacted ?? true,
    },
  }));
}

function buildOrderTimelineTechnicalItems(activeOrder = {}, fields = {}, timelineEvents = []) {
  const rawData = activeOrder.rawData || activeOrder.raw_data || {};
  const eventItems = timelineEvents.flatMap((event, index) => ([
    { label: `event_${index + 1}_event_type`, value: event.technical.eventType },
    { label: `event_${index + 1}_order_status_raw`, value: event.technical.orderStatusRaw },
    { label: `event_${index + 1}_delivery_status_raw`, value: event.technical.deliveryStatusRaw },
    { label: `event_${index + 1}_claim_status_raw`, value: event.technical.claimStatusRaw },
    { label: `event_${index + 1}_observed_at`, value: event.technical.observedAt },
    { label: `event_${index + 1}_source_phase`, value: event.technical.sourcePhase },
    { label: `event_${index + 1}_source_type`, value: event.technical.sourceType },
    { label: `event_${index + 1}_mapping_version`, value: event.technical.mappingVersion },
    { label: `event_${index + 1}_dedupe_key`, value: event.technical.dedupeKey },
    { label: `event_${index + 1}_raw_response_saved`, value: event.technical.rawResponseSaved },
    { label: `event_${index + 1}_privacy_fields_redacted`, value: event.technical.privacyFieldsRedacted },
  ]));

  return [
    { label: 'timeline_display_phase', value: 'Naver-ERP-14J' },
    { label: 'display_only', value: true },
    { label: 'order_status_events_rendered', value: timelineEvents.length },
    { label: 'selected_order_status_raw', value: activeOrder.rawStatus || activeOrder.order_status || rawData.order_status },
    { label: 'selected_delivery_status_raw', value: activeOrder.deliveryStatus || activeOrder.delivery_status || rawData.delivery_status },
    { label: 'selected_claim_status_raw', value: activeOrder.claimStatus || activeOrder.claim_status || rawData.claim_status },
    { label: 'current_mapping_version', value: fields.mappingVersion },
    { label: 'raw_response_saved', value: fields.rawResponseSaved },
    { label: 'event_write_enabled', value: false },
    { label: 'orders_write_enabled', value: false },
    { label: 'formal_order_sync_open', value: false },
    ...eventItems,
  ];
}

function isUsableOrderIdentity(value) {
  const text = String(value || '').trim();
  return Boolean(text && text !== '待接入' && text !== '订单编号已脱敏');
}

function normalizeOrderIdentity(value) {
  return String(value || '').trim();
}

function buildNaverOrderIdentityMatch(activeOrder, previewResult) {
  const rawData = activeOrder?.rawData || activeOrder?.raw_data || {};
  const previewFields = previewResult?.completeFields || {};
  const detailPreview = previewResult?.detailPreview || {};
  const localProductOrderHash = normalizeOrderIdentity(
    activeOrder?.productOrderHash
    || rawData.external_product_order_id_hash
    || activeOrder?.orderHash
    || rawData.external_order_id_hash,
  );
  const previewProductOrderHash = normalizeOrderIdentity(
    detailPreview.externalProductOrderIdHash
    || detailPreview.productOrderIdHash,
  );
  const localProductOrderNo = normalizeOrderIdentity(
    activeOrder?.productOrderNo
    || activeOrder?.external_product_order_id
    || rawData.external_product_order_id,
  );
  const previewProductOrderNo = normalizeOrderIdentity(
    previewFields.externalProductOrderId
    || previewFields.external_product_order_id,
  );

  if (!previewResult) {
    return {
      state: 'pending',
      matched: false,
      comparable: false,
      method: 'none',
      label: '等待最近订单核对',
      detail: '需要先查看最近订单完整信息，才能确认是否命中当前选中的本地订单。',
    };
  }

  if (!previewResult.available) {
    return {
      state: 'blocked',
      matched: false,
      comparable: false,
      method: 'none',
      label: '最近订单不可用',
      detail: '当前时间窗口没有可核对的订单详情，不能进入刷新审核。',
    };
  }

  if (localProductOrderHash && previewProductOrderHash) {
    const matched = localProductOrderHash === previewProductOrderHash;
    return {
      state: matched ? 'ready' : 'blocked',
      matched,
      comparable: true,
      method: 'hash',
      label: matched ? '订单身份一致' : '订单身份不一致',
      detail: matched
        ? '最近订单与当前本地运营订单一致。'
        : '最近订单与当前选中的本地运营订单不一致，不能进入刷新审核。',
    };
  }

  if (isUsableOrderIdentity(localProductOrderNo) && isUsableOrderIdentity(previewProductOrderNo)) {
    const matched = localProductOrderNo === previewProductOrderNo;
    return {
      state: matched ? 'ready' : 'blocked',
      matched,
      comparable: true,
      method: 'full_product_order_id',
      label: matched ? '订单身份一致' : '订单身份不一致',
      detail: matched
        ? '最近订单号与当前本地运营订单一致。'
        : '最近订单号与当前选中的本地运营订单不一致，不能进入刷新审核。',
    };
  }

  return {
    state: 'blocked',
    matched: false,
    comparable: false,
    method: 'unresolved',
    label: '订单身份无法确认',
    detail: '缺少可比较的订单标识，不能进入刷新审核。',
  };
}

function buildNaverOrderRefreshGatePlan({
  activeOrder,
  previewAllowed,
  previewResult,
  previewWindow,
  previewWindowLabel,
}) {
  const hasPreviewResult = Boolean(previewResult);
  const previewAvailable = Boolean(previewResult?.available);
  const selectedOperationalOrder = Boolean(activeOrder && !isNaverMockSyncOrder(activeOrder));
  const identityMatch = buildNaverOrderIdentityMatch(activeOrder, previewResult);
  const savePlan = previewResult?.savePlan || {};
  const noLocalWrites = !savePlan.ordersWritten && !savePlan.syncLogWritten && !savePlan.testedSuccessWritten;
  const noPlatformWrites = !savePlan.platformWritesEnabled && !savePlan.formalOrderSyncOpen;
  const rawResponseClosed = !savePlan.rawResponseSaved;

  let statusKind = 'pending';
  let statusLabel = '等待核对';
  let message = `先查看${previewWindowLabel}的最近订单完整信息，再由人工决定是否进入后续刷新审核。`;

  if (!previewAllowed) {
    statusKind = 'blocked';
    statusLabel = '当前店铺暂不可核对';
    message = '当前店铺暂未开放最近订单完整信息核对。';
  } else if (!activeOrder) {
    statusKind = 'pending';
    statusLabel = '等待本地订单';
    message = '当前没有可选择的 Naver 本地运营订单。';
  } else if (!selectedOperationalOrder) {
    statusKind = 'blocked';
    statusLabel = '不可刷新';
    message = '当前选中的是测试订单或非运营订单，不能进入刷新审核。';
  } else if (hasPreviewResult && !previewAvailable) {
    statusKind = 'blocked';
    statusLabel = '不可刷新';
    message = '当前时间窗口没有可核对的最近订单详情。';
  } else if (previewAvailable && !identityMatch.matched) {
    statusKind = 'blocked';
    statusLabel = '不可刷新';
    message = `${identityMatch.label}：${identityMatch.detail}`;
  } else if (previewAvailable) {
    statusKind = 'review';
    statusLabel = '可进入人工复核';
    message = '最近订单可用且订单身份一致；后续如要刷新本地订单，必须单独批准并先备份数据库。';
  }

  const canEnterManualReview = statusKind === 'review'
    && identityMatch.matched
    && noLocalWrites
    && noPlatformWrites
    && rawResponseClosed;

  return {
    statusKind,
    statusLabel,
    message,
    canEnterManualReview,
    businessMessage: canEnterManualReview
      ? '已具备进入人工复核的前置条件，但本页面不会自动刷新本地订单。'
      : message,
    items: [
      { label: '店铺与连接资料范围', state: previewAllowed ? 'ready' : 'blocked', detail: previewAllowed ? '当前店铺允许进行最近订单核对。' : '当前店铺不允许进入该核对流程。' },
      { label: '本地运营订单选择', state: selectedOperationalOrder ? 'ready' : (activeOrder ? 'blocked' : 'pending'), detail: selectedOperationalOrder ? '已选中 1 条本地运营订单。' : '需要先有 1 条可审核的 Naver 运营订单。' },
      { label: '最近订单完整信息', state: previewAvailable ? 'ready' : (hasPreviewResult ? 'blocked' : 'pending'), detail: previewAvailable ? `已取得${previewResult.previewWindowLabel || previewWindowLabel}最近订单完整信息。` : `尚未取得可用订单详情，当前窗口为${previewWindowLabel}。` },
      { label: '订单身份匹配', state: identityMatch.state, detail: identityMatch.detail },
      { label: '数据库备份', state: 'review', detail: '后续刷新前必须先备份 codex1.db，本阶段未执行。' },
      { label: '人工批准', state: 'review', detail: '后续刷新必须由人工单独批准，本页面不会触发。' },
      { label: '刷新字段白名单', state: previewAvailable ? 'review' : 'pending', detail: '后续只允许刷新订单状态、付款、配送、售后、金额、时间和安全商品字段。' },
      { label: '本地写入边界', state: noLocalWrites ? 'ready' : 'blocked', detail: '本页面不写本地订单，不写日志，不新增平台能力测试记录。' },
      { label: '平台写操作边界', state: noPlatformWrites ? 'ready' : 'blocked', detail: '不执行发货、取消、退货、换货、退款或其他平台订单写操作。' },
      { label: '原始响应边界', state: rawResponseClosed ? 'ready' : 'blocked', detail: '不保存 Naver 原始响应、平台密钥、临时授权、请求头或签名。' },
    ],
    technical: {
      phase: 'Naver-ERP-9D',
      plannedOnly: true,
      selectedOperationalOrder,
      previewAvailable,
      identityMatchState: identityMatch.state,
      identityMatched: identityMatch.matched,
      identityComparable: identityMatch.comparable,
      identityMatchMethod: identityMatch.method,
      previewWindow: previewResult?.previewWindow || previewWindow,
      requiresUserApproval: true,
      requiresDbBackup: true,
      realSyncAllowed: false,
      ordersWriteAllowed: false,
      syncLogWriteAllowed: false,
      testedSuccessWriteAllowed: false,
      platformWriteAllowed: false,
      rawResponseSaved: false,
      formalOrderSyncOpen: false,
    },
  };
}

function formatError(error) {
  const code = error?.errorCode || error?.data?.error_code || '';
  const messages = {
    REAL_API_TEST_DISABLED: '后端真实只读开关未开启，本次没有访问平台。',
    real_api_test_disabled: '后端真实只读开关未开启，本次没有访问平台。',
    ip_not_allowed: '服务器 IP 不在平台白名单内，请联系管理员处理。',
    auth_failed: '平台授权失败，请检查连接资料、权限或 IP 白名单。',
    CREDENTIAL_DECRYPT_FAILED: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
    decrypt_failed: '本地连接资料解密失败，请联系管理员重新保存连接资料。',
  };
  return messages[code] || error?.message || '订单请求失败，请检查后端服务状态。';
}

function validateWindow(startDate, endDate, maxPages) {
  if (!startDate || !endDate) return '请选择开始日期和结束日期。';
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '日期格式无效。';
  if (start > end) return '开始日期不能晚于结束日期。';
  const daySpan = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
  if (daySpan > 3) return '单次订单查询窗口最多 3 天。';
  if (Number(maxPages) < 1 || Number(maxPages) > 3) return '单次最多读取 3 页。';
  return '';
}

function ResultGrid({ result, mode }) {
  if (!result) return null;
  const isPreview = mode === 'preview';
  const createCount = Number(isPreview ? result.wouldCreate : result.createdCount || 0);
  const updateCount = Number(isPreview ? result.wouldUpdate : result.updatedCount || 0);
  const skippedCount = Number(result.skippedCount || 0);

  return (
    <div className="coupang-sync-result">
      <div className="sync-result-banner">
        {isPreview
          ? `订单预览完成：预计新增 ${createCount} 条，预计更新 ${updateCount} 条。`
          : `本地订单写入完成：新增 ${createCount} 条，更新 ${updateCount} 条，跳过 ${skippedCount} 条。`}
      </div>
      <TechnicalDetails
        items={[
          { label: 'would_create', value: result.wouldCreate },
          { label: 'would_update', value: result.wouldUpdate },
          { label: 'created_count', value: result.createdCount },
          { label: 'updated_count', value: result.updatedCount },
          { label: 'skipped_count', value: result.skippedCount },
          { label: 'page_count', value: result.pageCount },
          { label: 'next_cursor_exists', value: result.nextCursorExists },
          { label: 'date_window', value: `${result.startDate} ~ ${result.endDate}` },
          { label: 'KST_window', value: `${formatKstDateTimeWithLabel(result.windowStartAt)} / ${formatKstDateTimeWithLabel(result.windowEndAt)}` },
          { label: 'sample_ids', value: result.sampleIds?.length ? result.sampleIds.join(', ') : '[]' },
        ]}
      />
    </div>
  );
}

function CoupangOrderSyncPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const { markSynced } = useSyncRefresh();
  const [form, setForm] = useState({
    startDate: getKstDateOffsetString(-2),
    endDate: getKstTodayString(),
    maxPages: 1,
  });
  const [mode, setMode] = useState('');
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loadingAction, setLoadingAction] = useState('');

  const isCoupangStore = normalizePlatform(selectedStore?.platform) === 'coupang';
  const validationError = useMemo(
    () => validateWindow(form.startDate, form.endDate, form.maxPages),
    [form.endDate, form.maxPages, form.startDate],
  );

  if (!isCoupangStore) return null;

  const run = async (action) => {
    setMessage('');
    setError('');
    setResult(null);
    setMode(action);

    if (!isBackendSource) {
      setMessage('mock 模式只展示页面效果，不执行真实平台订单读取。');
      return;
    }
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoadingAction(action);
    try {
      const payload = {
        storeId: selectedStoreId,
        startDate: form.startDate,
        endDate: form.endDate,
        maxPages: Number(form.maxPages),
      };
      const nextResult = action === 'preview'
        ? await dataProvider.previewCoupangOrders(payload)
        : await dataProvider.syncCoupangOrders(payload);
      setResult(nextResult);
      setMessage(action === 'preview'
        ? '订单预览已完成，本次只估算影响，不写入本地订单。'
        : '订单已写入本地数据库，不会对 Coupang 平台做写操作。');
      if (action === 'sync') markSynced('orders');
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoadingAction('');
    }
  };

  return (
    <section className="content-card coupang-order-sync-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Coupang 订单读取</h2>
          <p>先查看指定日期内是否有订单，再按需写入本地。不会修改 Coupang 平台订单。</p>
        </div>
        <span className="period-chip">{selectedStore?.name || 'Coupang 店铺'}</span>
      </div>

      <div className="sync-control-grid">
        <label>
          <span>开始日期</span>
          <input type="date" value={form.startDate} onChange={(event) => setForm({ ...form, startDate: event.target.value })} />
        </label>
        <label>
          <span>结束日期</span>
          <input type="date" value={form.endDate} onChange={(event) => setForm({ ...form, endDate: event.target.value })} />
        </label>
        <label>
          <span>最多读取页数</span>
          <input type="number" min="1" max="3" value={form.maxPages} onChange={(event) => setForm({ ...form, maxPages: Number(event.target.value) })} />
        </label>
        <div className="sync-action-row">
          <button className="button ghost" onClick={() => run('preview')} disabled={Boolean(loadingAction)}>预览订单</button>
          <button className="button primary" onClick={() => run('sync')} disabled={Boolean(loadingAction)}>写入本地</button>
        </div>
      </div>

      <p className="mock-sync-note">单次日期窗口最多 3 天，最多读取 3 页。页面不显示平台密钥、临时授权、请求签名或订单原始响应。</p>
      {validationError && <div className="sync-inline-warning">{validationError}</div>}
      {loadingAction && <div className="sync-inline-warning">{loadingAction === 'preview' ? '正在预览订单...' : '正在写入本地订单...'}</div>}
      {message && <div className="mock-sync-success">{message}</div>}
      {error && <div className="mock-sync-error">{error}</div>}
      <ResultGrid result={result} mode={mode} />
    </section>
  );
}

function NaverOrderPreviewStatusPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [orders, setOrders] = useState([]);
  const [orderListMeta, setOrderListMeta] = useState({ testOrdersExcluded: 0 });
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setOrders([]);
      setOrderListMeta({ testOrdersExcluded: 0 });
      return undefined;
    }
    let cancelled = false;
    dataProvider.getOrders({
      storeId: selectedStoreId,
      platform: 'naver',
      page: 1,
      pageSize: 100,
    })
      .then((orderResponse) => {
        if (!cancelled) {
          setOrders(orderResponse.data || orderResponse.items || []);
          setOrderListMeta({ testOrdersExcluded: Number(orderResponse.testOrdersExcluded || 0) });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOrders([]);
          setOrderListMeta({ testOrdersExcluded: 0 });
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId]);

  if (!isNaverStore) return null;

  const status = getNaverOrderPreviewStatus();
  const allNaverOrders = filterNaverOrdersForStore(orders, selectedStore, selectedStoreId, { includeMockSync: true });
  const fulfillmentSummary = buildNaverOrderFulfillmentSummary(orders, { selectedStore, selectedStoreId });
  const claimSummary = buildNaverClaimReadonlySummary(fulfillmentSummary);
  const fulfillmentBusinessMessage = businessReadableSummary(fulfillmentSummary.businessMessage);
  const claimBusinessMessage = businessReadableSummary(claimSummary.businessMessage);
  const claimNextAction = businessReadableSummary(claimSummary.nextAction);
  const operationalOrderCount = fulfillmentSummary.total;
  const isolatedTestOrderCount = fulfillmentSummary.excludedMockSyncCount + orderListMeta.testOrdersExcluded;
  const localOrderCount = operationalOrderCount + isolatedTestOrderCount;
  const orderStageMessage = operationalOrderCount > 0
    ? `当前本地可见 ${operationalOrderCount} 条 Naver 运营订单，详情区可查看完整订单信息。正式订单批量同步仍未开放。`
    : '当前没有可展示的 Naver 运营订单。正式订单批量同步仍未开放。';

  return (
    <section className="content-card naver-preview-status-panel">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 订单概览</h2>
          <p>{orderStageMessage}</p>
        </div>
        <span className="period-chip">{selectedStore?.name || 'Naver 店铺'}</span>
      </div>
      <div className="business-capability-grid compact">
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>本地运营订单</strong>
            <span>{operationalOrderCount} 条</span>
          </div>
          <p>主列表和 Dashboard 只统计运营订单，测试数据已隔离。</p>
          <small>当前隔离测试数据 {isolatedTestOrderCount} 条，不混入业务摘要。</small>
        </article>
        <article className={`business-capability-card ${fulfillmentSummary.tone}`}>
          <div className="business-capability-head">
            <strong>履约 / 售后状态</strong>
            <span>{fulfillmentSummary.statusLabel}</span>
          </div>
          <p>{fulfillmentBusinessMessage}</p>
          <small>状态来自本地订单，不执行平台发货、取消、退货或换货写操作。</small>
        </article>
        <article className="business-capability-card info">
          <div className="business-capability-head">
            <strong>新订单 / 待发货</strong>
            <span>{fulfillmentSummary.newOrders + fulfillmentSummary.pendingDispatch} 条</span>
          </div>
          <p>新订单 {fulfillmentSummary.newOrders} 条，待发货 {fulfillmentSummary.pendingDispatch} 条。</p>
          <small>不会把已付款订单误显示为已发货。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>配送状态</strong>
            <span>{fulfillmentSummary.inDelivery + fulfillmentSummary.delivered} 条</span>
          </div>
          <p>配送中 {fulfillmentSummary.inDelivery} 条，配送完成 {fulfillmentSummary.delivered} 条。</p>
          <small>当前只展示配送状态，不接入配送写接口。</small>
        </article>
        <article className={`business-capability-card ${claimSummary.tone}`}>
          <div className="business-capability-head">
            <strong>取消 / 退货 / 换货</strong>
            <span>{claimSummary.statusLabel}</span>
          </div>
          <p>{claimBusinessMessage}</p>
          <small>{claimNextAction}</small>
        </article>
        <article className={fulfillmentSummary.unknown > 0 ? 'business-capability-card warning' : 'business-capability-card muted'}>
          <div className="business-capability-head">
            <strong>异常订单</strong>
            <span>{fulfillmentSummary.unknown} 条</span>
          </div>
          <p>{fulfillmentSummary.unknown > 0 ? '存在未识别状态，需要人工确认。' : '当前没有未识别订单状态。'}</p>
          <small>未知状态不会进入平台写操作。</small>
        </article>
        <article className="business-capability-card success">
          <div className="business-capability-head">
            <strong>详情展示</strong>
            <span>可查看详情</span>
          </div>
          <p>订单详情区可以查看完整订单号、商品编号、买家和收件信息。</p>
          <small>Dashboard 和主列表保持摘要口径。</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>正式订单同步</strong>
            <span>未开放</span>
          </div>
          <p>{status.sync.reason}</p>
          <small>批量同步、发货、取消、退货、换货写操作都需要单独确认。</small>
        </article>
      </div>
      <TechnicalDetails
        description="技术状态仅供管理员排查，普通卖家页面默认不展示。"
        items={[
          { label: 'orders_store8', value: localOrderCount },
          { label: 'naver_orders_scoped_total', value: allNaverOrders.length },
          { label: 'operational_orders_visible', value: operationalOrderCount },
          { label: 'mock_sync_orders_isolated', value: isolatedTestOrderCount },
          { label: 'source_type', value: 'naver_real_order_sync' },
          { label: 'post_write_preview_status', value: 'success' },
          { label: 'local_sync_result.status', value: 'not_requested' },
          { label: 'raw_response_saved', value: false },
          { label: 'privacy_fields_redacted', value: true },
          { label: 'address_saved', value: false },
          { label: 'fulfillment.total', value: operationalOrderCount },
          { label: 'fulfillment.new_orders', value: fulfillmentSummary.newOrders },
          { label: 'fulfillment.pending_dispatch', value: fulfillmentSummary.pendingDispatch },
          { label: 'fulfillment.in_delivery', value: fulfillmentSummary.inDelivery },
          { label: 'fulfillment.delivered', value: fulfillmentSummary.delivered },
          { label: 'fulfillment.cancel_requests', value: fulfillmentSummary.cancelRequests },
          { label: 'fulfillment.return_requests', value: fulfillmentSummary.returnRequests },
          { label: 'fulfillment.exchange_requests', value: fulfillmentSummary.exchangeRequests },
          { label: 'fulfillment.unknown', value: fulfillmentSummary.unknown },
          { label: 'claim.active_request_count', value: claimSummary.activeClaimRequestCount },
          { label: 'claim.platform_claim_write_enabled', value: claimSummary.platformClaimWriteEnabled },
          { label: 'platform_writes_enabled', value: fulfillmentSummary.platformWritesEnabled },
          { label: 'formal_order_sync_status', value: 'not_open' },
        ]}
      />
      <p className="mock-sync-note">订单详情区可受控展示完整订单号、商品编号和买家信息；平台密钥、临时授权、请求签名和订单原始响应不会展示。</p>
    </section>
  );
}

function NaverRoleAwareActionVisibilityPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [permissionState, setPermissionState] = useState({
    loading: false,
    readCheck: null,
    approvalRequiredCheck: null,
    adminApprovalMock: null,
    error: '',
  });
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setPermissionState({
        loading: false,
        readCheck: null,
        approvalRequiredCheck: null,
        adminApprovalMock: null,
        error: '',
      });
      return undefined;
    }

    let cancelled = false;
    const storeId = Number(selectedStoreId);
    setPermissionState((current) => ({ ...current, loading: true, error: '' }));

    Promise.all([
      dataProvider.checkPermissionMock({
        actorContext: { actor_id: 'local-operator', role: 'operator', store_ids: [storeId] },
        storeId,
        operationKey: 'orders.read',
      }),
      dataProvider.checkSensitiveActionPermissionMock({
        actorContext: { actor_id: 'local-admin', role: 'admin', store_ids: [storeId] },
        storeId,
        actionKey: 'orders.refresh_batch_write',
        manualApproval: false,
      }),
      dataProvider.checkSensitiveActionPermissionMock({
        actorContext: { actor_id: 'local-admin', role: 'admin', store_ids: [storeId] },
        storeId,
        actionKey: 'orders.refresh_batch_write',
        manualApproval: true,
      }),
    ])
      .then(([readCheck, approvalRequiredCheck, adminApprovalMock]) => {
        if (cancelled) return;
        setPermissionState({
          loading: false,
          readCheck,
          approvalRequiredCheck,
          adminApprovalMock,
          error: '',
        });
      })
      .catch(() => {
        if (!cancelled) {
          setPermissionState({
            loading: false,
            readCheck: null,
            approvalRequiredCheck: null,
            adminApprovalMock: null,
            error: '角色权限展示暂时加载失败，订单查看不受影响；敏感写入仍保持关闭。',
          });
        }
      });

    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId]);

  if (!isNaverStore) return null;

  const { loading, readCheck, approvalRequiredCheck, adminApprovalMock, error } = permissionState;
  const canReadOrders = Boolean(readCheck?.permissionVerified);
  const needsManualApproval = approvalRequiredCheck?.skipReason === 'manual_approval_required'
    || approvalRequiredCheck?.status === 'approval_blocked';
  const adminCanApproveInMock = adminApprovalMock?.status === 'approval_allowed_mock';

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 订单操作权限</h2>
          <p>这里用普通业务话术说明当前页面能做什么；真实写入和正式批量同步仍需要单独阶段批准。</p>
        </div>
        <span className="period-chip">{loading ? '检查中' : '权限规则'}</span>
      </div>
      {error ? <div className="mock-sync-error">{error}</div> : null}
      <div className="business-capability-grid compact">
        <article className={canReadOrders ? 'business-capability-card success' : 'business-capability-card warning'}>
          <div className="business-capability-head">
            <strong>订单查看</strong>
            <span>{canReadOrders ? '可查看' : '需确认'}</span>
          </div>
          <p>{canReadOrders ? '当前角色可以查看 Naver 订单。' : '当前角色暂未确认订单查看权限，请联系管理员确认店铺范围。'}</p>
          <small>页面只读取本地订单列表，不触发平台写操作。</small>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>订单刷新写入</strong>
            <span>{needsManualApproval ? '需审批' : '保持关闭'}</span>
          </div>
          <p>订单刷新写入需要管理员批准，并且必须先完成备份、只读复查和审计证据。</p>
          <small>本页面不会直接写入订单，也不会写 SyncLog 或能力测试成功记录。</small>
        </article>
        <article className={adminCanApproveInMock ? 'business-capability-card info' : 'business-capability-card muted'}>
          <div className="business-capability-head">
            <strong>管理员审批条件</strong>
            <span>{adminCanApproveInMock ? '已验证' : '待接入'}</span>
          </div>
          <p>{adminCanApproveInMock ? '本地审批规则已确认管理员可审批订单刷新动作。' : '管理员审批条件尚未通过本地规则确认。'}</p>
          <small>这只是本地权限规则验证，不代表真实登录权限系统已上线。</small>
        </article>
        <article className="business-capability-card muted">
          <div className="business-capability-head">
            <strong>正式订单同步</strong>
            <span>未开放</span>
          </div>
          <p>正式订单批量同步仍未开放，发货、取消、退货、换货写操作也未开放。</p>
          <small>后续写入阶段必须单独批准。</small>
        </article>
      </div>
      <TechnicalDetails
        title="查看权限检查技术详情"
        description="权限 key、审批状态和 mock 标记只放在折叠区，主页面只显示业务提示。"
        items={[
          { label: 'role_visibility_phase', value: 'ERP-UX-2A' },
          { label: 'permission_api_phase', value: readCheck?.phase || approvalRequiredCheck?.phase || 'ERP-Auth-1F' },
          { label: 'mock_permission_api', value: readCheck?.mockPermissionApi ?? true },
          { label: 'public_endpoint_enabled', value: readCheck?.publicEndpointEnabled ?? true },
          { label: 'read_check_status', value: readCheck?.status },
          { label: 'read_operation_key', value: readCheck?.operationKey },
          { label: 'read_permission_verified', value: readCheck?.permissionVerified },
          { label: 'approval_required_status', value: approvalRequiredCheck?.status },
          { label: 'approval_required_reason', value: approvalRequiredCheck?.skipReason },
          { label: 'approval_action_key', value: approvalRequiredCheck?.operationKey },
          { label: 'admin_approval_mock_status', value: adminApprovalMock?.status },
          { label: 'admin_approval_role_verified', value: adminApprovalMock?.approvalRoleVerified },
          { label: 'real_auth_session_created', value: readCheck?.realAuthSessionCreated ?? false },
          { label: 'real_database_written', value: readCheck?.realDatabaseWritten ?? false },
          { label: 'orders_written', value: readCheck?.ordersWritten ?? false },
          { label: 'products_written', value: readCheck?.productsWritten ?? false },
          { label: 'sync_log_written', value: readCheck?.syncLogWritten ?? false },
          { label: 'tested_success_written', value: readCheck?.capabilityTestedSuccessWritten ?? false },
          { label: 'raw_response_saved', value: readCheck?.rawResponseSaved ?? false },
          { label: 'formal_sync_open', value: readCheck?.formalSyncOpen ?? false },
          { label: 'platform_writes_enabled', value: readCheck?.platformWritesEnabled ?? false },
        ]}
      />
    </section>
  );
}

function DetailItem({ label, value }) {
  return (
    <div className="detail-item">
      <span>{label}</span>
      <strong>{value || '待接入'}</strong>
    </div>
  );
}

function NaverOrderCompleteDetailPanel() {
  const { selectedStore, selectedStoreId } = useStoreContext();
  const [orders, setOrders] = useState([]);
  const [selectedOrderId, setSelectedOrderId] = useState('');
  const [loadError, setLoadError] = useState('');
  const [previewResult, setPreviewResult] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [previewWindow, setPreviewWindow] = useState('24h');
  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    if (!isNaverStore || !selectedStoreId) {
      setOrders([]);
      setSelectedOrderId('');
      setLoadError('');
      setPreviewResult(null);
      setPreviewError('');
      return undefined;
    }
    let cancelled = false;
    setLoadError('');
    setPreviewResult(null);
    setPreviewError('');
    dataProvider.getOrders({
      storeId: selectedStoreId,
      platform: 'naver',
      page: 1,
      pageSize: 100,
    })
      .then((orderResponse) => {
        if (cancelled) return;
        const naverOrders = filterNaverOrdersForStore(
          orderResponse.data || orderResponse.items || [],
          selectedStore,
          selectedStoreId,
        );
        setOrders(naverOrders);
        setSelectedOrderId((currentId) => (
          naverOrders.some((order) => String(order.id) === String(currentId))
            ? currentId
            : String(naverOrders[0]?.id || '')
        ));
      })
      .catch((error) => {
        if (!cancelled) {
          setOrders([]);
          setSelectedOrderId('');
          setLoadError(error.message || 'Naver 订单详情加载失败。');
        }
      });
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStore, selectedStoreId]);

  if (!isNaverStore) return null;

  const activeOrder = orders.find((order) => String(order.id) === String(selectedOrderId)) || orders[0];
  const previewFields = previewResult?.available ? previewResult.completeFields : {};
  const fields = activeOrder ? getCompleteOrderFields(activeOrder, previewFields) : null;
  const completeFieldReady = Boolean(activeOrder && fields?.orderNo !== '待接入' && fields?.buyerName !== '待接入');
  const previewAllowed = !isBackendSource || String(selectedStoreId) === '8';
  const previewWindowLabel = getNaverCompletePreviewWindowLabel(previewWindow);
  const refreshGatePlan = buildNaverOrderRefreshGatePlan({
    activeOrder,
    previewAllowed,
    previewResult,
    previewWindow,
    previewWindowLabel,
  });
  const timelineEvents = activeOrder ? normalizeOrderStatusTimelineEvents(activeOrder) : [];
  const timelineTechnicalItems = activeOrder ? buildOrderTimelineTechnicalItems(activeOrder, fields, timelineEvents) : [];

  const runCompleteFieldPreview = async () => {
    if (previewLoading || !activeOrder || !previewAllowed) return;
    setPreviewLoading(true);
    setPreviewError('');
    setPreviewResult(null);
    try {
      const result = await dataProvider.previewNaverOrderCompleteFields({
        storeId: selectedStoreId,
        credentialId: 7,
        previewWindow,
      });
      setPreviewResult(result);
      if (!result.available) {
        setPreviewError(result.businessMessage || `当前选择的${previewWindowLabel}窗口没有可展示的 Naver 订单完整信息。`);
      }
    } catch (error) {
      setPreviewError(formatError(error));
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <section className="content-card">
      <div className="panel-heading-row">
        <div>
          <h2>Naver 订单详情</h2>
          <p>完整订单号、商品编号和买家信息只在内部订单详情区展示；Dashboard 和汇总卡片保持摘要口径。</p>
        </div>
        <span className="period-chip">{selectedStore?.name || 'Naver 店铺'}</span>
      </div>
      <div className="sync-action-row">
        <label className="form-field preview-window-field">
          <span>查看范围</span>
          <select value={previewWindow} disabled={previewLoading} onChange={(event) => setPreviewWindow(event.target.value)}>
            {naverCompletePreviewWindows.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <button
          className="button primary"
          onClick={runCompleteFieldPreview}
          disabled={!activeOrder || previewLoading || !previewAllowed}
        >
          {previewLoading ? '正在读取最近订单...' : '查看最近订单完整信息'}
        </button>
        <span className="mock-sync-note">
          {previewAllowed
            ? `手动查看 ${previewWindowLabel} 的最近订单完整信息；只展示结果，不保存新订单。`
            : '当前店铺暂未开放最近订单完整信息核对。'}
        </span>
      </div>
      {loadError ? <div className="mock-sync-error">{loadError}</div> : null}
      {previewResult?.available ? (
        <div className="mock-sync-success">已读取{previewResult.previewWindowLabel || previewWindowLabel}最近订单完整信息，页面仅展示结果，不写库。</div>
      ) : null}
      {previewError ? <div className="mock-sync-error">{previewError}</div> : null}
      {!activeOrder ? (
        <div className="empty-state">当前店铺暂无可展示的 Naver 本地订单详情。</div>
      ) : (
        <>
          <div className="detail-toolbar">
            {orders.map((order) => (
              <button
                className={String(order.id) === String(activeOrder.id) ? 'button primary' : 'button ghost'}
                key={order.id}
                onClick={() => setSelectedOrderId(String(order.id))}
              >
                {displayText(order.orderNo, order.external_order_id)} · {sourceTypeLabel(order)}
              </button>
            ))}
          </div>
          <div className="detail-modal">
            <section className="detail-section">
              <h3>订单信息</h3>
              <div className="detail-grid">
                <DetailItem label="完整订单号" value={fields.orderNo} />
                <DetailItem label="商品订单号" value={fields.productOrderNo} />
                <DetailItem label="订单状态" value={fields.orderStatus} />
                <DetailItem label="付款状态" value={fields.paymentStatus} />
                <DetailItem label="订单金额" value={fields.amount} />
                <DetailItem label="下单时间" value={fields.orderedAt} />
                <DetailItem label="付款时间" value={fields.paidAt} />
                <DetailItem label="来源" value={fields.sourceType} />
              </div>
            </section>
            <section className="detail-section">
              <h3>商品信息</h3>
              <div className="detail-grid">
                <DetailItem label="平台商品编号" value={fields.platformProductId} />
                <DetailItem label="商品名" value={fields.productName} />
                <DetailItem label="选项" value={fields.optionName} />
                <DetailItem label="数量" value={fields.quantity} />
              </div>
            </section>
            <section className="detail-section">
              <h3>买家与收件信息</h3>
              <div className="detail-grid">
                <DetailItem label="买家姓名" value={fields.buyerName} />
                <DetailItem label="买家电话" value={fields.buyerPhone} />
                <DetailItem label="收件人" value={fields.receiverName} />
                <DetailItem label="收件电话" value={fields.receiverPhone} />
                <DetailItem label="邮编" value={fields.zipCode} />
                <DetailItem label="收件地址" value={fields.receiverAddress} />
              </div>
            </section>
            <section className="detail-section">
              <h3>配送与售后</h3>
              <div className="detail-grid">
                <DetailItem label="配送状态" value={fields.deliveryStatus} />
                <DetailItem label="售后状态" value={fields.claimStatus} />
              </div>
            </section>
          </div>

          <section className="detail-section">
            <h3>订单状态时间线</h3>
            <div className="detail-grid">
              <DetailItem label="当前本地订单状态" value={fields.orderStatus} />
              <DetailItem label="当前配送状态" value={fields.deliveryStatus} />
              <DetailItem label="当前售后状态" value={fields.claimStatus} />
              <DetailItem label="最近订单时间" value={displayText(fields.paidAt, fields.orderedAt)} />
            </div>
            {timelineEvents.length ? (
              <Timeline items={timelineEvents} />
            ) : (
              <div className="empty-state compact">当前暂无已记录的订单状态历史。</div>
            )}
            <p className="mock-sync-note">状态时间线当前只展示本地记录。没有历史记录时，只表示本地尚未生成状态事件；正式订单同步、自动刷新和事件写入仍未开放。</p>
            <TechnicalDetails
              title="查看状态时间线技术详情"
              description="原始状态枚举、来源阶段和去重信息只放在折叠详情中；页面主区域只展示卖家可读状态。"
              items={timelineTechnicalItems}
            />
          </section>

          <section className="detail-section">
            <h3>后续刷新保护</h3>
            <div className={refreshGatePlan.statusKind === 'blocked' ? 'mock-sync-error' : 'sync-inline-warning'}>
              {refreshGatePlan.statusLabel}：{refreshGatePlan.businessMessage}
            </div>
            <p className="mock-sync-note">当前页面不会自动刷新本地订单，也不会执行平台发货、取消、退货或换货。需要刷新本地订单时，必须另开阶段、先备份数据库并由人工明确批准。</p>
            <TechnicalDetails
              title="查看刷新保护技术详情"
              description="刷新保护细节仅供管理员排查，普通卖家主页面不展示门禁参数。"
              items={[
                ...refreshGatePlan.items.map((item) => ({
                  label: `gate_${item.label}`,
                  value: `${item.state}: ${item.detail}`,
                })),
                { label: 'order_refresh_write_gate_phase', value: refreshGatePlan.technical.phase },
                { label: 'planned_only', value: refreshGatePlan.technical.plannedOnly },
                { label: 'selected_store_id', value: selectedStoreId },
                { label: 'credential_id', value: 7 },
                { label: 'selected_operational_order', value: refreshGatePlan.technical.selectedOperationalOrder },
                { label: 'preview_available', value: refreshGatePlan.technical.previewAvailable },
                { label: 'identity_match_state', value: refreshGatePlan.technical.identityMatchState },
                { label: 'identity_matched', value: refreshGatePlan.technical.identityMatched },
                { label: 'identity_comparable', value: refreshGatePlan.technical.identityComparable },
                { label: 'identity_match_method', value: refreshGatePlan.technical.identityMatchMethod },
                { label: 'preview_window', value: refreshGatePlan.technical.previewWindow },
                { label: 'can_enter_manual_review', value: refreshGatePlan.canEnterManualReview },
                { label: 'requires_user_approval', value: refreshGatePlan.technical.requiresUserApproval },
                { label: 'requires_db_backup', value: refreshGatePlan.technical.requiresDbBackup },
                { label: 'real_sync_allowed', value: refreshGatePlan.technical.realSyncAllowed },
                { label: 'orders_write_allowed', value: refreshGatePlan.technical.ordersWriteAllowed },
                { label: 'sync_log_write_allowed', value: refreshGatePlan.technical.syncLogWriteAllowed },
                { label: 'tested_success_write_allowed', value: refreshGatePlan.technical.testedSuccessWriteAllowed },
                { label: 'platform_write_allowed', value: refreshGatePlan.technical.platformWriteAllowed },
                { label: 'raw_response_saved', value: refreshGatePlan.technical.rawResponseSaved },
                { label: 'formal_order_sync_open', value: refreshGatePlan.technical.formalOrderSyncOpen },
              ]}
            />
          </section>

          <TechnicalDetails
            title="查看完整字段读取技术详情"
            description="仅保留字段可用性和口径，不展示平台原始响应。"
            items={[
              { label: 'complete_field_view', value: completeFieldReady },
              { label: 'complete_field_preview_requested', value: Boolean(previewResult?.requested) },
              { label: 'complete_field_preview_available', value: Boolean(previewResult?.available) },
              { label: 'preview_window', value: previewResult?.previewWindow || previewWindow },
              { label: 'window_hours', value: previewResult?.windowHours },
              { label: 'start_datetime', value: previewResult?.startDateTime },
              { label: 'end_datetime', value: previewResult?.endDateTime },
              { label: 'preview_status', value: previewResult?.previewStatus },
              { label: 'feed_called', value: previewResult?.feedCalled },
              { label: 'detail_called', value: previewResult?.detailCalled },
              { label: 'dashboard_summary_only', value: true },
              { label: 'formal_order_sync_open', value: false },
              { label: 'raw_response_saved', value: fields.rawResponseSaved },
              { label: 'mapping_version', value: fields.mappingVersion },
              { label: 'codex1_schema_write_enabled', value: previewResult?.savePlan?.codex1SchemaWriteEnabled ?? false },
              { label: 'orders_written', value: previewResult?.savePlan?.ordersWritten ?? false },
              { label: 'sync_log_written', value: previewResult?.savePlan?.syncLogWritten ?? false },
              { label: 'tested_success_written', value: previewResult?.savePlan?.testedSuccessWritten ?? false },
            ]}
          />
        </>
      )}
    </section>
  );
}

export default function Orders() {
  const { selectedStore, selectedStoreId, loading: storeLoading } = useStoreContext();
  const { versions } = useSyncRefresh();
  const pageApi = useMemo(() => ({
    ...api,
    list: async (params = {}) => {
      if (isBackendSource && (storeLoading || !selectedStoreId)) {
        return Promise.resolve({
          data: [],
          items: [],
          total: 0,
          page: params?.page || 1,
          pageSize: params?.pageSize || 5,
        });
      }
      const isSelectedNaverStore = normalizePlatform(params?.platform || selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';
      if (isBackendSource && isSelectedNaverStore) {
        const fullResult = await dataProvider.getOrders({
          ...params,
          page: 1,
          pageSize: 100,
        });
        const visibleRows = filterNaverOrdersForStore(
          fullResult.data || fullResult.items || [],
          selectedStore,
          selectedStoreId,
        );
        return {
          ...fullResult,
          data: paginateRows(visibleRows, params.page, params.pageSize),
          items: paginateRows(visibleRows, params.page, params.pageSize),
          total: visibleRows.length,
          page: params.page || 1,
          pageSize: params.pageSize || 5,
        };
      }
      return dataProvider.getOrders(params);
    },
  }), [selectedStore, selectedStoreId, storeLoading]);

  return (
    <>
      <NaverOrderPreviewStatusPanel />
      <NaverRoleAwareActionVisibilityPanel />
      <NaverOrderCompleteDetailPanel />
      <CoupangOrderSyncPanel />
      <ResourcePage
        title="订单管理"
        description="查看订单履约、发货、退款和异常处理状态。Naver 订单的完整信息放在上方详情区，主列表保持业务摘要。"
        resourceName="订单"
        api={pageApi}
        columns={columns}
        fields={fields}
        statuses={statusOptions}
        initialForm={{ orderNo: '', product: '', store: '', customer: '', amount: 0, status: '', createdAt: '' }}
        readOnly={isBackendSource}
        extraParams={isBackendSource && selectedStoreId ? { storeId: selectedStoreId } : {}}
        reloadKey={`${selectedStoreId}-${versions.orders}`}
      />
    </>
  );
}
