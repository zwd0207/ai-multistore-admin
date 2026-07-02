import { parseObservedFields } from './capabilityStatusMapper';
import {
  filterNaverProductsForStore,
  normalizeStockValue,
} from './naverInventory';

const PRICE_FIELDS = new Set(['price', 'currency', 'sale_price', 'discounted_price']);
const STOCK_FIELDS = new Set(['stock', 'stock_quantity', 'available_stock', 'quantity']);

function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function numberValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeFieldName(value) {
  return String(value || '')
    .trim()
    .replace(/^["']|["']$/g, '')
    .toLowerCase();
}

function normalizeFieldList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(normalizeFieldName).filter(Boolean);
  return String(value)
    .replace(/[\[\]{}]/g, '')
    .split(/[|,]/)
    .map(normalizeFieldName)
    .filter(Boolean);
}

function latestProductReadResult(results = []) {
  return results
    .filter((item) => {
      const observed = parseObservedFields(item.responseFieldsObserved || '');
      return item.capabilityKey === 'naver.product_read'
        || observed.capability_scope === 'product_read';
    })
    .sort((a, b) => new Date(b.testedAt || b.createdAt || 0) - new Date(a.testedAt || a.createdAt || 0))[0] || null;
}

function getObservedChangedFields(result = {}) {
  const safeResult = result || {};
  const observed = parseObservedFields(safeResult.responseFieldsObserved || '');
  return normalizeFieldList(
    observed.changed_fields
    || observed['dry_run_diff.changed_fields']
    || observed.update_changed_fields
    || observed.business_changed_fields
    || safeResult.changedFields
    || safeResult.changed_fields,
  );
}

function buildLocalPriceStockCoverage(products = [], selectedStore = {}, selectedStoreId = '') {
  const scopedProducts = filterNaverProductsForStore(products, selectedStore, selectedStoreId);
  return scopedProducts.reduce((summary, product) => {
    const price = numberOrNull(product.price);
    const stock = normalizeStockValue(product.stock ?? product.stock_quantity);
    return {
      ...summary,
      priceVisibleCount: summary.priceVisibleCount + (price === null ? 0 : 1),
      missingOrInvalidPriceCount: summary.missingOrInvalidPriceCount + (price === null ? 1 : 0),
      stockVisibleCount: summary.stockVisibleCount + (stock === null ? 0 : 1),
      missingOrInvalidStockCount: summary.missingOrInvalidStockCount + (stock === null ? 1 : 0),
    };
  }, {
    total: scopedProducts.length,
    priceVisibleCount: 0,
    missingOrInvalidPriceCount: 0,
    stockVisibleCount: 0,
    missingOrInvalidStockCount: 0,
  });
}

export function buildNaverProductChangeHints(products = [], {
  selectedStore = {},
  selectedStoreId = '',
  productStatus = {},
  results = [],
} = {}) {
  const productReadResult = latestProductReadResult(results);
  const observed = parseObservedFields(productReadResult?.responseFieldsObserved || '');
  const changedFields = getObservedChangedFields(productReadResult);
  const wouldUpdate = numberValue(
    productStatus?.summary?.wouldUpdate
    ?? observed.would_update
    ?? observed['dry_run_diff.would_update'],
  );
  const wouldRefreshOnly = numberValue(
    productStatus?.summary?.wouldRefreshOnly
    ?? observed.would_refresh_only
    ?? observed['dry_run_diff.would_refresh_only'],
  );
  const coverage = buildLocalPriceStockCoverage(products, selectedStore, selectedStoreId);
  const priceChangeObserved = changedFields.some((field) => PRICE_FIELDS.has(field));
  const stockChangeObserved = changedFields.some((field) => STOCK_FIELDS.has(field));
  const businessChangeObserved = wouldUpdate > 0 || changedFields.length > 0;
  const changedFieldLabels = [
    priceChangeObserved ? '价格' : null,
    stockChangeObserved ? '库存' : null,
  ].filter(Boolean);

  const statusLabel = priceChangeObserved || stockChangeObserved
    ? '价格 / 库存待核对'
    : businessChangeObserved
      ? '商品变化待核对'
      : '暂无价格 / 库存变化';
  const tone = businessChangeObserved ? 'warning' : 'success';
  const businessMessage = priceChangeObserved || stockChangeObserved
    ? `最近一次商品 dry-run 暴露${changedFieldLabels.join(' / ')}字段变化，需要人工核对后再决定是否写库。`
    : businessChangeObserved
      ? '最近一次商品 dry-run 提示存在业务字段变化，但没有明确落在价格或库存字段，需先人工核对。'
      : `最近一次 Naver 商品 dry-run 未发现价格或库存业务字段变化；当前本地 ${coverage.total} 条商品可用于价格和库存日常查看。`;
  const nextAction = businessChangeObserved
    ? '先核对变更字段和商品列表；未单独批准前不写库、不开放正式商品批量同步。'
    : '继续只读观察；后续 dry-run 如出现 price 或 stock_quantity 变化，再进入人工核对。';

  return {
    ...coverage,
    statusLabel,
    tone,
    businessMessage,
    nextAction,
    wouldUpdate,
    wouldRefreshOnly,
    changedFields,
    priceChangeObserved,
    stockChangeObserved,
    businessChangeObserved,
    source: 'post_sync_dry_run_summary_and_local_products',
    platformReadPerformedThisPhase: false,
    platformWriteEnabled: false,
    formalBatchSyncOpen: false,
    rawResponseSaved: false,
  };
}
