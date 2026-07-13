import { getNaverOrderStatusPresentation } from '../utils/naverOrderFulfillment.js';
import { adaptAutomaticReadAttentionSummary, adaptAutomaticReadStatus } from '../utils/automaticReadStatus.js';

const numberValue = (value) => Number(value || 0);
const emptyText = (value, fallback = '—') => value ?? fallback;

function adaptPlatform(value) {
  const platforms = { naver: 'Naver', coupang: 'Coupang', gmarket: 'Gmarket' };
  return platforms[String(value || '').toLowerCase()] || value || '—';
}

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
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

function naverBusinessStatusLabel(rawValue, ...labelValues) {
  const raw = String(statusRawValue(rawValue) || '').trim();
  const presentation = raw ? getNaverOrderStatusPresentation(raw) : null;
  if (presentation && presentation.bucket !== 'unknown') return presentation.label;
  const label = labelValues
    .map(statusLabelValue)
    .find((item) => item !== undefined && item !== null && String(item).trim() !== '');
  if (label) return String(label).trim();
  return presentation?.label || '';
}

function adaptStatus(value, mapping = {}) {
  return mapping[String(value || '').toLowerCase()] || value || '未知';
}

function compactPayload(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined && value !== null),
  );
}

function isSensitiveFinancialField(key = '') {
  const normalized = String(key).replace(/[_-]/g, '').toLowerCase();
  return [
    'bankaccountholder',
    'bankname',
    'bankaccount',
    'accesskey',
    'secretkey',
    'authorization',
    'signature',
    'token',
    'clientsecret',
  ].some((item) => normalized.includes(item));
}

function sanitizeFinancialObject(item = {}) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) return {};
  return Object.fromEntries(
    Object.entries(item)
      .filter(([key]) => !isSensitiveFinancialField(key))
      .map(([key, value]) => [key, value && typeof value === 'object' ? String(value) : value]),
  );
}

function sanitizeFieldMappingSuggestion(data = {}) {
  if (!data || typeof data !== 'object') return {};
  return Object.fromEntries(
    Object.entries(data)
      .filter(([key]) => !isSensitiveFinancialField(key))
      .map(([key, value]) => {
        if (Array.isArray(value)) {
          return [key, value.filter((item) => !isSensitiveFinancialField(item))];
        }
        if (value && typeof value === 'object') return [key, sanitizeFinancialObject(value)];
        return [key, value];
      }),
  );
}

function adaptFinancialSourceBoundaries(data = {}) {
  return {
    orderSalesScope: data.order_sales_scope || '',
    platformSalesDetailScope: data.platform_sales_detail_scope || '',
    settlementScope: data.settlement_scope || '',
    settlementMonthGranularityNotice: data.settlement_month_granularity_notice || '',
    finalAmountNotice: data.final_amount_notice || '',
    zeroDataNotice: data.zero_data_notice || '',
  };
}

function adaptFinancialSummary(data = {}) {
  if (!data || typeof data !== 'object' || Array.isArray(data) || !Object.keys(data).length) {
    return {
      available: false,
      orderSalesSummary: {
        scope: 'order_amount_from_orders',
        totalOrders: 0,
        totalOrderSalesAmount: 0,
        currency: 'KRW',
        latestOrderedAt: null,
      },
      platformSalesDetailSummary: {
        scope: 'platform_sales_details',
        salesDetailRows: 0,
        totalSaleAmount: 0,
        totalSettlementTargetAmount: 0,
        totalSettlementAmount: 0,
        latestRecognitionDate: null,
        currency: 'KRW',
        dataStatus: 'local_persisted_rows',
      },
      settlementSummary: {
        scope: 'platform_settlement_details',
        settlementRows: 0,
        totalSettlementAmount: 0,
        totalFinalAmount: 0,
        totalServiceFee: 0,
        latestRevenueRecognitionYearMonth: null,
        latestSettlementDate: null,
        currency: 'KRW',
        dataStatus: 'local_persisted_rows',
      },
      sourceBoundaries: adaptFinancialSourceBoundaries(),
    };
  }

  const orderSalesSummary = data.order_sales_summary || {};
  const platformSalesDetailSummary = data.platform_sales_detail_summary || {};
  const settlementSummary = data.settlement_summary || {};

  return {
    available: true,
    orderSalesSummary: {
      scope: orderSalesSummary.scope || 'order_amount_from_orders',
      totalOrders: numberValue(orderSalesSummary.total_orders),
      totalOrderSalesAmount: numberValue(orderSalesSummary.total_order_sales_amount),
      currency: orderSalesSummary.currency || 'KRW',
      latestOrderedAt: orderSalesSummary.latest_ordered_at || null,
    },
    platformSalesDetailSummary: {
      scope: platformSalesDetailSummary.scope || 'platform_sales_details',
      salesDetailRows: numberValue(platformSalesDetailSummary.sales_detail_rows),
      totalSaleAmount: numberValue(platformSalesDetailSummary.total_sale_amount),
      totalSettlementTargetAmount: numberValue(platformSalesDetailSummary.total_settlement_target_amount),
      totalSettlementAmount: numberValue(platformSalesDetailSummary.total_settlement_amount),
      latestRecognitionDate: platformSalesDetailSummary.latest_recognition_date || null,
      currency: platformSalesDetailSummary.currency || 'KRW',
      dataStatus: platformSalesDetailSummary.data_status || 'local_persisted_rows',
    },
    settlementSummary: {
      scope: settlementSummary.scope || 'platform_settlement_details',
      settlementRows: numberValue(settlementSummary.settlement_rows),
      totalSettlementAmount: numberValue(settlementSummary.total_settlement_amount),
      totalFinalAmount: numberValue(settlementSummary.total_final_amount),
      totalServiceFee: numberValue(settlementSummary.total_service_fee),
      latestRevenueRecognitionYearMonth: settlementSummary.latest_revenue_recognition_year_month || null,
      latestSettlementDate: settlementSummary.latest_settlement_date || null,
      currency: settlementSummary.currency || 'KRW',
      dataStatus: settlementSummary.data_status || 'local_persisted_rows',
    },
    sourceBoundaries: adaptFinancialSourceBoundaries(data.source_boundaries || {}),
  };
}

function normalizePlatformForBackend(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const platforms = {
    naver: 'naver',
    coupang: 'coupang',
    gmarket: 'gmarket',
    '11街': '11st',
    '11st': '11st',
    '옥션': 'auction',
    auction: 'auction',
  };
  return platforms[normalized] || normalized || value;
}

function normalizeStoreStatusForBackend(value) {
  const statuses = {
    '正常运营': 'active',
    '정상 운영': 'active',
    active: 'active',
    '审核中': 'review',
    '심사중': 'review',
    review: 'review',
    '申诉中': 'appeal',
    appeal: 'appeal',
    '판매중지': 'inactive',
    inactive: 'inactive',
    '使用中止': 'inactive',
  };
  return statuses[String(value || '').trim()] || value || 'active';
}

function normalizeDeviceStatusForBackend(value) {
  const statuses = {
    active: 'active',
    inactive: 'inactive',
    warning: 'warning',
    '正常': 'active',
    '启用': 'active',
    '停用': 'inactive',
    '风险': 'warning',
  };
  return statuses[String(value || '').trim()] || value || 'active';
}

function normalizeCredentialPlatformForBackend(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const platforms = {
    naver: 'naver',
    coupang: 'coupang',
  };
  return platforms[normalized] || normalized || value;
}

function normalizeAccountStatusForBackend(value) {
  const statuses = {
    active: 'active',
    inactive: 'inactive',
    '鍚敤': 'active',
    '鍋滅敤': 'inactive',
  };
  return statuses[String(value || '').trim()] || value || 'active';
}

function normalizeAuthStatusForBackend(value) {
  const normalized = String(value || '').trim().toLowerCase();
  const statuses = {
    not_configured: 'not_configured',
    configured: 'configured',
    needs_test: 'needs_test',
    test_failed: 'test_failed',
    test_passed: 'test_passed',
  };
  return statuses[normalized] || normalized || 'not_configured';
}

export function adaptStore(item = {}) {
  return {
    id: item.id,
    name: item.name,
    platform: adaptPlatform(item.platform),
    region: item.country,
    country: item.country,
    language: item.language,
    manager: emptyText(item.owner_name, '未配置'),
    products: numberValue(item.product_count),
    rawStatus: item.status,
    status: adaptStatus(item.status, { active: '정상 운영', inactive: '使用中止' }),
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: emptyText(item.updated_at),
  };
}

export function toBackendStorePayload(item = {}) {
  return compactPayload({
    name: String(item.name || '').trim(),
    platform: normalizePlatformForBackend(item.platform),
    country: String(item.country || item.region || 'KR').trim(),
    language: String(item.language || 'ko-KR').trim(),
    status: normalizeStoreStatusForBackend(item.status || item.rawStatus),
    owner_name: item.manager || item.ownerName || item.owner_name || null,
    remark: item.remark || null,
  });
}

export function adaptProduct(item = {}) {
  const rawPlatform = normalizePlatformForBackend(item.platform);
  const displayExternalId = rawPlatform === 'naver' && item.external_product_id ? '平台商品编号已脱敏' : item.external_product_id;
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    rawPlatform,
    externalId: displayExternalId,
    sku: rawPlatform === 'naver' ? displayExternalId : item.sku || displayExternalId,
    name: item.name,
    brand: item.brand,
    category: item.category,
    price: numberValue(item.price),
    currency: item.currency,
    stock: item.stock_quantity,
    sourceType: item.source_type,
    rawStatus: item.status,
    status: adaptStatus(item.status, { active: '판매중', review: '심사중', suspended: '판매중지' }),
    store: item.store_name || `店铺 #${item.store_id}`,
    lastSyncedAt: item.last_synced_at,
    createdAt: item.created_at,
    updatedAt: emptyText(item.updated_at || item.last_synced_at),
  };
}

