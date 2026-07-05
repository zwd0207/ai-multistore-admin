import { getNaverOrderStatusPresentation, normalizeNaverOrderStatus } from './naverOrderFulfillment';

export const SHIPPING_PHASE = 'Shipping-3A-to-3E';
export const SHIPPING_EXPORT_MOCK_PHASE = 'Shipping-3D';
export const SHIPPING_FILE_TYPE = 'shipping_request';
export const SHIPPING_FILE_FORMAT = 'xlsx';

export const UNSHIPPED_ORDER_STATUSES = new Set([
  'PAYED',
  'PLACE_PRODUCT_ORDER',
  'READY',
  'DELIVERY_READY',
]);

const EXCLUDED_ORDER_STATUSES = new Set([
  'DISPATCHED',
  'DELIVERING',
  'DELIVERED',
  'CANCELED',
  'CANCEL_REQUEST',
  'RETURN_REQUEST',
  'EXCHANGE_REQUEST',
]);

function normalizeText(value) {
  return String(value || '').trim();
}

function normalizeKeyPart(value) {
  return normalizeText(value)
    .toLocaleLowerCase('ko-KR')
    .replace(/\s+/g, ' ')
    .replace(/[|,，]/g, ' ')
    .trim();
}

function normalizePlatform(value) {
  return normalizeText(value).toLowerCase();
}

function storeIdOf(item = {}) {
  return item.storeId ?? item.store_id ?? item.storeID ?? '';
}

function platformOf(item = {}) {
  return normalizePlatform(item.rawPlatform || item.platform);
}

function rawOrderStatusOf(order = {}) {
  return normalizeText(order.rawStatus || order.order_status || order.status || '');
}

function rawDeliveryStatusOf(order = {}) {
  return normalizeText(order.deliveryStatus || order.delivery_status || '');
}

function productNameOf(order = {}) {
  return normalizeText(order.productName || order.product || order.product_name || '');
}

function optionNameOf(order = {}) {
  return normalizeText(order.optionName || order.option_name || order.rawData?.option_name || order.raw_data?.option_name || '');
}

function orderedAtOf(order = {}) {
  return order.orderedAt || order.ordered_at || order.createdAt || order.created_at || '';
}

function amountOf(order = {}) {
  return Number(order.amount ?? order.order_amount ?? 0);
}

function isHashedIdentifier(value) {
  return /^id-hash-[a-z0-9_-]+$/i.test(normalizeText(value));
}

function orderReferenceOf(order = {}) {
  const rawReference = normalizeText(order.fullOrderNo || order.orderNo || order.external_order_id || order.orderHash || '');
  if (!rawReference) return order.id ? `本地订单 #${order.id}` : '本地订单';
  if (isHashedIdentifier(rawReference)) return order.id ? `本地订单 #${order.id}` : '本地订单';
  return rawReference;
}

function isSameStore(item = {}, selectedStoreId = '') {
  if (!selectedStoreId) return true;
  return String(storeIdOf(item)) === String(selectedStoreId);
}

function isTargetPlatform(item = {}, platform = 'naver') {
  return platformOf(item) === normalizePlatform(platform);
}

function isUnshippedOrder(order = {}) {
  const normalizedStatus = normalizeNaverOrderStatus(rawOrderStatusOf(order));
  const normalizedDeliveryStatus = normalizeNaverOrderStatus(rawDeliveryStatusOf(order));
  if (EXCLUDED_ORDER_STATUSES.has(normalizedStatus)) return false;
  return UNSHIPPED_ORDER_STATUSES.has(normalizedStatus) || UNSHIPPED_ORDER_STATUSES.has(normalizedDeliveryStatus);
}

export function buildMappingKey(productName, optionName) {
  return `${normalizeKeyPart(productName)}::${normalizeKeyPart(optionName)}`;
}

