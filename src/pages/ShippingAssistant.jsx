import { useEffect, useMemo, useState } from 'react';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import SummaryCard from '../components/common/SummaryCard';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useStoreContext } from '../context/StoreContext';
import { shippingMockInventoryMappings, shippingMockOrders } from '../data/shippingMockData';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import {
  SHIPPING_EXPORT_MOCK_PHASE,
  buildLogisticsInventoryMappingMockGate,
  buildShippingAssistantSummary,
  buildShippingExcelExportMock,
  buildUnshippedOrderCandidates,
  createInitialLogisticsMappings,
  updateLogisticsStockQuantity,
} from '../utils/shippingAssistant';

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function moneyLabel(value, currency = 'KRW') {
  return `${Number(value || 0).toLocaleString()} ${currency || 'KRW'}`;
}

function displayText(value, fallback = '-') {
  const text = String(value ?? '').trim();
  return text || fallback;
}

function formatDateTime(value) {
  if (!value) return '-';
  try {
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Seoul',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(value));
  } catch {
    return String(value);
  }
}

function statusToneClass(tone) {
  return `status-badge ${tone || 'neutral'}`;
}

function buildDraftMapping(candidate = {}) {
  return {
    id: `shipping-draft-${candidate.id || candidate.mappingKey}`,
    storeId: candidate.storeId,
    platform: candidate.platform || 'naver',
    productName: candidate.productName,
    optionName: candidate.optionName,
    logisticsInventoryCode: '',
    logisticsProviderName: '韩国仓 A',
    currentStockQuantity: Math.max(Number(candidate.quantity || 0), 0),
    mappingVersion: 'shipping_mapping_local_draft_v1',
    isActive: true,
    isDraft: true,
    mappingKey: candidate.mappingKey,
  };
}

function ensureDraftMappings(candidates = [], mappings = [], existingDrafts = []) {
  const mappedKeys = new Set(mappings.map((item) => item.mappingKey || buildMappingKeySafe(item.productName, item.optionName)));
  const draftsByKey = new Map(existingDrafts.map((item) => [item.mappingKey, item]));
  return candidates
    .filter((candidate) => !mappedKeys.has(candidate.mappingKey))
    .map((candidate) => draftsByKey.get(candidate.mappingKey) || buildDraftMapping(candidate));
}

function buildMappingKeySafe(productName, optionName) {
  return `${String(productName || '').trim().toLocaleLowerCase('ko-KR').replace(/\s+/g, ' ')}::${String(optionName || '').trim().toLocaleLowerCase('ko-KR').replace(/\s+/g, ' ')}`;
}

function hasWritableMapping(mapping = {}) {
  return Boolean(String(mapping.productName || '').trim() && String(mapping.logisticsInventoryCode || '').trim());
}

function writableMappingPayload(mapping = {}) {
  return {
    productName: mapping.productName,
    optionName: mapping.optionName || '',
    platformProductIdHash: mapping.platformProductIdHash || null,
    platformOptionIdHash: mapping.platformOptionIdHash || null,
    internalSku: mapping.internalSku || '',
    logisticsInventoryCode: mapping.logisticsInventoryCode,
    logisticsProviderName: mapping.logisticsProviderName || '',
    currentStockQuantity: Number(mapping.currentStockQuantity || 0),
    stockStatus: mapping.stockStatus || null,
    matchPriority: Number(mapping.matchPriority || 100),
    isActive: mapping.isActive !== false,
  };
}

function LoadingPanel() {
  return (
    <div className="table-state">
      <span className="spinner" />
      正在读取本地发货候选...
    </div>
  );
}