export function adaptOrder(item = {}) {
  const rawPlatform = normalizePlatform(item.platform);
  const rawData = item.raw_data || {};
  const isNaver = rawPlatform === 'naver';
  const naverStatusLabel = isNaver
    ? naverBusinessStatusLabel(item.order_status || rawData.order_status, item.order_status_label_zh, rawData.order_status_label_zh, rawData.order_status)
    : '';
  const naverDeliveryStatus = item.delivery_status || rawData.delivery_status;
  const naverClaimStatus = item.claim_status || rawData.claim_status;
  const naverDeliveryLabel = isNaver
    ? naverBusinessStatusLabel(naverDeliveryStatus, item.delivery_status_label_zh, rawData.delivery_status_label_zh, naverDeliveryStatus)
    : item.delivery_status_label_zh || rawData.delivery_status_label_zh;
  const naverClaimLabel = isNaver
    ? naverBusinessStatusLabel(naverClaimStatus, item.claim_status_label_zh, rawData.claim_status_label_zh, naverClaimStatus)
    : item.claim_status_label_zh || rawData.claim_status_label_zh;
  const isHashOrderId = /^id-hash-[a-z0-9_-]+$/i.test(String(item.external_order_id || ''));
  const productOrderNo = item.external_product_order_id || rawData.external_product_order_id || '';
  const fullOrderNo = item.external_order_id
    || rawData.external_order_id_full
    || productOrderNo
    || rawData.external_order_id
    || '';
  const displayOrderNo = fullOrderNo || productOrderNo || item.id;
  const displayCustomer = item.buyer_name || rawData.buyer_name;
  const displayPhone = item.buyer_phone
    || rawData.buyer_phone
    || item.buyer_masked_phone
    || rawData.buyer_phone_masked;
  const productOrderHash = rawData.external_product_order_id_hash || (isNaver && isHashOrderId ? item.external_order_id : null);
  const platformProductId = item.platform_product_id || '';
  const statusEvents = item.status_events
    || item.statusEvents
    || item.order_status_events
    || item.orderStatusEvents
    || rawData.status_events
    || rawData.order_status_events
    || [];
  const deliveryCompany = item.delivery_company
    || item.deliveryCompany
    || rawData.delivery_company
    || rawData.deliveryCompany
    || rawData.deliveryCompanyName
    || rawData.shipping_carrier_label
    || rawData.shipping_carrier_code
    || '';
  const deliveryCompanyCode = item.delivery_company_code
    || item.deliveryCompanyCode
    || rawData.delivery_company_code
    || rawData.deliveryCompanyCode
    || rawData.shipping_carrier_code
    || '';
  const trackingNumber = item.tracking_number
    || item.trackingNumber
    || rawData.tracking_number
    || rawData.trackingNumber
    || rawData.shipping_tracking_number
    || '';
  const statusLabel = isNaver
    ? (naverStatusLabel || getNaverOrderStatusPresentation(item.order_status).label)
    : adaptStatus(item.order_status, {
      paid: '待发货',
      payed: '已付款 / 新订单',
      shipped: '배송중',
      completed: '구매확정',
      cancelled: '取消退款',
      canceled: '取消退款',
    });
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    rawPlatform,
    orderNo: displayOrderNo,
    fullOrderNo,
    orderHash: isNaver && isHashOrderId ? item.external_order_id : null,
    productOrderNo,
    productOrderHash,
    platformProductId,
    product: item.product_name,
    productName: item.product_name,
    optionName: item.option_name || '',
    productImageUrl: item.product_image_url || '',
    productUrl: item.product_url || '',
    customer: displayCustomer,
    customerName: displayCustomer,
    buyerName: item.buyer_name || rawData.buyer_name,
    buyerPhone: item.buyer_phone || rawData.buyer_phone,
    maskedPhone: item.buyer_masked_phone,
    phone: displayPhone,
    receiverName: item.receiver_name || rawData.receiver_name,
    receiverPhone: item.receiver_phone || rawData.receiver_phone,
    receiverAddress: item.receiver_address || rawData.receiver_address,
    zipCode: item.zip_code || rawData.zip_code,
    deliveryCompany,
    deliveryCompanyCode,
    delivery_company: deliveryCompany,
    delivery_company_code: deliveryCompanyCode,
    trackingNumber,
    tracking_number: trackingNumber,
    logisticsTraceStatus: item.logistics_trace_status || item.logisticsTraceStatus || (trackingNumber ? 'local_tracking_trace' : 'tracking_number_missing'),
    logisticsTraceAvailable: Boolean(trackingNumber),
    quantity: item.quantity,
    amount: numberValue(item.order_amount),
    currency: item.currency,
    rawStatus: item.order_status,
    status: statusLabel,
    paymentStatus: item.payment_status || rawData.payment_status,
    deliveryStatus: statusRawValue(naverDeliveryStatus),
    deliveryStatusLabelZh: naverDeliveryLabel,
    claimStatus: statusRawValue(naverClaimStatus),
    claimStatusLabelZh: naverClaimLabel,
    statusEvents,
    orderStatusEvents: statusEvents,
    sourceType: item.source_type,
    rawResponseSaved: rawData.raw_response_saved,
    privacyFieldsRedacted: rawData.privacy_fields_redacted,
    addressSaved: rawData.address_saved,
    addressObserved: rawData.address_observed,
    mappingVersion: rawData.mapping_version,
    store: item.store_name || `店铺 #${item.store_id}`,
    paidAt: item.paid_at,
    createdAt: item.ordered_at,
    updatedAt: emptyText(item.updated_at),
  };
}

export function adaptStoreOnboarding(item = {}) {
  const progress = item.progress_summary || item.progressSummary || {};
  const validation = item.validation_summary || item.validationSummary || {};
  return {
    ...item,
    id: item.id,
    storeId: item.store_id ?? item.storeId ?? null,
    status: item.status || 'validating',
    requestedStoreName: item.requested_store_name || item.requestedStoreName || '',
    validationSummary: validation,
    progressSummary: progress,
    lastErrorCode: item.last_error_code || item.lastErrorCode || '',
    nextRetryAt: item.next_retry_at || item.nextRetryAt || null,
  };
}

export function adaptOrderLogisticsTrace(data = {}) {
  const events = Array.isArray(data.events) ? data.events : [];
  return {
    status: data.status || 'tracking_number_missing',
    orderId: data.order_id ?? data.orderId,
    storeId: data.store_id ?? data.storeId,
    platform: adaptPlatform(data.platform),
    orderNo: data.order_no || data.orderNo || '',
    productOrderNo: data.product_order_no || data.productOrderNo || '',
    deliveryCompany: data.delivery_company || data.deliveryCompany || '',
    deliveryCompanyCode: data.delivery_company_code || data.deliveryCompanyCode || '',
    trackingNumber: data.tracking_number || data.trackingNumber || '',
    trackingSource: data.tracking_source || data.trackingSource || 'local_tracking_trace',
    realtimeTrackingOpen: Boolean(data.realtime_tracking_open ?? data.realtimeTrackingOpen),
    message: data.message || '',
    events: events.map((item, index) => ({
      id: item.id || `${data.order_id || data.orderId || 'trace'}-${index}`,
      time: item.time || item.observed_at || item.created_at || '',
      label: item.label || item.title || '物流轨迹记录',
      description: item.description || item.content || '',
      source: item.source || '',
    })),
  };
}

export function adaptNaverOrderCompletePreview(data = {}) {
  const preview = data.complete_field_preview || {};
  const completeFields = preview.complete_fields || {};
  const detailPreview = data.detail_preview || {};
  const savePlan = preview.save_plan || {};

  return {
    storeId: data.store_id,
    credentialId: data.credential_id,
    platform: adaptPlatform(data.platform),
    rawPlatform: data.platform,
    previewStatus: data.preview_status,
    errorCode: data.error_code,
    businessMessage: data.business_message,
    feedCalled: Boolean(data.field_observation?.feed_called),
    detailCalled: Boolean(data.field_observation?.detail_called),
    detailHttpStatus: data.field_observation?.detail_http_status,
    requested: Boolean(preview.requested),
    previewOnly: preview.preview_only !== false,
    available: Boolean(preview.available),
    fieldAvailability: preview.field_availability || {},
    detailPreview: {
      externalOrderIdHash: detailPreview.external_order_id_hash || detailPreview.order_id_hash,
      externalProductOrderIdHash: detailPreview.external_product_order_id_hash || detailPreview.product_order_id_hash,
      orderStatus: detailPreview.order_status?.raw || detailPreview.order_status,
      orderStatusLabelZh: naverBusinessStatusLabel(detailPreview.order_status, detailPreview.order_status_label_zh, detailPreview.order_status),
      orderAmount: detailPreview.order_amount,
      currency: detailPreview.currency,
      rawResponseSaved: Boolean(detailPreview.raw_response_saved),
      privacyFieldsRedacted: detailPreview.privacy_fields_redacted !== false,
      addressSaved: Boolean(detailPreview.address_saved),
      mappingVersion: detailPreview.mapping_version,
    },
    savePlan: {
      codex1SchemaWriteEnabled: Boolean(savePlan.codex1_schema_write_enabled),
      requiresUserApproval: Boolean(savePlan.requires_user_approval),
      requiresDbBackup: Boolean(savePlan.requires_db_backup),
      formalOrderSyncOpen: Boolean(savePlan.formal_order_sync_open),
      platformWritesEnabled: Boolean(savePlan.platform_writes_enabled),
      ordersWritten: Boolean(savePlan.orders_written),
      syncLogWritten: Boolean(savePlan.sync_log_written),
      testedSuccessWritten: Boolean(savePlan.tested_success_written),
      rawResponseSaved: Boolean(savePlan.raw_response_saved),
    },
    completeFields: {
      externalOrderId: completeFields.external_order_id,
      externalProductOrderId: completeFields.external_product_order_id,
      platformProductId: completeFields.platform_product_id,
      productName: completeFields.product_name,
      optionName: completeFields.option_name,
      quantity: completeFields.quantity,
      orderAmount: completeFields.order_amount,
      currency: completeFields.currency,
      orderStatus: completeFields.order_status,
      orderStatusLabelZh: naverBusinessStatusLabel(completeFields.order_status, completeFields.order_status_label_zh),
      paymentStatus: completeFields.payment_status,
      deliveryStatus: completeFields.delivery_status,
      deliveryStatusLabelZh: naverBusinessStatusLabel(completeFields.delivery_status, completeFields.delivery_status_label_zh),
      claimStatus: completeFields.claim_status,
      claimStatusLabelZh: naverBusinessStatusLabel(completeFields.claim_status, completeFields.claim_status_label_zh),
      buyerName: completeFields.buyer_name,
      buyerPhone: completeFields.buyer_phone,
      receiverName: completeFields.receiver_name,
      receiverPhone: completeFields.receiver_phone,
      receiverAddress: completeFields.receiver_address,
      zipCode: completeFields.zip_code,
      orderedAt: completeFields.ordered_at,
      paidAt: completeFields.paid_at,
      lastChangedAt: completeFields.last_changed_at,
      rawResponseSaved: Boolean(completeFields.raw_response_saved),
      mappingVersion: completeFields.mapping_version,
    },
  };
}