export function buildUnshippedOrderCandidates(orders = [], {
  selectedStoreId = '',
  platform = 'naver',
} = {}) {
  return orders
    .filter((order) => isSameStore(order, selectedStoreId))
    .filter((order) => isTargetPlatform(order, platform))
    .filter(isUnshippedOrder)
    .map((order) => {
      const rawStatus = rawOrderStatusOf(order);
      const statusPresentation = getNaverOrderStatusPresentation(rawStatus);
      const productName = productNameOf(order);
      const optionName = optionNameOf(order);
      return {
        id: order.id,
        storeId: storeIdOf(order),
        platform: platformOf(order),
        orderNo: orderReferenceOf(order),
        productOrderNo: order.productOrderNo || order.external_product_order_id || order.productOrderHash || '',
        productName,
        optionName,
        quantity: Number(order.quantity || 0),
        amount: amountOf(order),
        currency: order.currency || 'KRW',
        orderedAt: orderedAtOf(order),
        rawStatus,
        statusLabel: statusPresentation.label,
        sourceType: order.sourceType || order.source_type || 'local_order',
        mappingKey: buildMappingKey(productName, optionName),
      };
    });
}

export function createInitialLogisticsMappings(candidates = [], seedMappings = []) {
  const normalizedSeed = seedMappings.map((item) => ({
    ...item,
    storeId: storeIdOf(item),
    platform: platformOf(item) || 'naver',
    mappingKey: buildMappingKey(item.productName, item.optionName),
  }));

  const nextMappings = [...normalizedSeed];
  const knownKeys = new Set(nextMappings.map((item) => item.mappingKey));
  const firstCandidate = candidates[0];
  if (firstCandidate && !knownKeys.has(firstCandidate.mappingKey)) {
    nextMappings.unshift({
      id: `shipping-map-auto-${firstCandidate.id || 'first'}`,
      storeId: firstCandidate.storeId,
      platform: firstCandidate.platform || 'naver',
      productName: firstCandidate.productName,
      optionName: firstCandidate.optionName,
      logisticsInventoryCode: 'PXG-AUTO-MATCH-001',
      logisticsProviderName: '韩国仓 A',
      currentStockQuantity: Math.max(firstCandidate.quantity || 1, 5),
      mappingVersion: 'shipping_mapping_mock_v1',
      isActive: true,
      mappingKey: firstCandidate.mappingKey,
      autoSeeded: true,
    });
  }
  return nextMappings;
}

export function updateLogisticsStockQuantity(mappings = [], mappingId, nextQuantity) {
  const quantity = Math.max(0, Number(nextQuantity || 0));
  return mappings.map((item) => (
    String(item.id) === String(mappingId)
      ? { ...item, currentStockQuantity: quantity, lastManualUpdatedAt: new Date().toISOString() }
      : item
  ));
}

function classifyStock(mapping, quantity) {
  if (!mapping) return { status: 'unmatched', label: '需要维护库存编号', tone: 'warning' };
  const stock = Number(mapping.currentStockQuantity ?? 0);
  if (stock <= 0) return { status: 'out_of_stock', label: '物流库存为 0', tone: 'danger' };
  if (stock < Number(quantity || 0)) return { status: 'insufficient', label: '物流库存不足', tone: 'warning' };
  if (stock <= 3) return { status: 'low_stock', label: '物流库存偏低', tone: 'warning' };
  return { status: 'ready', label: '可导出', tone: 'success' };
}

