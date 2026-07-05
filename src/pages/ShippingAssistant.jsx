import { useEffect, useMemo, useState } from 'react';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import SummaryCard from '../components/common/SummaryCard';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useStoreContext } from '../context/StoreContext';
import { shippingMockInventoryMappings, shippingMockOrders } from '../data/shippingMockData';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import {
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
    ['3', '维护物流库存', '当前为页面内 mock，后续再落库。'],
    ['4', '生成导出预览', '先生成 Excel 合同预览，不产生真实文件。'],
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

function StockMaintenancePanel({ mappings = [], onChangeStock }) {
  const activeMappings = mappings.filter((item) => item.isActive !== false);
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>物流商库存维护</h2>
          <p>当前是本地页面内 mock，用来验证运营流程；不会写入数据库。</p>
        </div>
      </div>
      {activeMappings.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>库存编号</th>
                <th>匹配商品</th>
                <th>物流商</th>
                <th>当前库存</th>
              </tr>
            </thead>
            <tbody>
              {activeMappings.map((mapping) => (
                <tr key={mapping.id}>
                  <td><strong>{mapping.logisticsInventoryCode}</strong></td>
                  <td>
                    <strong>{mapping.productName}</strong>
                    <span className="cell-subtitle">{displayText(mapping.optionName, '无选项')}</span>
                  </td>
                  <td>{mapping.logisticsProviderName}</td>
                  <td>
                    <input
                      className="shipping-stock-input"
                      type="number"
                      min="0"
                      value={mapping.currentStockQuantity}
                      onChange={(event) => onChangeStock(mapping.id, event.target.value)}
                    />
                  </td>
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
          <p>当前只生成导出合同预览，不创建真实文件、不写导出记录。</p>
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
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [exportPreview, setExportPreview] = useState(null);

  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    let cancelled = false;
    setExportPreview(null);

    if (storeLoading) return () => { cancelled = true; };
    if (!selectedStoreId || !isNaverStore) {
      setOrders([]);
      setMappings([]);
      setLoadError('');
      return () => { cancelled = true; };
    }

    async function loadOrders() {
      setLoading(true);
      setLoadError('');
      try {
        const nextOrders = isBackendSource
          ? (await dataProvider.getOrders({
            storeId: selectedStoreId,
            platform: 'naver',
            page: 1,
            pageSize: 100,
          })).data || []
          : shippingMockOrders.filter((order) => String(order.storeId || order.store_id) === String(selectedStoreId));

        if (cancelled) return;
        const nextCandidates = buildUnshippedOrderCandidates(nextOrders, {
          selectedStoreId,
          platform: 'naver',
        });
        setOrders(nextOrders);
        setMappings(createInitialLogisticsMappings(nextCandidates, shippingMockInventoryMappings));
      } catch (error) {
        if (!cancelled) {
          setOrders([]);
          setMappings([]);
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
    mappings,
    selectedStoreId,
    platform: 'naver',
  }), [candidates, mappings, selectedStoreId]);

  const summary = buildShippingAssistantSummary(gate);

  const changeStock = (mappingId, nextQuantity) => {
    setMappings((current) => updateLogisticsStockQuantity(current, mappingId, nextQuantity));
    setExportPreview(null);
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
        <SummaryCard title="可导出行" value={summary.exportReadyCount} note="Excel mock 预览" tone={summary.exportReadyCount ? 'success' : 'default'} />
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
          description="普通运营只看发货处理信息；技术字段仅用于管理员确认当前仍是本地 mock gate。"
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
          ]}
        />
      </section>

      <StockMaintenancePanel mappings={mappings} onChangeStock={changeStock} />

      <ExportPreviewPanel
        gate={gate}
        exportPreview={exportPreview}
        onGenerate={generateExportPreview}
      />

      <TechnicalDetails
        title="查看 Excel mock 导出边界"
        description="本阶段只验证导出字段合同，不创建真实文件、不写导出记录、不写审计记录。"
        items={[
          { label: 'phase', value: exportPreview?.phase || 'Shipping-1J' },
          { label: 'file_type', value: exportPreview?.fileType || 'shipping_request' },
          { label: 'file_format', value: exportPreview?.fileFormat || 'xlsx' },
          { label: 'file_generated', value: exportPreview?.fileGenerated ?? false },
          { label: 'file_persisted', value: exportPreview?.filePersisted ?? false },
          { label: 'export_record_written', value: exportPreview?.exportRecordWritten ?? false },
          { label: 'operation_audit_rows_written', value: exportPreview?.operationAuditRowsWritten ?? false },
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