export function adaptCustomerInquiry(item = {}) {
  const rawData = item.raw_data || {};
  const stableOrder = item.order_context || item.orderContext || null;
  const stableLogistics = item.logistics_context || item.logisticsContext || {};
  const relatedOrder = stableOrder || item.related_order || item.relatedOrder || {};
  const productOrderIds = Array.isArray(rawData.product_order_id_list) ? rawData.product_order_id_list : [];
  const orderNo = item.order_no || relatedOrder.order_no || rawData.order_id || productOrderIds[0] || '';
  const productName = item.product_name || relatedOrder.product_name || rawData.product_name || '';
  const source = item.source || rawData.source || item.source_type || '';
  const replyEnabled = item.reply_enabled ?? item.replyEnabled ?? (source !== 'naver_readonly');
  const readonlyId = item.readonly_id ?? item.readonlyId
    ?? (String(item.inquiry_id || '').startsWith('pxg_naver_readonly:') ? String(item.inquiry_id).split(':')[1] : null);
  const safeSummary = item.summary || item.title || item.inquiry_type || item.category || 'customer inquiry';
  const isReadonly = readonlyId !== null && readonlyId !== undefined && String(readonlyId) !== '';
  return {
    id: item.inquiry_id || item.id,
    readonlyId,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform || source),
    rawPlatform: normalizePlatform(item.platform || source),
    ticketNo: item.external_inquiry_id || item.inquiry_id,
    externalInquiryId: item.external_inquiry_id || item.inquiry_id,
    type: item.category || item.inquiry_type,
    inquiryType: item.category || item.inquiry_type,
    customer: item.customer_name,
    customerName: item.customer_name,
    title: item.title || item.summary,
    content: isReadonly ? '' : safeSummary,
    summary: safeSummary,
    detailLoaded: !isReadonly,
    rawStatus: item.status,
    status: adaptStatus(item.status, { open: '문의 대기', answered: '답변 완료', processing: '처리중' }),
    priority: item.priority || '일반',
    replyEnabled,
    replyDisabledReason: item.reply_disabled_reason || item.replyDisabledReason || '',
    source,
    store: item.store_name || `店铺 #${item.store_id}`,
    orderNo: emptyText(orderNo),
    productName: emptyText(productName),
    productOrderIds,
    relatedOrder: {
      orderNo: relatedOrder.order_no || orderNo,
      productOrderNo: relatedOrder.product_order_no || productOrderIds[0] || '',
      productName: relatedOrder.product_name || productName,
      orderStatus: relatedOrder.order_status || '',
      batchNo: relatedOrder.warehouse_batch_no || relatedOrder.batch_no || '',
      batchStatus: relatedOrder.warehouse_batch_status || relatedOrder.batch_status || '',
      warehouseStatus: relatedOrder.warehouse_row_status || '',
      carrier: stableLogistics.carrier || relatedOrder.carrier || '',
      trackingNumber: stableLogistics.tracking_number_masked || relatedOrder.tracking_number_masked || relatedOrder.tracking_number || '',
      trackingStatus: stableLogistics.shipment_status || relatedOrder.tracking_status || '',
      shippedAt: stableLogistics.shipped_at || '',
    },
    answerContent: rawData.answer_content || '',
    platformReplySubmitted: Boolean(rawData.platform_reply_submitted),
    platformReplyAlreadyExisted: Boolean(rawData.platform_reply_already_existed),
    rawResponseSaved: Boolean(rawData.raw_response_saved),
    sourceType: source || rawData.source_type || '',
    hasRelatedOrder: Boolean(
      relatedOrder.order_no || relatedOrder.product_order_no || relatedOrder.id
      || item.order_no || rawData.order_id || productOrderIds.length,
    ),
    receivedAt: item.received_at,
    createdAt: item.created_at || item.received_at,
    answeredAt: item.answered_at,
    lastReplyAt: emptyText(item.answered_at),
    updatedAt: emptyText(item.updated_at || item.created_at),
    orderInfo: {
      orderNo: emptyText(orderNo),
      paymentMethod: '—',
      receiver: emptyText(item.customer_name),
      amount: 0,
      address: '—',
    },
    productInfo: {
      productName: emptyText(productName),
      sku: '—',
      quantity: 0,
      store: item.store_name || `店铺 #${item.store_id}`,
    },
    replies: rawData.answer_content ? [{ content: rawData.answer_content, createdAt: item.answered_at }] : [],
  };
}

export function adaptCustomerInquiryDetail(item = {}) {
  const source = item.detail || item.item || item.inquiry || item;
  const detail = { detailLoaded: true };
  const content = source.decrypted_content ?? source.decryptedContent ?? source.content ?? source.message;
  const title = source.decrypted_title ?? source.decryptedTitle ?? source.title;
  const readonlyId = source.readonly_id ?? source.readonlyId;
  const storeId = source.store_id ?? source.storeId;
  if (content !== undefined && content !== null) detail.content = content;
  if (typeof title === 'string' && title.trim()) detail.title = title;
  if (readonlyId !== undefined && readonlyId !== null && String(readonlyId).trim()) detail.readonlyId = readonlyId;
  if (storeId !== undefined && storeId !== null) detail.storeId = storeId;
  if (typeof source.platform === 'string' && source.platform.trim()) detail.platform = source.platform;
  return detail;
}

export function naverCustomerInquiryRefresh(data = {}) {
  const status = data.status || data.raw_status || 'unavailable';
  const unavailable = ['unavailable', 'not_open', 'skipped', 'blocked'].includes(status)
    || ['not_open', 'unavailable', 'blocked_by_connection'].includes(data.error_code || data.errorCode);
  const success = status === 'success';
  return {
    status: success ? 'success' : unavailable ? 'unavailable' : status,
    message: data.message || (success ? 'Naver 客服消息刷新完成' : 'Naver 客服消息暂不可用'),
    errorCode: data.error_code || data.errorCode || null,
    createdCount: numberValue(data.created_count ?? data.createdCount),
    updatedCount: numberValue(data.updated_count ?? data.updatedCount),
    platformWrite: Boolean(data.platform_write ?? data.platformWrite),
  };
}

export function adaptSyncLog(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    type: item.sync_type,
    rawStatus: item.status,
    status: adaptStatus(item.status, { success: '성공', failed: '실패', running: '처리중', pending: '대기' }),
    message: item.message,
    startedAt: item.started_at,
    finishedAt: item.finished_at,
    logNo: `SYNC-${item.id ?? '—'}`,
    time: item.finished_at || item.started_at,
    module: '数据同步',
    actionType: item.sync_type,
    operator: 'Codex1 后端',
    objectName: adaptPlatform(item.platform),
    summary: item.message || item.sync_type,
    riskLevel: item.status === 'failed' ? '높음' : '낮음',
  };
}