export function buildLogisticsInventoryMappingMockGate({
  candidates = [],
  mappings = [],
  selectedStoreId = '',
  platform = 'naver',
} = {}) {
  const mappingByKey = new Map(mappings
    .filter((item) => item.isActive !== false)
    .filter((item) => isSameStore(item, selectedStoreId))
    .filter((item) => isTargetPlatform(item, platform))
    .map((item) => [item.mappingKey || buildMappingKey(item.productName, item.optionName), item]));

  const rows = candidates.map((candidate) => {
    const mapping = mappingByKey.get(candidate.mappingKey);
    const stockState = classifyStock(mapping, candidate.quantity);
    return {
      ...candidate,
      mappingId: mapping?.id || '',
      logisticsInventoryCode: mapping?.logisticsInventoryCode || '',
      logisticsProviderName: mapping?.logisticsProviderName || '',
      currentStockQuantity: Number(mapping?.currentStockQuantity ?? 0),
      matchStatus: mapping ? 'matched' : 'unmatched',
      stockStatus: stockState.status,
      stockStatusLabel: stockState.label,
      stockTone: stockState.tone,
      exportReady: Boolean(mapping && stockState.status === 'ready'),
      handlingNote: mapping
        ? stockState.label
        : '请先维护商品和选项对应的物流商库存编号。',
    };
  });

  const matchedCount = rows.filter((row) => row.matchStatus === 'matched').length;
  const unmatchedCount = rows.length - matchedCount;
  const exportReadyCount = rows.filter((row) => row.exportReady).length;
  const insufficientStockCount = rows.filter((row) => ['out_of_stock', 'insufficient', 'low_stock'].includes(row.stockStatus)).length;
  const status = rows.length === 0
    ? 'empty'
    : unmatchedCount > 0
      ? 'needs_mapping'
      : insufficientStockCount > 0
        ? 'stock_attention'
        : 'ready';

  return {
    phase: 'Shipping-2F',
    status,
    businessMessage: rows.length === 0
      ? '当前没有可用于发货辅助的未发货订单。'
      : `已检查 ${rows.length} 条未发货候选，${matchedCount} 条已匹配库存编号，${exportReadyCount} 条可进入导出预览。`,
    rows,
    totalCandidates: rows.length,
    matchedCount,
    unmatchedCount,
    insufficientStockCount,
    exportReadyCount,
    realApiCalled: false,
    realDatabaseWritten: false,
    ordersWritten: false,
    productsWritten: false,
    syncLogWritten: false,
    testedSuccessWritten: false,
    operationAuditRowsWritten: false,
    formalOrderSyncOpen: false,
    platformWritesEnabled: false,
    rawResponseSaved: false,
  };
}

function simpleHash(text = '') {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash).toString(16).padStart(8, '0').slice(0, 10);
}

export function buildShippingExcelExportMock({
  rows = [],
  selectedStore = {},
  selectedStoreId = '',
  includeReceiverPrivacy = false,
} = {}) {
  const exportRows = rows.filter((row) => row.exportReady);
  const createdAt = new Date().toISOString();
  const fileName = `naver-shipping-request-store-${selectedStoreId || selectedStore?.id || 'local'}-${createdAt.slice(0, 10)}.xlsx`;
  const fingerprint = simpleHash(JSON.stringify(exportRows.map((row) => ({
    orderNo: row.orderNo,
    productName: row.productName,
    optionName: row.optionName,
    quantity: row.quantity,
    logisticsInventoryCode: row.logisticsInventoryCode,
  }))));

  return {
    phase: SHIPPING_EXPORT_MOCK_PHASE,
    fileType: SHIPPING_FILE_TYPE,
    fileFormat: SHIPPING_FILE_FORMAT,
    fileName,
    fileHash: `mock-${fingerprint}`,
    generatedAt: createdAt,
    rowCount: exportRows.length,
    matchedRowCount: exportRows.length,
    unmatchedRowCount: rows.length - exportRows.length,
    includeReceiverPrivacy,
    fileGenerated: false,
    filePersisted: false,
    exportRecordWritten: false,
    downloadRecordWritten: false,
    operationAuditRowsWritten: false,
    exportRecordSchemaPlanned: true,
    auditLinkagePlanned: true,
    trackingImportContractPlanned: true,
    trackingNumberImportOpen: false,
    realApiCalled: false,
    realDatabaseWritten: false,
    formalOrderSyncOpen: false,
    platformWritesEnabled: false,
    businessMessage: 'mock 模式只生成页面预览；backend 模式可生成本地 Excel 文件并写入导出记录。',
    rows: exportRows.map((row) => ({
      platform: 'naver',
      storeName: selectedStore?.name || `store-${selectedStoreId || row.storeId || 'local'}`,
      orderDate: row.orderedAt,
      orderNo: row.orderNo,
      productName: row.productName,
      optionName: row.optionName,
      quantity: row.quantity,
      logisticsInventoryCode: row.logisticsInventoryCode,
      logisticsProviderName: row.logisticsProviderName,
      logisticsCurrentStock: row.currentStockQuantity,
      matchStatus: '已匹配',
      note: 'Excel mock 预览，尚未生成真实文件。',
    })),
  };
}

export function buildShippingAssistantSummary(gate = {}) {
  return {
    unshippedCandidates: gate.totalCandidates || 0,
    matchedCount: gate.matchedCount || 0,
    unmatchedCount: gate.unmatchedCount || 0,
    stockAttentionCount: gate.insufficientStockCount || 0,
    exportReadyCount: gate.exportReadyCount || 0,
  };
}