function ShippingWorkflowSteps() {
  const steps = [
    ['1', '读取未发货订单', '只读取本地候选，不执行平台发货写入。'],
    ['2', '匹配库存编号', '第一阶段按商品名称 + 选项名称匹配。'],
    ['3', '维护物流库存', 'backend 模式可保存到本地映射和库存表。'],
    ['4', '生成导出预览', '真实 Excel 文件生成仍需单独审批。'],
  ];

  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>发货辅助流程</h2>
          <p>Naver 未发货订单是第一个真实落地功能；页面保持简单，技术门禁留在高级详情里。</p>
        </div>
      </div>
      <div className="shipping-step-grid">
        {steps.map(([index, title, description]) => (
          <article key={index} className="shipping-step">
            <span>{index}</span>
            <strong>{title}</strong>
            <p>{description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function CandidateTable({ rows = [] }) {
  if (!rows.length) {
    return (
      <EmptyState
        title="暂无未发货候选"
        description="当前店铺没有可进入发货辅助流程的本地 Naver 订单。"
      />
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>订单</th>
            <th>商品 / 选项</th>
            <th>数量</th>
            <th>订单状态</th>
            <th>物流库存编号</th>
            <th>物流库存</th>
            <th>处理状态</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.id}-${row.mappingId || 'unmatched'}`}>
              <td>
                <strong>{displayText(row.orderNo)}</strong>
                <span className="cell-subtitle">{formatDateTime(row.orderedAt)} · {moneyLabel(row.amount, row.currency)}</span>
              </td>
              <td>
                <strong>{displayText(row.productName)}</strong>
                <span className="cell-subtitle">{displayText(row.optionName, '无选项')}</span>
              </td>
              <td>{row.quantity}</td>
              <td>{row.statusLabel}</td>
              <td>{displayText(row.logisticsInventoryCode, '待维护')}</td>
              <td>{row.matchStatus === 'matched' ? `${row.currentStockQuantity} 件` : '-'}</td>
              <td><span className={statusToneClass(row.stockTone)}><i />{row.stockStatusLabel}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StockMaintenancePanel({
  mappings = [],
  draftMappings = [],
  onChangeMapping,
  onSaveMappings,
  saving = false,
  saveResult,
  saveError = '',
  backendMode = false,
}) {
  const activeMappings = [...mappings, ...draftMappings].filter((item) => item.isActive !== false);
  const writableCount = activeMappings.filter(hasWritableMapping).length;
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>物流商库存维护</h2>
          <p>{backendMode ? '保存后写入本地物流映射和库存表，不执行平台发货写入。' : 'mock 模式只维护页面状态，不写入数据库。'}</p>
        </div>
        <button className="button primary" onClick={onSaveMappings} disabled={!writableCount || saving}>
          {saving ? '保存中...' : '保存映射与库存'}
        </button>
      </div>
      {saveError ? <div className="mock-sync-error">{saveError}</div> : null}
      {saveResult?.businessMessage ? <div className="mock-sync-success">{saveResult.businessMessage}</div> : null}
      {activeMappings.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>库存编号</th>
                <th>匹配商品</th>
                <th>物流商</th>
                <th>当前库存</th>
                <th>保存状态</th>
              </tr>
            </thead>
            <tbody>
              {activeMappings.map((mapping) => (
                <tr key={mapping.id}>
                  <td>
                    <input
                      className="shipping-stock-input shipping-code-input"
                      value={mapping.logisticsInventoryCode}
                      placeholder="库存编号"
                      onChange={(event) => onChangeMapping(mapping.id, { logisticsInventoryCode: event.target.value }, mapping.isDraft)}
                    />
                  </td>
                  <td>
                    <strong>{mapping.productName}</strong>
                    <span className="cell-subtitle">{displayText(mapping.optionName, '无选项')}</span>
                  </td>
                  <td>
                    <input
                      className="shipping-stock-input shipping-provider-input"
                      value={mapping.logisticsProviderName || ''}
                      placeholder="物流商"
                      onChange={(event) => onChangeMapping(mapping.id, { logisticsProviderName: event.target.value }, mapping.isDraft)}
                    />
                  </td>
                  <td>
                    <input
                      className="shipping-stock-input"
                      type="number"
                      min="0"
                      value={mapping.currentStockQuantity}
                      onChange={(event) => onChangeMapping(mapping.id, { currentStockQuantity: event.target.value }, mapping.isDraft)}
                    />
                  </td>
                  <td>{mapping.isDraft ? '待保存' : '已保存'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="暂无库存编号映射" description="后续阶段会增加映射维护入口。" />
      )}
    </section>
  );
}

function ExportPreviewPanel({ gate, exportPreview, onGenerate }) {
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>物流商 Excel 导出预览</h2>
          <p>当前通过真实 Excel 生成 mock 门禁；真实文件、导出记录、审计记录和物流单号回传仍需单独审批。</p>
        </div>
        <button className="button primary" onClick={onGenerate} disabled={!gate.exportReadyCount}>
          生成 Excel 导出预览
        </button>
      </div>
      {!gate.exportReadyCount ? (
        <EmptyState title="还不能导出" description="请先完成库存编号匹配，并确认物流库存足够。" />
      ) : null}
      {exportPreview ? (
        <div className="shipping-export-preview">
          <div className="sync-result-grid">
            <span>文件名</span>
            <strong>{exportPreview.fileName}</strong>
            <span>文件类型</span>
            <strong>{exportPreview.fileType} / {exportPreview.fileFormat}</strong>
            <span>导出行数</span>
            <strong>{exportPreview.rowCount}</strong>
            <span>文件指纹</span>
            <strong>{exportPreview.fileHash}</strong>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>订单</th>
                  <th>商品 / 选项</th>
                  <th>数量</th>
                  <th>物流库存编号</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                {exportPreview.rows.map((row) => (
                  <tr key={`${row.orderNo}-${row.logisticsInventoryCode}`}>
                    <td>{row.orderNo}</td>
                    <td>
                      <strong>{row.productName}</strong>
                      <span className="cell-subtitle">{displayText(row.optionName, '无选项')}</span>
                    </td>
                    <td>{row.quantity}</td>
                    <td>{row.logisticsInventoryCode}</td>
                    <td>{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default function ShippingAssistant() {
  const {
    selectedStore,
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [orders, setOrders] = useState([]);
  const [mappings, setMappings] = useState([]);
  const [draftMappings, setDraftMappings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [exportPreview, setExportPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveResult, setSaveResult] = useState(null);

  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    let cancelled = false;
    setExportPreview(null);

    if (storeLoading) return () => { cancelled = true; };
    if (!selectedStoreId || !isNaverStore) {
      setOrders([]);
      setMappings([]);
      setDraftMappings([]);
      setLoadError('');
      return () => { cancelled = true; };
    }

    async function loadOrders() {
      setLoading(true);
      setLoadError('');
      setSaveError('');
      setSaveResult(null);
      try {
        const [orderResult, mappingResult] = await Promise.all([
          isBackendSource
            ? dataProvider.getOrders({
              storeId: selectedStoreId,
              platform: 'naver',
              page: 1,
              pageSize: 100,
            })
            : Promise.resolve({
              data: shippingMockOrders.filter((order) => String(order.storeId || order.store_id) === String(selectedStoreId)),
            }),
          isBackendSource
            ? dataProvider.getShippingLogisticsMappings({
              storeId: selectedStoreId,
              platform: 'naver',
            })
            : Promise.resolve({ data: [] }),
        ]);
        const nextOrders = orderResult.data || [];
        const persistedMappings = isBackendSource
          ? (mappingResult.data || [])
          : createInitialLogisticsMappings(buildUnshippedOrderCandidates(nextOrders, {
            selectedStoreId,
            platform: 'naver',
          }), shippingMockInventoryMappings);

        if (cancelled) return;
        const nextCandidates = buildUnshippedOrderCandidates(nextOrders, {
          selectedStoreId,
          platform: 'naver',
        });
        setOrders(nextOrders);
        setMappings(persistedMappings);
        setDraftMappings(ensureDraftMappings(nextCandidates, persistedMappings, []));
      } catch (error) {
        if (!cancelled) {
          setOrders([]);
          setMappings([]);
          setDraftMappings([]);
          setLoadError(error.message || '发货候选加载失败。');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadOrders();
    return () => { cancelled = true; };
  }, [isNaverStore, selectedStoreId, storeLoading]);

  const candidates = useMemo(() => buildUnshippedOrderCandidates(orders, {
    selectedStoreId,
    platform: 'naver',
  }), [orders, selectedStoreId]);

  const gate = useMemo(() => buildLogisticsInventoryMappingMockGate({
    candidates,
    mappings: [...mappings, ...draftMappings.filter(hasWritableMapping)],
    selectedStoreId,
    platform: 'naver',
  }), [candidates, mappings, draftMappings, selectedStoreId]);

  const summary = buildShippingAssistantSummary(gate);

  const changeMapping = (mappingId, patch, isDraft = false) => {
    const updater = (current) => current.map((item) => (
      String(item.id) === String(mappingId)
        ? {
          ...item,
          ...patch,
          currentStockQuantity: patch.currentStockQuantity !== undefined
            ? Math.max(0, Number(patch.currentStockQuantity || 0))
            : item.currentStockQuantity,
          lastManualUpdatedAt: new Date().toISOString(),
        }
        : item
    ));
    if (isDraft) {
      setDraftMappings(updater);
    } else if (patch.currentStockQuantity !== undefined && Object.keys(patch).length === 1) {
      setMappings((current) => updateLogisticsStockQuantity(current, mappingId, patch.currentStockQuantity));
    } else {
      setMappings(updater);
    }
    setExportPreview(null);
  };

  const saveMappings = async () => {
    const writableMappings = [...mappings, ...draftMappings].filter(hasWritableMapping).map(writableMappingPayload);
    if (!writableMappings.length) {
      setSaveError('请先填写至少一个物流库存编号。');
      setSaveResult(null);
      return;
    }
    setSaving(true);
    setSaveError('');
    setSaveResult(null);
    try {
      const payload = {
        storeId: selectedStoreId,
        platform: 'naver',
        manualApproval: true,
        actorContext: {
          role: 'admin',
          actor_id: 'shipping-local-operator',
        },
        mappings: writableMappings,
      };
      const gateResult = await dataProvider.checkShippingLogisticsMappingWriteGate(payload);
      if (!['mapping_stock_write_gate_ready', 'mock_mapping_stock_updated'].includes(gateResult.status)) {
        throw new Error(gateResult.businessMessage || gateResult.skipReason || '物流映射保存门禁未通过。');
      }
      const writeResult = await dataProvider.writeShippingLogisticsMappings(payload);
      if (!['mapping_stock_local_write_succeeded', 'mock_mapping_stock_updated'].includes(writeResult.status)) {
        throw new Error(writeResult.businessMessage || writeResult.skipReason || '物流映射保存失败。');
      }
      const nextMappings = writeResult.data?.length ? writeResult.data : writableMappings.map((item, index) => ({
        id: `shipping-local-map-${index + 1}`,
        storeId: selectedStoreId,
        platform: 'naver',
        productName: item.productName,
        optionName: item.optionName,
        logisticsInventoryCode: item.logisticsInventoryCode,
        logisticsProviderName: item.logisticsProviderName,
        currentStockQuantity: item.currentStockQuantity,
        isActive: true,
        mappingKey: buildMappingKeySafe(item.productName, item.optionName),
      }));
      setMappings(nextMappings);
      setDraftMappings(ensureDraftMappings(candidates, nextMappings, []));
      setSaveResult(writeResult);
      setExportPreview(null);
    } catch (error) {
      setSaveError(error.message || '物流映射保存失败。');
    } finally {
      setSaving(false);
    }
  };

  const generateExportPreview = () => {
    setExportPreview(buildShippingExcelExportMock({
      rows: gate.rows,
      selectedStore,
      selectedStoreId,
      includeReceiverPrivacy: false,
    }));
  };

  if (storeLoading) {
    return (
      <>
        <PageHeader title="发货辅助" description="正在读取当前店铺..." />
        <LoadingPanel />
      </>
    );
  }

  if (storeError) {
    return (
      <>
        <PageHeader title="发货辅助" description="店铺信息加载失败。" />
        <EmptyState title="店铺信息不可用" description={storeError} />
      </>
    );
  }

  if (!isNaverStore) {
    return (
      <>
        <PageHeader
          title="发货辅助"
          description="第一阶段先落地 Naver 未发货订单下载和物流库存编号匹配。"
        />
        <EmptyState
          title="请选择 Naver 店铺"
          description="Coupang 和其他平台会保留扩展位，但当前 Shipping Assistant 只开放 Naver 本地流程。"
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="发货辅助"
        description="Naver 未发货订单下载、库存编号匹配、物流库存维护和 Excel 导出预览。"
      />

      <div className="summary-grid shipping-summary-grid">
        <SummaryCard title="未发货候选" value={summary.unshippedCandidates} note="本地 Naver 订单" tone={summary.unshippedCandidates ? 'info' : 'default'} />
        <SummaryCard title="已匹配库存编号" value={summary.matchedCount} note="商品名 + 选项名" tone={summary.unmatchedCount ? 'warning' : 'success'} />
        <SummaryCard title="待维护映射" value={summary.unmatchedCount} note="需要人工补齐" tone={summary.unmatchedCount ? 'warning' : 'success'} />
        <SummaryCard title="库存需关注" value={summary.stockAttentionCount} note="物流库存不足或偏低" tone={summary.stockAttentionCount ? 'warning' : 'success'} />
        <SummaryCard title="可导出行" value={summary.exportReadyCount} note="Excel mock 门禁" tone={summary.exportReadyCount ? 'success' : 'default'} />
      </div>

      <ShippingWorkflowSteps />

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h2>未发货订单候选</h2>
            <p>{gate.businessMessage}</p>
          </div>
          <span className="period-chip">{selectedStore?.name || 'Naver 店铺'}</span>
        </div>
        {loading ? <LoadingPanel /> : null}
        {loadError ? <div className="mock-sync-error">{loadError}</div> : null}
        {!loading && !loadError ? <CandidateTable rows={gate.rows} /> : null}
        <TechnicalDetails
          title="查看发货候选技术边界"
          description="普通运营只看发货处理信息；技术字段仅用于管理员确认当前只允许本地映射和库存维护。"
          items={[
            { label: 'phase', value: gate.phase },
            { label: 'data_source_backend', value: isBackendSource },
            { label: 'selected_store_id', value: selectedStoreId },
            { label: 'platform', value: 'naver' },
            { label: 'real_api_called', value: gate.realApiCalled },
            { label: 'real_database_written', value: gate.realDatabaseWritten },
            { label: 'orders_written', value: gate.ordersWritten },
            { label: 'products_written', value: gate.productsWritten },
            { label: 'sync_log_written', value: gate.syncLogWritten },
            { label: 'tested_success_written', value: gate.testedSuccessWritten },
            { label: 'operation_audit_rows_written', value: gate.operationAuditRowsWritten },
            { label: 'formal_order_sync_open', value: gate.formalOrderSyncOpen },
            { label: 'platform_writes_enabled', value: gate.platformWritesEnabled },
            { label: 'raw_response_saved', value: gate.rawResponseSaved },
            { label: 'mapping_write_phase', value: saveResult?.phase || 'not_saved_this_session' },
            { label: 'shipping_mappings_written', value: saveResult?.shippingMappingsWritten ?? false },
            { label: 'shipping_inventory_written', value: saveResult?.shippingInventoryWritten ?? false },
            { label: 'mapping_operation_audit_rows_written', value: saveResult?.operationAuditRowsWritten ?? false },
          ]}
        />
      </section>

      <StockMaintenancePanel
        mappings={mappings}
        draftMappings={draftMappings}
        onChangeMapping={changeMapping}
        onSaveMappings={saveMappings}
        saving={saving}
        saveResult={saveResult}
        saveError={saveError}
        backendMode={isBackendSource}
      />
      <ExportPreviewPanel
        gate={gate}
        exportPreview={exportPreview}
        onGenerate={generateExportPreview}
      />

      <TechnicalDetails
        title="查看 Excel 生成 mock 门禁"
        description="当前只确认真实 Excel、导出记录、审计联动和物流单号回传的边界；不创建真实文件、不写导出记录。"
        items={[
          { label: 'phase', value: exportPreview?.phase || SHIPPING_EXPORT_MOCK_PHASE },
          { label: 'file_type', value: exportPreview?.fileType || 'shipping_request' },
          { label: 'file_format', value: exportPreview?.fileFormat || 'xlsx' },
          { label: 'file_generated', value: exportPreview?.fileGenerated ?? false },
          { label: 'file_persisted', value: exportPreview?.filePersisted ?? false },
          { label: 'export_record_written', value: exportPreview?.exportRecordWritten ?? false },
          { label: 'download_record_written', value: exportPreview?.downloadRecordWritten ?? false },
          { label: 'operation_audit_rows_written', value: exportPreview?.operationAuditRowsWritten ?? false },
          { label: 'export_record_schema_planned', value: exportPreview?.exportRecordSchemaPlanned ?? true },
          { label: 'audit_linkage_planned', value: exportPreview?.auditLinkagePlanned ?? true },
          { label: 'tracking_import_contract_planned', value: exportPreview?.trackingImportContractPlanned ?? true },
          { label: 'tracking_number_import_open', value: exportPreview?.trackingNumberImportOpen ?? false },
          { label: 'receiver_privacy_included', value: exportPreview?.includeReceiverPrivacy ?? false },
          { label: 'real_api_called', value: exportPreview?.realApiCalled ?? false },
          { label: 'real_database_written', value: exportPreview?.realDatabaseWritten ?? false },
          { label: 'formal_order_sync_open', value: exportPreview?.formalOrderSyncOpen ?? false },
          { label: 'platform_writes_enabled', value: exportPreview?.platformWritesEnabled ?? false },
        ]}
      />
    </>
  );
}