export function adaptDeviceEnvironment(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    name: item.environment_name,
    deviceType: item.device_type,
    osName: item.os_name,
    browserName: item.browser_name,
    ipLabel: item.ip_label,
    proxyLabel: item.proxy_label,
    status: item.status,
    lastUsedAt: item.last_used_at,
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function toBackendDeviceEnvironmentPayload(item = {}, storeId) {
  return compactPayload({
    store_id: Number(item.storeId || storeId),
    environment_name: String(item.name || '').trim(),
    device_type: String(item.deviceType || '').trim(),
    os_name: item.osName || null,
    browser_name: item.browserName || null,
    ip_label: item.ipLabel || null,
    proxy_label: item.proxyLabel || null,
    status: normalizeDeviceStatusForBackend(item.status),
    last_used_at: item.lastUsedAt || null,
    remark: item.remark || null,
  });
}

export function adaptEmailAccount(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    email: item.email_address,
    address: item.email_address,
    provider: item.provider,
    label: item.account_label,
    purpose: item.account_label,
    hasCredential: Boolean(item.has_password_or_token),
    status: item.status,
    lastCheckedAt: item.last_checked_at,
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function toBackendEmailAccountPayload(item = {}, storeId) {
  return compactPayload({
    store_id: Number(item.storeId || storeId),
    email_address: String(item.email || '').trim(),
    provider: String(item.provider || '').trim(),
    account_label: item.label || null,
    password_or_token: item.credentialInput ? String(item.credentialInput) : undefined,
    status: normalizeAccountStatusForBackend(item.status),
    remark: item.remark || null,
  });
}

export function adaptImportantEmail(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    emailAccountId: item.email_account_id,
    platform: item.platform,
    type: item.mail_type,
    emailType: item.mail_type,
    sender: item.sender,
    subject: item.subject,
    title: item.subject,
    snippet: item.snippet,
    summary: item.snippet,
    receivedAt: item.received_at,
    status: item.status,
    priority: item.priority,
    relatedCaseId: item.related_case_id,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptAppealCase(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: item.platform,
    type: item.case_type,
    title: item.case_title,
    name: item.case_title,
    status: item.case_status,
    caseNo: item.external_case_id,
    deadlineAt: item.deadline_at,
    deadline: item.deadline_at,
    summary: item.summary,
    actionRequired: item.action_required,
    relatedOrderId: item.related_order_id,
    relatedProductId: item.related_product_id,
    submittedAt: item.submitted_at,
    resolvedAt: item.resolved_at,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptCredential(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    rawPlatform: item.platform,
    name: item.credential_name,
    credentialName: item.credential_name,
    vendorId: item.vendor_id,
    clientId: item.client_id,
    market: item.market,
    authStatus: item.auth_status || 'not_configured',
    lastTestedAt: item.last_tested_at,
    tokenExpiresAt: item.token_expires_at,
    apiRemark: item.api_remark,
    status: item.status,
    hasAccessKey: Boolean(item.has_access_key),
    hasSecretKey: Boolean(item.has_secret_key),
    hasAccessToken: Boolean(item.has_access_token),
    hasRefreshToken: Boolean(item.has_refresh_token),
    accessKeyStatus: item.has_access_key ? '已配置' : '未配置',
    secretKeyStatus: item.has_secret_key ? '已配置' : '未配置',
    accessTokenStatus: item.has_access_token ? '已配置' : '未配置',
    refreshTokenStatus: item.has_refresh_token ? '已配置' : '未配置',
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptPlatformLogin(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    platform: adaptPlatform(item.platform),
    rawPlatform: item.platform,
    label: item.login_label,
    account: item.login_account,
    emailAccountId: item.email_account_id,
    deviceEnvironmentId: item.device_environment_id,
    loginStatus: item.login_status,
    status: item.login_status,
    hasLoginPassword: Boolean(item.hasLoginPassword),
    passwordStatus: item.hasLoginPassword ? '已保存密码' : '未保存密码',
    lastLoginCheckAt: item.last_login_check_at,
    remark: item.remark,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptApiCapability(item = {}) {
  return {
    id: item.id,
    platform: adaptPlatform(item.platform),
    rawPlatform: item.platform,
    capabilityKey: item.capability_key,
    capabilityName: item.capability_name,
    apiCategory: item.api_category,
    endpointPath: item.endpoint_path,
    method: item.method,
    requiredCredentialType: item.required_credential_type,
    requiredPermission: item.required_permission,
    ordinaryStoreSupported: item.ordinary_store_supported,
    testStatus: item.test_status,
    testMode: item.test_mode,
    requestParamsSummary: item.request_params_summary,
    responseFieldsSummary: item.response_fields_summary,
    errorCodesSummary: item.error_codes_summary,
    dataUsefulness: item.data_usefulness,
    firstPhaseCandidate: Boolean(item.first_phase_candidate),
    salesSourceType: item.sales_source_type,
    officialDocUrl: item.official_doc_url,
    docCheckedAt: item.doc_checked_at,
    notes: item.notes,
    lastCheckedAt: item.last_checked_at,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function adaptApiCapabilityResult(item = {}) {
  return {
    id: item.id,
    storeId: item.store_id,
    capabilityId: item.capability_id,
    credentialId: item.credential_id,
    testMode: item.test_mode,
    testStatus: item.test_status,
    httpStatus: item.http_status,
    errorCode: item.error_code,
    businessErrorHint: item.business_error_hint || null,
    safeKeywordFlags: item.safe_keyword_flags || null,
    capabilityScope: item.capability_scope || null,
    pathKind: item.path_kind || null,
    permissionResult: item.permission_result,
    rateLimitSummary: item.rate_limit_summary,
    responseFieldsObserved: item.response_fields_observed,
    testedAt: item.tested_at,
    notes: item.notes,
    createdAt: item.created_at,
  };
}

const NAVER_DEFAULT_API_BASE = 'https://api.commerce.naver.com/external';

function trimmedOrNull(value) {
  if (typeof value !== 'string') return value ?? null;
  const trimmed = value.trim();
  return trimmed || null;
}

function optionalSecret(value) {
  const trimmed = trimmedOrNull(value);
  return trimmed || undefined;
}

function normalizeTokenExpiresAt(value) {
  const trimmed = trimmedOrNull(value);
  if (!trimmed) return null;
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

export function toBackendCredentialPayload(item = {}, storeId) {
  const credentialName = item.name || item.credentialName;
  const normalizedPlatform = 'platform' in item ? normalizeCredentialPlatformForBackend(item.platform) : undefined;
  const payload = { store_id: Number(item.storeId || storeId) };
  if ('platform' in item) payload.platform = normalizedPlatform;
  if (credentialName) payload.credential_name = String(credentialName).trim();
  if (normalizedPlatform === 'coupang' && 'vendorId' in item) payload.vendor_id = trimmedOrNull(item.vendorId);
  if (normalizedPlatform === 'naver' && 'clientId' in item) payload.client_id = trimmedOrNull(item.clientId);
  if (normalizedPlatform === 'naver') payload.access_key = null;
  if (normalizedPlatform === 'coupang' && optionalSecret(item.accessKeyInput)) payload.access_key = optionalSecret(item.accessKeyInput);
  if (optionalSecret(item.secretKeyInput)) payload.secret_key = optionalSecret(item.secretKeyInput);
  if (normalizedPlatform === 'naver' && optionalSecret(item.accessTokenInput)) payload.access_token = optionalSecret(item.accessTokenInput);
  if (normalizedPlatform === 'naver' && optionalSecret(item.refreshTokenInput)) payload.refresh_token = optionalSecret(item.refreshTokenInput);
  if (normalizedPlatform === 'naver' && 'tokenExpiresAt' in item) payload.token_expires_at = normalizeTokenExpiresAt(item.tokenExpiresAt);
  if (normalizedPlatform === 'naver') payload.extra_config = { api_base: NAVER_DEFAULT_API_BASE };
  if ('market' in item) payload.market = trimmedOrNull(item.market);
  if ('authStatus' in item) payload.auth_status = normalizeAuthStatusForBackend(item.authStatus);
  if ('lastTestedAt' in item) payload.last_tested_at = item.lastTestedAt || null;
  if ('apiRemark' in item) payload.api_remark = trimmedOrNull(item.apiRemark);
  if ('status' in item) payload.status = normalizeAccountStatusForBackend(item.status);
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

export function toBackendPlatformLoginPayload(item = {}, storeId) {
  const payload = { store_id: Number(item.storeId || storeId) };
  if ('platform' in item) payload.platform = normalizeCredentialPlatformForBackend(item.platform);
  if ('label' in item) payload.login_label = item.label ? String(item.label).trim() : undefined;
  if ('account' in item) payload.login_account = item.account ? String(item.account).trim() : null;
  if (item.passwordInput) payload.login_password = String(item.passwordInput);
  if ('emailAccountId' in item) payload.email_account_id = item.emailAccountId ? Number(item.emailAccountId) : null;
  if ('deviceEnvironmentId' in item) payload.device_environment_id = item.deviceEnvironmentId ? Number(item.deviceEnvironmentId) : null;
  if ('loginStatus' in item || 'status' in item) payload.login_status = normalizeAccountStatusForBackend(item.loginStatus || item.status);
  if ('remark' in item) payload.remark = item.remark || null;
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

export function toBackendApiCapabilityPayload(item = {}) {
  const payload = {};
  if ('platform' in item) payload.platform = normalizeCredentialPlatformForBackend(item.platform);
  if ('capabilityKey' in item) payload.capability_key = String(item.capabilityKey || '').trim();
  if ('capabilityName' in item) payload.capability_name = String(item.capabilityName || '').trim();
  if ('apiCategory' in item) payload.api_category = String(item.apiCategory || '').trim();
  if ('endpointPath' in item) payload.endpoint_path = item.endpointPath ? String(item.endpointPath).trim() : null;
  if ('method' in item) payload.method = item.method ? String(item.method).trim().toUpperCase() : null;
  if ('requiredCredentialType' in item) payload.required_credential_type = item.requiredCredentialType ? String(item.requiredCredentialType).trim() : null;
  if ('requiredPermission' in item) payload.required_permission = item.requiredPermission || null;
  if ('ordinaryStoreSupported' in item) payload.ordinary_store_supported = item.ordinaryStoreSupported || 'unknown';
  if ('testStatus' in item) payload.test_status = item.testStatus || 'not_tested';
  if ('testMode' in item) payload.test_mode = item.testMode || 'docs_only';
  if ('requestParamsSummary' in item) payload.request_params_summary = item.requestParamsSummary || null;
  if ('responseFieldsSummary' in item) payload.response_fields_summary = item.responseFieldsSummary || null;
  if ('errorCodesSummary' in item) payload.error_codes_summary = item.errorCodesSummary || null;
  if ('dataUsefulness' in item) payload.data_usefulness = item.dataUsefulness || 'unknown';
  if ('firstPhaseCandidate' in item) payload.first_phase_candidate = Boolean(item.firstPhaseCandidate);
  if ('salesSourceType' in item) payload.sales_source_type = item.salesSourceType || 'not_applicable';
  if ('officialDocUrl' in item) payload.official_doc_url = item.officialDocUrl ? String(item.officialDocUrl).trim() : null;
  if ('docCheckedAt' in item) payload.doc_checked_at = item.docCheckedAt || null;
  if ('notes' in item) payload.notes = item.notes || null;
  if ('lastCheckedAt' in item) payload.last_checked_at = item.lastCheckedAt || null;
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));
}

export function toBackendApiCapabilityResultPayload(item = {}, storeId) {
  const payload = { store_id: Number(item.storeId || storeId) };
  if ('capabilityId' in item) payload.capability_id = Number(item.capabilityId);
  if ('credentialId' in item) payload.credential_id = item.credentialId ? Number(item.credentialId) : null;
  if ('testMode' in item) payload.test_mode = item.testMode || 'manual';
  if ('testStatus' in item) payload.test_status = item.testStatus || 'planned';
  if ('httpStatus' in item) payload.http_status = item.httpStatus ? Number(item.httpStatus) : null;
  if ('errorCode' in item) payload.error_code = item.errorCode ? String(item.errorCode).trim() : null;
  if ('businessErrorHint' in item) payload.business_error_hint = item.businessErrorHint || null;
  if ('safeKeywordFlags' in item) payload.safe_keyword_flags = item.safeKeywordFlags || null;
  if ('capabilityScope' in item) payload.capability_scope = item.capabilityScope || null;
  if ('pathKind' in item) payload.path_kind = item.pathKind || null;
  if ('permissionResult' in item) payload.permission_result = item.permissionResult || null;
  if ('rateLimitSummary' in item) payload.rate_limit_summary = item.rateLimitSummary || null;
  if ('responseFieldsObserved' in item) payload.response_fields_observed = item.responseFieldsObserved || null;
  if ('testedAt' in item) payload.tested_at = item.testedAt || null;
  if ('notes' in item) payload.notes = item.notes || null;
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined && !Number.isNaN(value)));
}

export function adaptApiCapabilitySummary(data = {}) {
  return {
    semanticNotice: data.semantic_notice || '',
    platformSummary: (data.platform_summary || []).map((item) => ({
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      totalCapabilities: numberValue(item.total_capabilities),
      docsOnlyCount: numberValue(item.docs_only_count),
      manualCount: numberValue(item.manual_count),
      testedSuccessCount: numberValue(item.tested_success_count),
      notTestedCount: numberValue(item.not_tested_count),
      permissionRequiredCount: numberValue(item.permission_required_count),
      unavailableCount: numberValue(item.unavailable_count),
      firstPhaseCandidateCount: numberValue(item.first_phase_candidate_count),
      realReadonlyCount: numberValue(item.real_readonly_count),
      lastCheckedAt: item.last_checked_at,
    })),
    storeResultSummary: (data.store_result_summary || []).map((item) => ({
      storeId: item.store_id,
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      totalResults: numberValue(item.total_results),
      credentialBoundResults: numberValue(item.credential_bound_results),
      docsOnlyCount: numberValue(item.docs_only_count),
      manualCount: numberValue(item.manual_count),
      mockCount: numberValue(item.mock_count),
      sandboxCount: numberValue(item.sandbox_count),
      testedSuccessCount: numberValue(item.tested_success_count),
      testedFailedCount: numberValue(item.tested_failed_count),
      permissionRequiredCount: numberValue(item.permission_required_count),
      unavailableCount: numberValue(item.unavailable_count),
      notTestedCount: numberValue(item.not_tested_count),
      latestTestedAt: item.latest_tested_at,
      missingFirstPhaseCandidates: (item.missing_first_phase_candidates || []).map((candidate) => ({
        capabilityId: candidate.capability_id,
        platform: adaptPlatform(candidate.platform),
        rawPlatform: candidate.platform,
        capabilityKey: candidate.capability_key,
        capabilityName: candidate.capability_name,
        apiCategory: candidate.api_category,
      })),
    })),
    attentionItems: (data.attention_items || []).map((item, index) => ({
      id: item.code || `api-capability-attention-${index + 1}`,
      code: item.code,
      level: item.level || 'info',
      platform: item.platform ? adaptPlatform(item.platform) : null,
      rawPlatform: item.platform,
      storeId: item.store_id,
      count: numberValue(item.count),
      message: item.message,
    })),
  };
}

export function adaptApiCredentialReadiness(data = {}) {
  const storeBound = data.store_bound_readiness || null;
  return {
    semanticNotice: data.semantic_notice || '',
    realApiTestEnabled: Boolean(data.real_api_test_enabled),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    platforms: (data.platforms || []).map((item) => ({
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      credentialStatus: item.credential_status || 'missing',
      readinessStatus: item.readiness_status || 'disabled',
      fields: item.fields || {},
    })),
    storeBoundReadiness: storeBound ? {
      storeId: storeBound.store_id,
      platform: adaptPlatform(storeBound.platform),
      rawPlatform: storeBound.platform,
      credentialId: storeBound.credential_id,
      credentialName: storeBound.credential_name,
      configured: Boolean(storeBound.configured),
      clientIdConfigured: Boolean(storeBound.client_id_configured),
      secretKeyConfigured: Boolean(storeBound.secret_key_configured),
      secretKeyDecryptable: Boolean(storeBound.secret_key_decryptable),
      apiBase: storeBound.api_base,
      channelNoConfigured: Boolean(storeBound.channel_no_configured),
      accessTokenStatus: storeBound.access_token_status || 'missing',
      refreshTokenConfigured: Boolean(storeBound.refresh_token_configured),
      tokenExpiresAt: storeBound.token_expires_at,
      authStatus: storeBound.auth_status,
      missingFields: storeBound.missing_fields || [],
      warnings: storeBound.warnings || [],
    } : null,
  };
}

export function adaptApiCredentialSmokeTest(data = {}) {
  return {
    semanticNotice: data.semantic_notice || '',
    mode: data.mode || 'readonly',
    realApiTestEnabled: Boolean(data.real_api_test_enabled),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    results: (data.results || []).map((item) => ({
      platform: adaptPlatform(item.platform),
      rawPlatform: item.platform,
      enabled: Boolean(item.enabled),
      configured: Boolean(item.configured),
      storeId: item.store_id,
      credentialId: item.credential_id,
      pathKind: item.path_kind,
      capabilityScope: item.capability_scope,
      grantTypeUsed: item.grant_type_used,
      sellerAccountIdConfigured: Boolean(item.seller_account_id_configured),
      channelNoSource: item.channel_no_source,
      channelNoObserved: Boolean(item.channel_no_observed),
      channelNoConfigured: Boolean(item.channel_no_configured),
      channelNoPersisted: Boolean(item.channel_no_persisted),
      multipleChannelsObserved: Boolean(item.multiple_channels_observed),
      businessStatusSummary: item.business_status_summary || {},
      tokenTest: item.token_test || 'skipped',
      sellerOrAccountTest: item.seller_or_account_test || 'skipped',
      productReadTest: item.product_read_test || 'skipped',
      orderReadTest: item.order_read_test || 'skipped',
      settlementReadTest: item.settlement_read_test || 'skipped',
      errorCode: item.error_code || null,
      maskedMessage: item.masked_message || '',
      testedAt: item.tested_at || null,
    })),
  };
}

export function adaptCoupangOrderSyncResult(data = {}) {
  const syncLog = data.sync_log || {};
  const checkpoint = data.checkpoint || {};
  return {
    storeId: data.store_id,
    platform: adaptPlatform(data.platform),
    rawPlatform: data.platform,
    syncType: data.sync_type,
    sourceType: data.source_type,
    writeScope: data.write_scope,
    platformWrite: Boolean(data.platform_write),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    businessTimezone: data.business_timezone,
    startDate: data.start_date,
    endDate: data.end_date,
    windowStartAt: data.window_start_at,
    windowEndAt: data.window_end_at,
    maxPages: numberValue(data.max_pages),
    pageCount: numberValue(data.page_count),
    nextCursorExists: Boolean(data.next_cursor_exists),
    wouldCreate: numberValue(data.would_create),
    wouldUpdate: numberValue(data.would_update),
    createdCount: numberValue(data.created_count),
    updatedCount: numberValue(data.updated_count),
    skippedCount: numberValue(data.skipped_count),
    sampleIds: data.sample_ids || [],
    lastSyncedAt: data.last_synced_at,
    syncLog: {
      id: syncLog.id,
      status: syncLog.status,
      message: syncLog.message,
    },
    checkpoint: {
      id: checkpoint.id,
      lastSyncedAt: checkpoint.last_synced_at,
      windowStartAt: checkpoint.window_start_at,
      windowEndAt: checkpoint.window_end_at,
    },
  };
}

export function adaptCoupangProductSyncResult(data = {}) {
  const syncLog = data.sync_log || {};
  const checkpoint = data.checkpoint || {};
  return {
    storeId: data.store_id,
    platform: adaptPlatform(data.platform),
    rawPlatform: data.platform,
    syncType: data.sync_type,
    sourceType: data.source_type,
    writeScope: data.write_scope,
    platformWrite: Boolean(data.platform_write),
    realApiWriteEnabled: Boolean(data.real_api_write_enabled),
    statusFilter: data.status_filter || 'APPROVED',
    statusSemanticNotice: data.status_semantic_notice || '',
    maxPages: numberValue(data.max_pages),
    pageCount: numberValue(data.page_count),
    nextCursorExists: Boolean(data.next_cursor_exists),
    wouldCreate: numberValue(data.would_create),
    wouldUpdate: numberValue(data.would_update),
    createdCount: numberValue(data.created_count),
    updatedCount: numberValue(data.updated_count),
    skippedCount: numberValue(data.skipped_count),
    sampleIds: data.sample_ids || [],
    perStatus: (data.per_status || []).map((item) => ({
      status: item.status,
      statusSemantic: item.status_semantic || '',
      pageCount: numberValue(item.page_count),
      nextCursorExists: Boolean(item.next_cursor_exists),
      itemCount: numberValue(item.item_count),
      wouldCreate: numberValue(item.would_create),
      wouldUpdate: numberValue(item.would_update),
      skippedCount: numberValue(item.skipped_count),
      sampleIds: item.sample_ids || [],
    })),
    lastSyncedAt: data.last_synced_at,
    syncLog: {
      id: syncLog.id,
      status: syncLog.status,
      message: syncLog.message,
    },
    checkpoint: {
      id: checkpoint.id,
      lastSyncedAt: checkpoint.last_synced_at,
      windowStartAt: checkpoint.window_start_at,
      windowEndAt: checkpoint.window_end_at,
    },
  };
}

export function adaptCoupangFinancialPreviewResult(data = {}) {
  const syncLog = data.sync_log || {};
  return {
    storeId: data.store_id,
    platform: adaptPlatform(data.platform),
    rawPlatform: data.platform,
    syncType: data.sync_type,
    sourceType: data.source_type,
    businessTimezone: data.business_timezone,
    startDate: data.start_date,
    endDate: data.end_date,
    windowStartAt: data.window_start_at,
    windowEndAt: data.window_end_at,
    maxPages: numberValue(data.max_pages),
    pageCount: numberValue(data.page_count),
    nextCursorExists: Boolean(data.next_cursor_exists),
    totalRows: numberValue(data.total_rows),
    sampleIds: data.sample_ids || [],
    sampleRows: (data.sample_rows || []).map(sanitizeFinancialObject),
    summaryTotals: sanitizeFinancialObject(data.summary_totals || {}),
    months: data.months || [],
    perMonth: (data.per_month || []).map((item) => ({
      revenueRecognitionYearMonth: item.revenue_recognition_year_month,
      itemCount: numberValue(item.item_count),
      sampleIds: item.sample_ids || [],
    })),
    semanticNotice: data.semantic_notice || '',
    dateAvailabilityNotice: data.date_availability_notice || '',
    monthSemanticNotice: data.month_semantic_notice || '',
    fieldMappingSuggestion: sanitizeFieldMappingSuggestion(data.field_mapping_suggestion || {}),
    syncLog: {
      id: syncLog.id,
      status: syncLog.status,
      message: syncLog.message,
    },
  };
}

function adaptOperatorTask(item = {}) {
  return {
    taskId: item.task_id || '',
    taskType: item.task_type || '',
    storeId: item.store_id ?? item.storeId ?? null,
    storeName: item.store_name || item.storeName || '',
    platform: adaptPlatform(item.platform),
    priority: numberValue(item.priority),
    title: item.title || '',
    description: item.description || '',
    status: item.status || '',
    count: numberValue(item.count),
    actionPath: item.action_path || '',
    actionLabel: item.action_label || '',
    relatedOrderId: item.related_order_id ?? null,
    relatedBatchId: item.related_batch_id ?? null,
    relatedInquiryId: item.related_inquiry_id ?? null,
    updatedAt: item.updated_at || null,
    stale: item.stale === true,
  };
}

export function adaptOperatorWorkbench(data = {}) {
  const section = (key) => (data.sections?.[key] || []).map(adaptOperatorTask);
  const source = (key) => ({
    sourceStatus: data.sources?.[key]?.status || 'unavailable',
    reasonCode: data.sources?.[key]?.reason_code || '',
    failedStoreCount: numberValue(data.sources?.[key]?.failed_store_count),
    failures: (data.sources?.[key]?.failures || []).map((failure) => ({
      storeId: failure.store_id ?? failure.storeId ?? null,
      storeName: failure.store_name || failure.storeName || '',
      platform: adaptPlatform(failure.platform),
      reasonCode: failure.reason_code || failure.reasonCode || '',
    })),
  });
  return {
    summary: {
      urgent: numberValue(data.summary?.urgent),
      actionRequired: numberValue(data.summary?.action_required),
      waiting: numberValue(data.summary?.waiting),
      completedToday: numberValue(data.summary?.completed_today),
    },
    sections: {
      urgent: section('urgent'),
      action_required: section('action_required'),
      waiting: section('waiting'),
      completed_today: section('completed_today'),
    },
    sources: {
      orders: source('orders'),
      shipping: source('shipping'),
      customer_inquiries: source('customer_inquiries'),
    },
  };
}

export function adaptDashboardSummary(data = {}) {
  const risks = (data.risk_flags || []).map((item, index) => ({
    id: item.code || `backend-risk-${index + 1}`,
    title: '后端风险提醒',
    description: item.message,
    status: item.level || 'info',
  }));
  const latestLogs = (data.latest_sync_logs || []).map(adaptSyncLog);
  const recentOrders = (data.recent_orders || []).map(adaptOrder);
  const pendingCustomers = numberValue(data.open_customer_inquiries);

  const summary = {
    storeTotal: numberValue(data.store_count),
    productTotal: numberValue(data.product_count),
    todayOrderCount: numberValue(data.order_count),
    todaySalesAmount: numberValue(data.total_sales_amount),
    scopeOrderCount: numberValue(data.order_count),
    scopeSalesAmount: numberValue(data.total_sales_amount),
    pendingCustomers,
    pendingAppeals: numberValue(data.open_appeal_cases),
    riskEnvironments: risks.filter((item) => /ENV|DEVICE|IP|LOGIN/i.test(item.id)).length,
    unreadImportantEmails: numberValue(data.unread_important_emails),
    currency: data.currency || 'KRW',
    businessTimezone: data.business_timezone,
    businessDate: data.business_date,
    businessDayStart: data.business_day_start,
    businessDayEnd: data.business_day_end,
    apiCapabilitySummary: adaptApiCapabilitySummary(data.api_capability_summary),
    financialSummary: adaptFinancialSummary(data.financial_summary),
    operatorWorkbench: adaptOperatorWorkbench(data.operator_workbench || {}),
  };

  const todos = pendingCustomers > 0
    ? [{ id: 'backend-inquiries', title: '待回复客服', description: `${pendingCustomers} 条咨询等待回复`, status: '대기중' }]
    : [];

  return {
    ...summary,
    summary,
    risks,
    todos,
    activities: {
      logs: [
        ...latestLogs.map((item) => ({
          ...item,
          module: '同步任务',
          summary: item.message || item.type,
          time: item.finishedAt || item.startedAt || '',
        })),
        ...recentOrders.map((item) => ({
          ...item,
          module: '最近订单',
          summary: `${item.orderNo || '订单'} · ${item.product || ''}`,
          time: item.createdAt || '',
        })),
      ],
      appeals: [],
      customers: [],
      emails: [],
      orders: recentOrders,
    },
    recentOrders,
    latestSyncLogs: latestLogs,
  };
}

export function metricDisplayValue(metric = {}) {
  if (!metric || typeof metric !== 'object') return '-';
  if (metric.display_value !== undefined && metric.display_value !== null) return String(metric.display_value);
  if (metric.displayValue !== undefined && metric.displayValue !== null) return String(metric.displayValue);
  if (metric.value === null || metric.value === undefined) return '?';
  return String(metric.value);
}

function adaptOverviewMetric(metric = {}) {
  return {
    value: metric.value ?? null,
    displayValue: metricDisplayValue(metric),
    dataStatus: metric.data_status || metric.dataStatus || 'unknown',
    reason: metric.reason || '',
  };
}

function adaptOverviewResource(resource = {}) {
  return {
    status: resource.status || 'unknown',
    errorCode: resource.error_code || resource.errorCode || '',
    message: resource.message || '',
    dataStatus: resource.data_status || resource.dataStatus || 'unknown',
  };
}

function adaptStoreOverviewRow(item = {}) {
  const metrics = item.metrics || {};
  const resources = item.resources || {};
  return {
    id: item.store_id || item.id,
    storeId: item.store_id || item.id,
    storeName: item.store_name || item.storeName || item.name || `店铺 #${item.store_id || item.id}`,
    platform: adaptPlatform(item.platform),
    rawPlatform: normalizePlatformForBackend(item.platform),
    ownerName: item.owner_name || item.ownerName || '',
    storeStatus: item.store_status || item.storeStatus || '',
    connectionStatus: item.connection_status || item.connectionStatus || '待同步',
    connectionTone: item.connection_tone || item.connectionTone || 'warning',
    connectionReason: item.connection_reason || item.connectionReason || '',
    lastSyncAt: item.last_sync_at || item.lastSyncAt || '',
    latestManualSyncStatus: item.latest_manual_sync_status || item.latestManualSyncStatus || '',
    metrics: {
      todayOrders: adaptOverviewMetric(metrics.today_orders || metrics.todayOrders),
      pendingShipments: adaptOverviewMetric(metrics.pending_shipments || metrics.pendingShipments),
      abnormalOrders: adaptOverviewMetric(metrics.abnormal_orders || metrics.abnormalOrders),
      inventoryAlerts: adaptOverviewMetric(metrics.inventory_alerts || metrics.inventoryAlerts),
    },
    resources: {
      products: adaptOverviewResource(resources.products),
      orders: adaptOverviewResource(resources.orders),
      customerInquiries: adaptOverviewResource(resources.customer_inquiries || resources.customerInquiries),
    },
    automaticReadStatus: adaptAutomaticReadStatus(item.automatic_read_status),
    automaticReadAttentionSummary: adaptAutomaticReadAttentionSummary(
      item.automatic_read_attention_summary || item.automaticReadAttentionSummary,
    ),
    workbenchSummary: adaptOperatorWorkbench({
      summary: item.workbench_summary || item.workbenchSummary || {},
    }).summary,
  };
}

export function adaptStoreOverview(data = {}) {
  const summary = data.summary || {};
  const stores = (data.stores || []).map(adaptStoreOverviewRow);
  return {
    status: data.status || '',
    dataPolicy: data.data_policy || data.dataPolicy || '',
    businessTimezone: data.business_timezone || data.businessTimezone || '',
    businessDate: data.business_date || data.businessDate || '',
    businessDayStart: data.business_day_start || data.businessDayStart || '',
    businessDayEnd: data.business_day_end || data.businessDayEnd || '',
    stores,
    operatorWorkbench: adaptOperatorWorkbench(data.operator_workbench || data.operatorWorkbench || {}),
    summary: {
      storeCount: numberValue(summary.store_count ?? data.store_count ?? stores.length),
      connectedStoreCount: numberValue(summary.connected_store_count),
      attentionStoreCount: numberValue(summary.attention_store_count),
      ipBlockedStoreCount: numberValue(summary.ip_blocked_store_count),
      ordersUnknownStoreCount: numberValue(summary.orders_unknown_store_count),
      inventoryUnknownStoreCount: numberValue(summary.inventory_unknown_store_count),
      todayOrderCount: numberValue(summary.today_order_count),
      pendingShipmentCount: numberValue(summary.pending_shipment_count),
      abnormalOrderCount: numberValue(summary.abnormal_order_count),
      inventoryAlertCount: numberValue(summary.inventory_alert_count),
    },
  };
}

export function adaptAiDailyContext(data = {}) {
  return {
    date: data.date,
    businessTimezone: data.business_timezone,
    businessDayStart: data.business_day_start,
    businessDayEnd: data.business_day_end,
    scope: {
      storeId: data.scope?.store_id ?? null,
      platform: data.scope?.platform ? adaptPlatform(data.scope.platform) : null,
    },
    salesSummary: data.sales_summary || {},
    orderSummary: data.order_summary || {},
    customerInquirySummary: data.customer_inquiry_summary || {},
    syncSummary: data.sync_summary || {},
    financialContext: adaptFinancialSummary(data.financial_context),
    apiCapabilityContext: adaptApiCapabilitySummary(data.api_capability_context),
    riskFlags: data.risk_flags || [],
    recommendedFocus: data.recommended_focus || [],
  };
}

function operationAuditRiskLabel(item = {}) {
  const statusText = String(item.status_label_zh || item.status || '');
  const nextAction = String(item.next_action_label_zh || '');
  if (statusText.includes('失败') || statusText.includes('阻断')) return '高风险';
  if (statusText.includes('计划') || nextAction.includes('复核') || nextAction.includes('批准')) return '中风险';
  return '低风险';
}

export function adaptOperationAuditLog(item = {}) {
  const advanced = item.advanced_details || {};
  const statusLabel = item.status_label_zh || item.status || '待确认';
  const targetLabel = item.target_label || item.targetLabel || '业务对象';
  const platformLabel = item.platform_label || adaptPlatform(item.platform) || '本地系统';
  const changedFields = item.changed_fields_label_zh || [];
  const summaryParts = [
    item.counts_summary_label_zh,
    changedFields.length ? `字段：${changedFields.join('、')}` : '',
    item.safety_label_zh,
  ].filter(Boolean);

  return {
    id: `audit-${item.id}`,
    auditId: item.id,
    time: item.created_at,
    objectName: targetLabel,
    module: `${platformLabel} / 操作审计`,
    actionType: item.action_label_zh || '本地运营操作',
    operator: item.actor_label || item.actor_type_label || '系统',
    status: statusLabel,
    rawStatus: advanced.status || item.status || statusLabel,
    riskLevel: operationAuditRiskLabel(item),
    summary: summaryParts.join('；') || '安全审计记录',
    nextStep: item.next_action_label_zh || '无需处理，保留记录备查。',
    backupEvidence: item.backup_evidence_label_zh || '暂无备份证据',
    recoveryEvidence: item.backup_evidence_label_zh || '暂无恢复证据',
    safetyLabel: item.safety_label_zh || '未返回敏感原文',
    reasonLabel: item.reason_label_zh || '',
    changedFields,
    source: 'Codex1 操作审计',
    auditRuntimeSource: 'operation_audit_logs',
    advancedDetails: advanced,
    beforeData: null,
    afterData: null,
  };
}

export function adaptOperationAuditLogList(data = {}) {
  const items = (data.items || []).map(adaptOperationAuditLog);
  return {
    data: items,
    items,
    total: numberValue(data.total),
    limit: numberValue(data.limit),
    offset: numberValue(data.offset),
    limitWasCapped: Boolean(data.limit_was_capped),
    includeAdvanced: Boolean(data.include_advanced),
    status: data.status,
    runtimeStatus: data.status,
    businessMessage: data.business_message || '',
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled),
    readonlyLocalRoute: Boolean(data.readonly_local_route),
  };
}

export function adaptOperationAuditSummary(data = {}) {
  return {
    status: data.status || '',
    runtimeStatus: data.audit_runtime_status || 'empty',
    total: numberValue(data.total),
    statusCounts: data.status_counts_label_zh || {},
    backupEvidenceCount: numberValue(data.backup_evidence_count),
    restoreEvidenceCount: numberValue(data.restore_evidence_count),
    needsAttentionCount: numberValue(data.needs_attention_count),
    latestAuditTime: data.latest_audit_time || null,
    businessMessage: data.business_message || '',
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled),
    readonlyLocalRoute: Boolean(data.readonly_local_route),
  };
}

function backupStatusLabel(item = {}) {
  if (item.manifestValid && item.sensitiveScanPassed && item.backupExists && item.backupSizeMatches) {
    return '备份可用';
  }
  if (!item.backupExists) return '备份文件缺失';
  if (!item.manifestValid || !item.sensitiveScanPassed) return '需要复核';
  if (!item.backupSizeMatches) return '大小不一致';
  return '待确认';
}

function formatBytes(value) {
  const bytes = numberValue(value);
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function adaptBackupReportItem(item = {}) {
  const adapted = {
    id: item.backup_id || item.manifest_path || item.backup_path,
    backupId: item.backup_id,
    createdAt: item.created_at,
    phase: item.phase || '未标记阶段',
    operationType: item.operation_type || 'local_backup',
    actorLabel: item.created_by_actor_label || '本地操作人',
    backupLocation: item.backup_inside_root === false ? '备份目录外，需复核' : '本地备份目录内',
    backupSha256Abbrev: item.backup_sha256_abbrev || '',
    backupSizeBytes: numberValue(item.backup_size_bytes),
    backupSizeLabel: formatBytes(item.backup_size_bytes),
    sqliteIntegrityCheck: item.sqlite_integrity_check || 'unknown',
    retentionClass: item.retention_class || '',
    retentionUntil: item.retention_until || '',
    protectedFromAutoDelete: Boolean(item.protected_from_auto_delete),
    restoreDrillStatus: item.restore_drill_status || 'pending',
    baselineCounts: item.baseline_counts || {},
    manifestValid: Boolean(item.manifest_valid),
    sensitiveScanPassed: Boolean(item.sensitive_scan_passed),
    backupExists: Boolean(item.backup_exists),
    backupInsideRoot: item.backup_inside_root !== false,
    backupSizeMatches: Boolean(item.backup_size_matches),
    rawResponseSaved: Boolean(item.raw_response_saved),
    secretsSaved: Boolean(item.secrets_saved),
    privacyFieldsRedacted: item.privacy_fields_redacted !== false,
    advancedDetails: {
      backup_id: item.backup_id,
      phase: item.phase,
      operation_type: item.operation_type,
      created_at: item.created_at,
      backup_location: item.backup_inside_root === false ? 'outside_root' : 'approved_root',
      backup_sha256_abbrev: item.backup_sha256_abbrev,
      backup_size_bytes: item.backup_size_bytes,
      sqlite_integrity_check: item.sqlite_integrity_check,
      retention_class: item.retention_class,
      retention_until: item.retention_until,
      protected_from_auto_delete: item.protected_from_auto_delete,
      restore_drill_status: item.restore_drill_status,
      baseline_counts: item.baseline_counts || {},
      manifest_valid: item.manifest_valid,
      sensitive_scan_passed: item.sensitive_scan_passed,
      backup_exists: item.backup_exists,
      backup_inside_root: item.backup_inside_root,
      backup_size_matches: item.backup_size_matches,
      raw_response_saved: false,
      secrets_saved: false,
      privacy_fields_redacted: item.privacy_fields_redacted !== false,
    },
  };
  return {
    ...adapted,
    status: backupStatusLabel(adapted),
    evidence: adapted.manifestValid && adapted.sensitiveScanPassed ? '清单和安全检查通过' : '需要管理员复核',
    nextStep: adapted.manifestValid && adapted.sensitiveScanPassed && adapted.backupExists
      ? '保留备份证据，恢复操作仍需单独审批。'
      : '请管理员检查备份清单和文件状态。',
  };
}

export function adaptBackupLocalReport(data = {}) {
  const items = (data.items || []).map(adaptBackupReportItem);
  return {
    status: data.status || '',
    businessMessage: data.business_message || '',
    backupReportReadonly: data.backup_report_readonly !== false,
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled),
    backupCount: numberValue(data.backup_count),
    manifestCount: numberValue(data.manifest_count),
    allManifestsValid: Boolean(data.all_manifests_valid),
    allSensitiveScansPassed: Boolean(data.all_sensitive_scans_passed),
    items,
    latestBackup: data.latest_backup ? adaptBackupReportItem(data.latest_backup) : null,
    summary: data.summary || {},
    backupDeleted: Boolean(data.backup_deleted),
    realRestoreExecuted: Boolean(data.real_restore_executed),
    productionDbTouched: Boolean(data.production_db_touched),
    rowsWritten: numberValue(data.rows_written),
    rawResponseSaved: Boolean(data.raw_response_saved),
    secretsSaved: Boolean(data.secrets_saved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open),
    platformWritesEnabled: Boolean(data.platform_writes_enabled),
    sensitiveScanPassed: data.sensitive_scan_passed !== false,
  };
}

export function adaptBackupLocalReportSummary(data = {}) {
  return {
    status: data.status || '',
    businessMessage: data.business_message || '',
    backupReportReadonly: data.backup_report_readonly !== false,
    publicEndpointEnabled: Boolean(data.public_endpoint_enabled),
    backupCount: numberValue(data.backup_count),
    manifestCount: numberValue(data.manifest_count),
    reportedItemCount: numberValue(data.reported_item_count),
    validManifestCount: numberValue(data.valid_manifest_count),
    sensitiveScanPassedCount: numberValue(data.sensitive_scan_passed_count),
    existingBackupCount: numberValue(data.existing_backup_count),
    needsAttentionCount: numberValue(data.needs_attention_count),
    allManifestsValid: Boolean(data.all_manifests_valid),
    allSensitiveScansPassed: Boolean(data.all_sensitive_scans_passed),
    latestBackup: data.latest_backup ? adaptBackupReportItem(data.latest_backup) : null,
    backupDeleted: Boolean(data.backup_deleted),
    realRestoreExecuted: Boolean(data.real_restore_executed),
    productionDbTouched: Boolean(data.production_db_touched),
    rowsWritten: numberValue(data.rows_written),
    rawResponseSaved: Boolean(data.raw_response_saved),
    secretsSaved: Boolean(data.secrets_saved),
    privacyFieldsRedacted: data.privacy_fields_redacted !== false,
    formalSyncOpen: Boolean(data.formal_sync_open),
    platformWritesEnabled: Boolean(data.platform_writes_enabled),
    sensitiveScanPassed: data.sensitive_scan_passed !== false,
  };
}

const manualSyncResourceLabels = {
  products: '商品',
  orders: '订单',
  customer_inquiries: '客服消息',
};

const manualSyncConnectionErrorCodes = new Set([
  'ip_not_allowed',
  'auth_failed',
  'permission_forbidden',
  'product_api_not_allowed',
  'order_api_not_allowed',
  'credential_not_ready',
  'credential_invalid',
  'credential_not_found',
  'channel_no_missing',
  'channel_selection_required',
  'blocked_by_connection',
]);

function manualSyncConnectionIssue(items = []) {
  return items.find((item) => manualSyncConnectionErrorCodes.has(String(item.errorCode || '').toLowerCase())
    || String(item.message || '').includes('平台连接未通过'));
}

function manualSyncStatusLabel(status, items = []) {
  const ipBlocked = items.find((item) => item.errorCode === 'ip_not_allowed' || String(item.message || '').includes('IP 白名单未通过'));
  if (ipBlocked) return '最近一次同步：IP 白名单未通过';

  const permissionBlocked = items.find((item) => String(item.message || '').includes('API 权限未开通')
    || ['auth_failed', 'permission_forbidden', 'product_api_not_allowed', 'order_api_not_allowed'].includes(String(item.errorCode || '').toLowerCase()));
  if (permissionBlocked) return '最近一次同步：API 权限未开通';

  const channelBlocked = items.find((item) => ['channel_no_missing', 'channel_selection_required'].includes(String(item.errorCode || '').toLowerCase()));
  if (channelBlocked) return '最近一次同步：店铺频道未确认';

  const credentialBlocked = items.find((item) => ['credential_not_ready', 'credential_invalid', 'credential_not_found'].includes(String(item.errorCode || '').toLowerCase()));
  if (credentialBlocked) return '最近一次同步：API 资料未配置完整';

  if (manualSyncConnectionIssue(items)) return '最近一次同步：平台连接未通过';

  if (status === 'success') return '本地同步完成';
  if (status === 'partial_success') return '部分同步完成';

  const failed = items.find((item) => item.status === 'failed');
  if (failed) return failed.message || '同步失败';

  const customerNotOpen = items.find((item) => item.resource === 'customer_inquiries' && item.errorCode === 'not_open');
  if (customerNotOpen && items.length === 1) return '客服消息暂未接入';

  const skipped = items.find((item) => item.status === 'skipped');
  if (skipped) return skipped.message || '待同步';

  return '待同步';
}

function manualSyncModalTitle(status, items = []) {
  if (manualSyncConnectionIssue(items)) return '平台连接未通过（本次手动同步结果）';
  if (status === 'success') return '手动同步结果';
  if (status === 'partial_success') return '手动同步结果';
  return '手动同步结果';
}

function adaptManualBatchSyncItem(item = {}) {
  return {
    status: item.status || 'skipped',
    platform: adaptPlatform(item.platform),
    rawPlatform: item.platform,
    resource: item.resource,
    resourceLabel: manualSyncResourceLabels[item.resource] || item.resource || '-',
    message: item.message || '',
    errorCode: item.error_code || null,
    createdCount: numberValue(item.created_count),
    updatedCount: numberValue(item.updated_count),
    skippedCount: numberValue(item.skipped_count),
    deletedCount: numberValue(item.deleted_count),
    fullSnapshot: Boolean(item.full_snapshot),
    deleteExecuted: Boolean(item.delete_executed),
    platformWrite: Boolean(item.platform_write),
    sourceType: item.source_type || '',
    rawStatus: item.raw_status || '',
  };
}

export function manualBatchSyncResult(data = {}) {
  const items = (data.items || []).map(adaptManualBatchSyncItem);
  const summary = data.summary || {};
  const normalizedItems = items.map((item) => {
    if (item.resource !== 'customer_inquiries') return item;
    const unavailable = ['not_open', 'unavailable'].includes(String(item.errorCode || '').toLowerCase())
      || item.status === 'skipped';
    return {
      ...item,
      status: unavailable ? 'skipped' : item.status,
      message: unavailable
        ? '客服消息暂不可用'
        : item.status === 'success'
          ? '客服消息同步完成'
          : '客服消息同步结果待确认',
    };
  });
  return {
    status: data.status || 'skipped',
    statusLabel: manualSyncStatusLabel(data.status, normalizedItems),
    modalTitle: manualSyncModalTitle(data.status, items),
    connectionBlocked: Boolean(manualSyncConnectionIssue(items)),
    storeId: data.store_id,
    storePlatform: data.store_platform,
    requestedPlatforms: data.requested_platforms || [],
    replacePolicy: data.replace_policy || '',
    deletePolicy: data.delete_policy || '',
    platformWrite: Boolean(data.platform_write),
    items: normalizedItems,
    summary: {
      successCount: numberValue(summary.success_count),
      failedCount: numberValue(summary.failed_count),
      skippedCount: numberValue(summary.skipped_count),
      createdCount: numberValue(summary.created_count),
      updatedCount: numberValue(summary.updated_count),
      deletedCount: numberValue(summary.deleted_count),
    },
    syncLog: data.sync_log ? {
      id: data.sync_log.id,
      status: data.sync_log.status,
      message: data.sync_log.message,
    } : null,
  };
}

export function manualNaverOrderRefreshResult(data = {}) {
  const status = data.status || 'skipped';
  const createdCount = numberValue(data.created_count ?? data.createdCount);
  const updatedCount = numberValue(data.updated_count ?? data.updatedCount);
  const skippedCount = numberValue(data.skipped_count ?? data.skippedCount);
  const message = data.message || (
    status === 'success'
      ? `本地订单刷新完成：新增 ${createdCount}，更新 ${updatedCount}，跳过 ${skippedCount}。不会回填平台。`
      : 'Naver 订单本地刷新暂未完成'
  );
  return {
    status,
    statusLabel: status === 'success' ? '本地订单刷新完成' : message,
    storeId: data.store_id ?? data.storeId,
    platform: adaptPlatform(data.platform || 'naver'),
    resource: data.resource || 'orders',
    message,
    errorCode: data.error_code || data.errorCode || null,
    createdCount,
    updatedCount,
    skippedCount,
    noChangeCount: numberValue(data.no_change_count ?? data.noChangeCount),
    platformWrite: Boolean(data.platform_write ?? data.platformWrite),
    platformWritesEnabled: Boolean(data.platform_writes_enabled ?? data.platformWritesEnabled),
    rawResponseSaved: Boolean(data.raw_response_saved ?? data.rawResponseSaved),
    privacyFieldsRedacted: Boolean(data.privacy_fields_redacted ?? data.privacyFieldsRedacted ?? true),
    addressSaved: Boolean(data.address_saved ?? data.addressSaved),
    sourceType: data.source_type || data.sourceType || '',
    rawStatus: data.raw_status || data.rawStatus || '',
    sampleIds: data.sample_ids || data.sampleIds || [],
    syncLog: data.sync_log ? {
      id: data.sync_log.id,
      status: data.sync_log.status,
      message: data.sync_log.message,
    } : null,
  };
}

export function adaptList(data, adapter) {
  const source = Array.isArray(data) ? { items: data, total: data.length } : (data || {});
  const items = (source.items || []).map(adapter);
  return {
    data: items,
    items,
    total: source.total ?? items.length,
    page: source.page ?? 1,
    pageSize: source.page_size ?? source.pageSize ?? (items.length || 10),
    includeTestOrders: Boolean(source.include_test_orders ?? source.includeTestOrders ?? false),
    testOrdersExcluded: Number(source.test_orders_excluded ?? source.testOrdersExcluded ?? 0),
  };
}

export const adapters = {
  store: adaptStore,
  product: adaptProduct,
  order: adaptOrder,
  storeOnboarding: adaptStoreOnboarding,
  orderLogisticsTrace: adaptOrderLogisticsTrace,
  customerInquiry: adaptCustomerInquiry,
  customerInquiryDetail: adaptCustomerInquiryDetail,
  naverCustomerInquiryRefresh,
  syncLog: adaptSyncLog,
  deviceEnvironment: adaptDeviceEnvironment,
  emailAccount: adaptEmailAccount,
  importantEmail: adaptImportantEmail,
  appealCase: adaptAppealCase,
  credential: adaptCredential,
  platformLogin: adaptPlatformLogin,
  apiCapability: adaptApiCapability,
  apiCapabilityResult: adaptApiCapabilityResult,
  apiCapabilitySummary: adaptApiCapabilitySummary,
  apiCredentialReadiness: adaptApiCredentialReadiness,
  apiCredentialSmokeTest: adaptApiCredentialSmokeTest,
  operationAuditLog: adaptOperationAuditLog,
  operationAuditLogList: adaptOperationAuditLogList,
  operationAuditSummary: adaptOperationAuditSummary,
  backupReportItem: adaptBackupReportItem,
  backupLocalReport: adaptBackupLocalReport,
  backupLocalReportSummary: adaptBackupLocalReportSummary,
  storeOverview: adaptStoreOverview,
  metricDisplayValue,
  manualBatchSyncResult,
  manualNaverOrderRefreshResult,
  coupangOrderSyncResult: adaptCoupangOrderSyncResult,
  coupangProductSyncResult: adaptCoupangProductSyncResult,
  coupangFinancialPreviewResult: adaptCoupangFinancialPreviewResult,
  naverOrderCompletePreview: adaptNaverOrderCompletePreview,
  toBackendStorePayload,
  toBackendDeviceEnvironmentPayload,
  toBackendEmailAccountPayload,
  toBackendCredentialPayload,
  toBackendPlatformLoginPayload,
  toBackendApiCapabilityPayload,
  toBackendApiCapabilityResultPayload,
  dashboardSummary: adaptDashboardSummary,
  aiDailyContext: adaptAiDailyContext,
  list: adaptList,
};

export default adapters;
