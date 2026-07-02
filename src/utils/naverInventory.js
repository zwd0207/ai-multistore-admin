export const NAVER_LOW_STOCK_THRESHOLD = 5;
const MAX_ATTENTION_ITEMS = 5;

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function normalizeText(value) {
  return String(value || '').trim();
}

export function normalizeStockValue(value) {
  if (value === null || value === undefined || value === '') return null;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue < 0) return null;
  return numericValue;
}

export function getInventoryStatusForStock(value, threshold = NAVER_LOW_STOCK_THRESHOLD) {
  const stock = normalizeStockValue(value);
  if (stock === null) {
    return {
      key: 'invalid',
      label: '库存数据异常',
      tone: 'warning',
      stockLabel: '-',
    };
  }
  if (stock === 0) {
    return {
      key: 'out_of_stock',
      label: '缺货',
      tone: 'danger',
      stockLabel: '0',
    };
  }
  if (stock < threshold) {
    return {
      key: 'low_stock',
      label: '低库存',
      tone: 'warning',
      stockLabel: String(stock),
    };
  }
  return {
    key: 'normal',
    label: '库存正常',
    tone: 'success',
    stockLabel: String(stock),
  };
}

function getProductStock(product = {}) {
  return normalizeStockValue(product.stock ?? product.stock_quantity);
}

function firstText(...values) {
  const value = values.find((item) => item !== undefined && item !== null && String(item).trim() !== '');
  return value === undefined ? '' : String(value).trim();
}

function buildInventoryItem(product = {}, status = {}, stock = null) {
  return {
    id: product.id,
    name: firstText(product.name, product.product_name, '未命名商品'),
    status: firstText(product.status, product.rawStatus, product.raw_status, '-'),
    sourceType: firstText(product.sourceType, product.source_type),
    stock,
    stockLabel: status.stockLabel,
    statusKey: status.key,
    statusLabel: status.label,
    tone: status.tone,
    updatedAt: getProductUpdatedAt(product),
  };
}

function getProductUpdatedAt(product = {}) {
  return product.lastSyncedAt
    || product.last_synced_at
    || product.updatedAt
    || product.updated_at
    || product.createdAt
    || product.created_at
    || '';
}

function isNaverProduct(product = {}) {
  return normalizePlatform(product.rawPlatform || product.platform) === 'naver';
}

function isSelectedStoreProduct(product = {}, selectedStore = {}, selectedStoreId = '') {
  const productStoreId = product.storeId ?? product.store_id;
  if (selectedStoreId && productStoreId !== undefined && productStoreId !== null) {
    return String(productStoreId) === String(selectedStoreId);
  }
  const productStoreName = normalizeText(product.store || product.store_name);
  const selectedStoreName = normalizeText(selectedStore?.name);
  if (productStoreName && selectedStoreName) return productStoreName === selectedStoreName;
  return true;
}

export function filterNaverProductsForStore(products = [], selectedStore = {}, selectedStoreId = '') {
  return products.filter((product) => (
    isNaverProduct(product) && isSelectedStoreProduct(product, selectedStore, selectedStoreId)
  ));
}

export function buildNaverInventorySummary(products = [], {
  selectedStore = {},
  selectedStoreId = '',
  threshold = NAVER_LOW_STOCK_THRESHOLD,
} = {}) {
  const scopedProducts = filterNaverProductsForStore(products, selectedStore, selectedStoreId);
  const attentionItems = [];
  const summary = scopedProducts.reduce((value, product) => {
    const stock = getProductStock(product);
    const status = getInventoryStatusForStock(stock, threshold);
    if (status.key !== 'normal') {
      attentionItems.push(buildInventoryItem(product, status, stock));
    }
    if (stock === null) return { ...value, invalidStock: value.invalidStock + 1 };
    if (stock === 0) return { ...value, outOfStock: value.outOfStock + 1 };
    if (stock < threshold) return { ...value, lowStock: value.lowStock + 1 };
    return { ...value, normalStock: value.normalStock + 1 };
  }, {
    total: scopedProducts.length,
    outOfStock: 0,
    lowStock: 0,
    normalStock: 0,
    invalidStock: 0,
  });
  const latestUpdatedAt = scopedProducts
    .map(getProductUpdatedAt)
    .filter(Boolean)
    .sort()
    .at(-1) || null;
  const attentionCount = summary.outOfStock + summary.lowStock + summary.invalidStock;
  const outOfStockItems = attentionItems.filter((item) => item.statusKey === 'out_of_stock');
  const lowStockItems = attentionItems.filter((item) => item.statusKey === 'low_stock');
  const invalidStockItems = attentionItems.filter((item) => item.statusKey === 'invalid');
  const primaryAttentionItem = outOfStockItems[0] || invalidStockItems[0] || lowStockItems[0] || null;
  const statusLabel = summary.total === 0
    ? '暂无本地商品'
    : attentionCount > 0
      ? '需要关注库存'
      : '库存状态稳定';
  const tone = summary.total === 0
    ? 'muted'
    : summary.outOfStock > 0 || summary.invalidStock > 0
      ? 'warning'
      : summary.lowStock > 0
        ? 'warning'
        : 'success';
  const businessMessage = summary.total === 0
    ? '当前没有可用于库存提醒的 Naver 本地商品。'
    : `已只读检查 ${summary.total} 条 Naver 本地商品：缺货 ${summary.outOfStock} 条，低库存 ${summary.lowStock} 条，库存正常 ${summary.normalStock} 条。`;
  const nextAction = attentionCount > 0
    ? `优先处理 ${primaryAttentionItem?.name || '库存异常商品'}；当前只做提醒，不会修改 Naver 平台库存。`
    : '当前库存提醒稳定；继续以本地商品库存做日常观察。';

  return {
    ...summary,
    threshold,
    thresholdRule: `0 < stock < ${threshold}`,
    latestUpdatedAt,
    attentionCount,
    attentionItems: attentionItems.slice(0, MAX_ATTENTION_ITEMS),
    outOfStockItems: outOfStockItems.slice(0, MAX_ATTENTION_ITEMS),
    lowStockItems: lowStockItems.slice(0, MAX_ATTENTION_ITEMS),
    invalidStockItems: invalidStockItems.slice(0, MAX_ATTENTION_ITEMS),
    primaryAttentionItem,
    statusLabel,
    tone,
    businessMessage,
    nextAction,
    platformWriteEnabled: false,
    platformReadPerformed: false,
    inventoryHistoryAvailable: false,
    platformComparisonAvailable: false,
    rawResponseSaved: false,
    source: 'local_products_only',
  };
}
