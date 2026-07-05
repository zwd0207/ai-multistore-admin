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
  SHIPPING_SHIPMENT_WRITEBACK_BOUNDARY_PHASE,
  SHIPPING_TRACKING_IMPORT_XLSX_PARSER_PHASE,
  SHIPPING_TRACKING_IMPORT_MOCK_PHASE,
  SHIPPING_TRACKING_IMPORT_RECORD_PHASE,
  SHIPPING_TRACKING_ORDER_MATCH_PHASE,
  SHIPPING_ORDER_STATUS_LOCAL_UPDATE_PHASE,
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

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',').pop() : result);
    };
    reader.onerror = () => reject(new Error('File read failed.'));
    reader.readAsDataURL(file);
  });
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

function ExportPreviewPanel({ gate, exportPreview, onGenerate, generating = false, exportError = '', backendMode = false }) {
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>物流商 Excel 导出预览</h2>
          <p>{backendMode ? '可生成本地 Excel 文件，并写入导出记录和审计证据；不会回传 Naver。' : 'mock 模式只生成页面预览；真实文件、导出记录和审计记录不会写入。'}</p>
        </div>
        <button className="button primary" onClick={onGenerate} disabled={!gate.exportReadyCount || generating}>
          {generating ? '生成中...' : backendMode ? '生成本地 Excel 文件' : '生成 Excel 导出预览'}
        </button>
      </div>
      {exportError ? <div className="mock-sync-error">{exportError}</div> : null}
      {!gate.exportReadyCount ? (
        <EmptyState title="还不能导出" description="请先完成库存编号匹配，并确认物流库存足够。" />
      ) : null}
      {exportPreview ? (
        <div className="shipping-export-preview">
          {exportPreview.businessMessage ? <div className="mock-sync-success">{exportPreview.businessMessage}</div> : null}
          <div className="sync-result-grid">
            <span>文件名</span>
            <strong>{exportPreview.fileName}</strong>
            <span>文件类型</span>
            <strong>{exportPreview.fileType} / {exportPreview.fileFormat}</strong>
            <span>导出行数</span>
            <strong>{exportPreview.rowCount}</strong>
            <span>文件指纹</span>
            <strong>{exportPreview.fileHash}</strong>
            {exportPreview.filePath ? (
              <>
                <span>本地路径</span>
                <strong>{exportPreview.filePath}</strong>
              </>
            ) : null}
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

function ExportHistoryPanel({
  history = [],
  loading = false,
  error = '',
  businessMessage = '',
}) {
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>发货导出历史</h2>
          <p>{businessMessage || '只读查看本地发货 Excel 导出记录，方便运营确认最近生成过哪些文件。'}</p>
        </div>
      </div>
      {loading ? <LoadingPanel /> : null}
      {error ? <div className="mock-sync-error">{error}</div> : null}
      {!loading && !error && !history.length ? (
        <EmptyState
          title="暂无导出记录"
          description="生成本地 Excel 后，这里会显示文件名、导出时间、行数和审计关联。"
        />
      ) : null}
      {!loading && !error && history.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>导出时间</th>
                <th>文件</th>
                <th>行数</th>
                <th>状态</th>
                <th>审计关联</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.id || item.fileSha256 || item.fileName}>
                  <td>{formatDateTime(item.createdAt)}</td>
                  <td>
                    <strong>{displayText(item.fileName)}</strong>
                    <span className="cell-subtitle">{displayText(item.fileType)} / {displayText(item.fileFormat)}</span>
                  </td>
                  <td>{item.rowCount}</td>
                  <td><span className={statusToneClass(item.fileGenerated ? 'success' : 'neutral')}><i />{item.fileGenerated ? '已生成' : '演示记录'}</span></td>
                  <td>{displayText(item.auditCorrelationId, '未关联')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <TechnicalDetails
        title="查看导出历史技术详情"
        description="普通运营只看文件和行数；本地路径、文件哈希、只读边界放在这里。"
        items={[
          { label: 'phase', value: 'Shipping-4D' },
          { label: 'history_count', value: history.length },
          { label: 'tracking_import_phase', value: SHIPPING_TRACKING_IMPORT_MOCK_PHASE },
          { label: 'tracking_number_import_open', value: false },
          { label: 'shipment_writeback_open', value: false },
          { label: 'real_api_called', value: false },
          { label: 'orders_written', value: false },
          { label: 'products_written', value: false },
          { label: 'sync_log_written', value: false },
        ]}
      >
        {history.map((item) => (
          <pre key={`history-${item.id || item.fileName}`}>{JSON.stringify({
            id: item.id,
            file_path: item.filePath,
            file_sha256: item.fileSha256,
            file_generated: item.fileGenerated,
            file_persisted: item.filePersisted,
            raw_response_saved: item.rawResponseSaved,
            secrets_saved: item.secretsSaved,
            privacy_fields_redacted: item.privacyFieldsRedacted,
            mapping_version: item.mappingVersion,
          }, null, 2)}</pre>
        ))}
      </TechnicalDetails>
    </section>
  );
}

function TrackingImportHistoryPanel({
  history = [],
  loading = false,
  error = '',
  businessMessage = '',
}) {
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>物流单号导入记录</h2>
          <p>{businessMessage || '只读查看本地物流单号导入批次；当前不会更新订单，也不会回填 Naver 发货。'}</p>
        </div>
      </div>
      {loading ? <LoadingPanel /> : null}
      {error ? <div className="mock-sync-error">{error}</div> : null}
      {!loading && !error && !history.length ? (
        <EmptyState
          title="暂无物流单号导入记录"
          description="后续导入物流商回传表后，这里会显示导入时间、行数、重复行和审计关联。"
        />
      ) : null}
      {!loading && !error && history.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>导入时间</th>
                <th>来源文件</th>
                <th>行数</th>
                <th>状态</th>
                <th>回填</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.id || item.auditCorrelationId || item.sourceFileName}>
                  <td>{formatDateTime(item.createdAt)}</td>
                  <td>
                    <strong>{displayText(item.sourceFileName, '本地导入记录')}</strong>
                    <span className="cell-subtitle">{displayText(item.fileType)} / {displayText(item.fileFormat)}</span>
                  </td>
                  <td>
                    <strong>{item.rowCount}</strong>
                    <span className="cell-subtitle">可处理 {item.readyRowCount} / 重复 {item.duplicateRowCount}</span>
                  </td>
                  <td><span className={statusToneClass(item.importStatus === 'recorded' ? 'success' : 'neutral')}><i />{displayText(item.importStatus, 'recorded')}</span></td>
                  <td><span className={statusToneClass(item.shipmentWritebackCalled ? 'warning' : 'neutral')}><i />{item.shipmentWritebackCalled ? '已回填' : '未回填'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <TechnicalDetails
        title="查看物流单号导入技术边界"
        description="普通运营只看导入记录；平台回填、订单更新、原始响应和敏感信息边界放在这里核对。"
        items={[
          { label: 'phase', value: SHIPPING_TRACKING_IMPORT_RECORD_PHASE },
          { label: 'history_count', value: history.length },
          { label: 'tracking_number_import_open', value: false },
          { label: 'shipment_writeback_open', value: false },
          { label: 'shipment_writeback_called', value: false },
          { label: 'orders_updated', value: false },
          { label: 'real_api_called', value: false },
          { label: 'orders_written', value: false },
          { label: 'products_written', value: false },
          { label: 'sync_log_written', value: false },
        ]}
      >
        {history.map((item) => (
          <pre key={`tracking-history-${item.id || item.auditCorrelationId}`}>{JSON.stringify({
            id: item.id,
            source_file_name: item.sourceFileName,
            audit_correlation_id: item.auditCorrelationId,
            import_status: item.importStatus,
            parser_contract_acknowledged: item.parserContractAcknowledged,
            tracking_number_import_open: item.trackingNumberImportOpen,
            shipment_writeback_called: item.shipmentWritebackCalled,
            orders_updated: item.ordersUpdated,
            raw_response_saved: item.rawResponseSaved,
            secrets_saved: item.secretsSaved,
            privacy_fields_redacted: item.privacyFieldsRedacted,
            mapping_version: item.mappingVersion,
          }, null, 2)}</pre>
        ))}
      </TechnicalDetails>
    </section>
  );
}

function TrackingImportParserUploadPanel({
  fileName = '',
  fileSize = 0,
  preview,
  importResult,
  loading = false,
  saving = false,
  error = '',
  saveError = '',
  onFileChange,
  onParse,
  onSaveImport,
}) {
  const rows = preview?.rows || [];
  const canSave = preview?.status === 'tracking_xlsx_parser_mock_ready' && rows.length > 0 && !loading && !saving;
  const saved = ['tracking_import_local_write_succeeded', 'mock_tracking_import_local_record_ready'].includes(importResult?.status);
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>物流单号表导入</h2>
          <p>{importResult?.businessMessage || preview?.businessMessage || '先预览物流商回传 xlsx，确认后保存为本地导入记录；不会回填 Naver。'}</p>
        </div>
        <span className={statusToneClass(saved || preview?.status === 'tracking_xlsx_parser_mock_ready' ? 'success' : 'neutral')}><i />{saved ? '已保存记录' : preview?.status === 'tracking_xlsx_parser_mock_ready' ? '预览通过' : '等待上传'}</span>
      </div>
      <div className="upload-shell">
        <input
          type="file"
          accept=".xlsx"
          onChange={onFileChange}
          disabled={loading || saving}
        />
        <div>
          <strong>{fileName || 'No xlsx selected'}</strong>
          <span className="cell-subtitle">
            {fileSize ? `${fileSize.toLocaleString()} bytes selected` : 'Expected columns: order reference, product order reference, carrier, tracking number.'}
          </span>
        </div>
        <button
          type="button"
          className="button primary"
          onClick={onParse}
          disabled={loading || saving || !fileName}
        >
          {loading ? '解析中...' : '预览 xlsx'}
        </button>
        <button
          type="button"
          className="button ghost"
          onClick={onSaveImport}
          disabled={!canSave}
        >
          {saving ? '保存中...' : '保存本地导入记录'}
        </button>
      </div>
      {error ? <div className="mock-sync-error">{error}</div> : null}
      {saveError ? <div className="mock-sync-error">{saveError}</div> : null}
      {preview?.status === 'tracking_xlsx_parser_mock_ready' ? (
        <div className="mock-sync-success">预览通过。确认行内容后，可保存为本地物流单号导入记录。</div>
      ) : null}
      {saved ? (
        <div className="mock-sync-success">本地导入记录已生成；下一步可匹配订单并更新本地订单状态。</div>
      ) : null}
      {rows.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Tracking</th>
                <th>Carrier</th>
                <th>Row status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.rowIndex}-${row.orderNo}-${row.trackingNumber}`}>
                  <td>
                    <strong>{displayText(row.orderNo)}</strong>
                    <span className="cell-subtitle">{displayText(row.productOrderNo)}</span>
                  </td>
                  <td>
                    <strong>{displayText(row.trackingNumber)}</strong>
                    <span className="cell-subtitle">{formatDateTime(row.shippedAt)}</span>
                  </td>
                  <td>{displayText(row.carrier)}</td>
                  <td><span className={statusToneClass(row.rowStatus === 'ready_for_future_review' ? 'success' : 'warning')}><i />{displayText(row.rowStatus)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <TechnicalDetails
        title="Tracking xlsx parser boundary"
        description="Parser preview keeps file content out of storage and does not update orders or call Naver."
        items={[
          { label: 'phase', value: preview?.phase || SHIPPING_TRACKING_IMPORT_XLSX_PARSER_PHASE },
          { label: 'status', value: preview?.status || 'not_checked' },
          { label: 'source_file_name', value: preview?.sourceFileName || fileName || 'not_selected' },
          { label: 'parser_version', value: preview?.parserVersion || 'shipping_tracking_import_xlsx_parser_v1' },
          { label: 'file_received', value: preview?.fileReceived ?? false },
          { label: 'file_size_bytes', value: preview?.fileSizeBytes || fileSize || 0 },
          { label: 'row_count', value: preview?.rowCount ?? 0 },
          { label: 'ready_row_count', value: preview?.readyRowCount ?? 0 },
          { label: 'duplicate_row_count', value: preview?.duplicateRowCount ?? 0 },
          { label: 'import_batch_id', value: importResult?.importBatchId || 'not_created' },
          { label: 'operation_audit_log_id', value: importResult?.operationAuditLogId || 'not_created' },
          { label: 'file_content_saved', value: preview?.fileContentSaved ?? false },
          { label: 'parsed_rows_written', value: preview?.parsedRowsWritten ?? false },
          { label: 'import_record_written', value: importResult?.importRecordWritten ?? preview?.importRecordWritten ?? false },
          { label: 'tracking_number_import_open', value: preview?.trackingNumberImportOpen ?? false },
          { label: 'shipment_writeback_called', value: importResult?.shipmentWritebackCalled ?? preview?.shipmentWritebackCalled ?? false },
          { label: 'orders_updated', value: importResult?.ordersUpdated ?? preview?.ordersUpdated ?? false },
          { label: 'real_api_called', value: importResult?.realApiCalled ?? preview?.realApiCalled ?? false },
          { label: 'real_database_written', value: importResult?.realDatabaseWritten ?? preview?.realDatabaseWritten ?? false },
          { label: 'raw_response_saved', value: importResult?.rawResponseSaved ?? preview?.rawResponseSaved ?? false },
          { label: 'privacy_fields_redacted', value: importResult?.privacyFieldsRedacted ?? preview?.privacyFieldsRedacted ?? true },
          { label: 'next_action', value: importResult ? 'match_orders_then_local_status_update' : preview?.nextAction || 'not_ready' },
        ]}
      >
        {preview ? (
          <pre>{JSON.stringify({
            mapped_columns: preview.mappedColumns,
            unknown_columns: preview.unknownColumns,
            integration_plan_ready: preview.integrationPlanReady,
            tracking_number_import_open: preview.trackingNumberImportOpen,
            shipment_writeback_called: preview.shipmentWritebackCalled,
            orders_updated: preview.ordersUpdated,
            file_content_saved: preview.fileContentSaved,
            parsed_rows_written: preview.parsedRowsWritten,
            raw_response_saved: preview.rawResponseSaved,
            import_batch_id: importResult?.importBatchId,
            operation_audit_log_id: importResult?.operationAuditLogId,
          }, null, 2)}</pre>
        ) : null}
      </TechnicalDetails>
    </section>
  );
}

function TrackingOrderMatchEvidencePanel({
  evidence,
  loading = false,
  error = '',
}) {
  const rows = evidence?.rows || [];
  const statusLabel = evidence?.status === 'tracking_order_match_empty'
    ? '暂无可匹配单号'
    : evidence?.matchedOrderCount
      ? '已有匹配证据'
      : '待匹配';
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>单号匹配订单证据</h2>
          <p>{evidence?.businessMessage || '只读检查物流单号导入记录是否能匹配本地订单；当前不会更新订单状态。'}</p>
        </div>
        <span className={statusToneClass(evidence?.matchedOrderCount ? 'success' : 'neutral')}><i />{statusLabel}</span>
      </div>
      {loading ? <LoadingPanel /> : null}
      {error ? <div className="mock-sync-error">{error}</div> : null}
      {!loading && !error && !rows.length ? (
        <EmptyState
          title="暂无匹配证据"
          description="导入物流商回传表后，系统会先只读匹配本地订单，再进入人工审核。"
        />
      ) : null}
      {!loading && !error && rows.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>订单</th>
                <th>物流单号</th>
                <th>本地匹配</th>
                <th>后续写入</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.rowIndex}-${row.orderNo}-${row.trackingNumber}`}>
                  <td>
                    <strong>{displayText(row.orderNo)}</strong>
                    <span className="cell-subtitle">{displayText(row.orderSummary?.product_name || row.orderSummary?.productName || row.productOrderNo)}</span>
                  </td>
                  <td>
                    <strong>{displayText(row.trackingNumber)}</strong>
                    <span className="cell-subtitle">{displayText(row.carrier)} / {formatDateTime(row.shippedAt)}</span>
                  </td>
                  <td><span className={statusToneClass(row.matchStatus === 'matched_existing_order' ? 'success' : 'warning')}><i />{row.matchStatus === 'matched_existing_order' ? '已匹配' : '未匹配'}</span></td>
                  <td>{row.futureWriteAllowed ? '允许后续审核' : '只读证据'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <TechnicalDetails
        title="查看单号匹配技术边界"
        description="匹配证据只读生成，不更新订单，不调用 Naver。"
        items={[
          { label: 'phase', value: evidence?.phase || SHIPPING_TRACKING_ORDER_MATCH_PHASE },
          { label: 'status', value: evidence?.status || 'not_checked' },
          { label: 'total_tracking_rows', value: evidence?.totalTrackingRows ?? 0 },
          { label: 'matched_order_count', value: evidence?.matchedOrderCount ?? 0 },
          { label: 'unmatched_order_count', value: evidence?.unmatchedOrderCount ?? 0 },
          { label: 'duplicate_tracking_row_count', value: evidence?.duplicateTrackingRowCount ?? 0 },
          { label: 'shipment_writeback_called', value: evidence?.shipmentWritebackCalled ?? false },
          { label: 'orders_updated', value: evidence?.ordersUpdated ?? false },
          { label: 'real_api_called', value: evidence?.realApiCalled ?? false },
          { label: 'real_database_written', value: evidence?.realDatabaseWritten ?? false },
        ]}
      />
    </section>
  );
}

function TrackingOrderStatusLocalUpdatePanel({
  evidence,
  gate,
  result,
  approvals = {},
  onToggleApproval,
  onCheckGate,
  onWrite,
  loading = false,
  error = '',
  latestImportBatchId = null,
  backendMode = false,
}) {
  const matchedCount = Number(evidence?.matchedOrderCount || 0);
  const gateReady = gate?.status === 'tracking_order_status_update_gate_ready';
  const noopReady = gate?.status === 'tracking_order_status_update_noop_ready' || result?.status === 'tracking_order_status_update_noop';
  const mockReady = result?.status === 'mock_tracking_order_status_update_ready';
  const updateSucceeded = result?.status === 'tracking_order_status_update_succeeded';
  const canCheck = Boolean(latestImportBatchId && matchedCount);
  const canWrite = gateReady && !loading;
  const approvalRows = [
    ['manualApproval', '人工批准'],
    ['backupEvidenceAcknowledged', '备份证据'],
    ['auditEvidenceAcknowledged', '审计证据'],
    ['operatorChecklistAcknowledged', '操作清单'],
  ];
  const statusText = updateSucceeded
    ? '本地状态已更新'
    : mockReady
      ? 'mock 流程通过'
      : noopReady
      ? '无需重复更新'
      : gateReady
        ? '可以本地更新'
        : matchedCount
          ? '等待审批'
          : '等待匹配';

  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>本地订单状态更新</h2>
          <p>{result?.businessMessage || gate?.businessMessage || '物流单号已匹配后，可在本地把订单标记为已发货 / 配送中；不会回填 Naver。'}</p>
        </div>
        <span className={statusToneClass(updateSucceeded || mockReady || gateReady || noopReady ? 'success' : 'neutral')}><i />{statusText}</span>
      </div>

      <div className="summary-grid shipping-summary-grid">
        <SummaryCard title="匹配订单" value={matchedCount} note="来自物流单号匹配" tone={matchedCount ? 'success' : 'default'} />
        <SummaryCard title="可更新" value={gate?.updateCandidateCount ?? 0} note="本地订单状态" tone={gate?.updateCandidateCount ? 'success' : 'default'} />
        <SummaryCard title="已是发货中" value={gate?.alreadyUpdatedCount ?? result?.alreadyUpdatedCount ?? 0} note="重复执行不写入" tone="default" />
        <SummaryCard title="已更新" value={result?.updatedOrderCount ?? 0} note={backendMode ? '本地数据库' : 'mock 演示'} tone={updateSucceeded ? 'success' : 'default'} />
        <SummaryCard title="Naver 回填" value={result?.shipmentWritebackCalled ? '已调用' : '未调用'} note="本阶段保持关闭" tone="default" />
      </div>

      <div className="shipping-approval-grid">
        {approvalRows.map(([key, label]) => (
          <label className="shipping-approval-item" key={key}>
            <input
              type="checkbox"
              checked={Boolean(approvals[key])}
              onChange={(event) => onToggleApproval?.(key, event.target.checked)}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>

      {error ? <div className="mock-sync-error">{error}</div> : null}
      {gate?.skipReason && gate.status === 'blocked' ? (
        <div className="mock-sync-error">门禁未通过：{gate.skipReason}</div>
      ) : null}
      {updateSucceeded ? (
        <div className="mock-sync-success">订单状态更新证据已生成；正式批量同步和 Naver 回填仍未开放。</div>
      ) : null}
      {mockReady ? (
        <div className="mock-sync-success">mock 模式已走通审批流程；没有写入数据库。</div>
      ) : null}
      {noopReady ? (
        <div className="mock-sync-success">匹配订单已经处于已发货 / 配送中，本次没有重复写入。</div>
      ) : null}

      <div className="table-toolbar">
        <button className="button ghost" type="button" onClick={onCheckGate} disabled={!canCheck || loading}>
          {loading ? '检查中...' : '检查更新门禁'}
        </button>
        <button className="button primary" type="button" onClick={onWrite} disabled={!canWrite}>
          {loading ? '处理中...' : '更新本地订单状态'}
        </button>
      </div>

      <TechnicalDetails
        title="查看本地状态更新边界"
        description="Shipping-8 只更新本地订单状态、状态时间线和审计证据，不调用平台发货接口。"
        items={[
          { label: 'phase', value: result?.phase || gate?.phase || SHIPPING_ORDER_STATUS_LOCAL_UPDATE_PHASE },
          { label: 'status', value: result?.status || gate?.status || 'not_checked' },
          { label: 'import_batch_id', value: latestImportBatchId || 'not_available' },
          { label: 'target_order_status', value: result?.targetOrderStatus || gate?.targetOrderStatus || 'DISPATCHED' },
          { label: 'target_order_status_label_zh', value: result?.targetOrderStatusLabelZh || gate?.targetOrderStatusLabelZh || '已发货 / 配送中' },
          { label: 'matched_order_count', value: matchedCount },
          { label: 'update_candidate_count', value: gate?.updateCandidateCount ?? 0 },
          { label: 'updated_order_count', value: result?.updatedOrderCount ?? 0 },
          { label: 'order_status_events_written', value: result?.orderStatusEventsWritten ?? false },
          { label: 'tracking_import_batch_updated', value: result?.trackingImportBatchUpdated ?? false },
          { label: 'operation_audit_rows_written', value: result?.operationAuditRowsWritten ?? false },
          { label: 'orders_updated', value: result?.ordersUpdated ?? false },
          { label: 'orders_written', value: result?.ordersWritten ?? false },
          { label: 'products_written', value: result?.productsWritten ?? false },
          { label: 'sync_log_written', value: result?.syncLogWritten ?? false },
          { label: 'tested_success_written', value: result?.capabilityTestedSuccessWritten ?? false },
          { label: 'real_api_called', value: result?.realApiCalled ?? false },
          { label: 'real_database_written', value: result?.realDatabaseWritten ?? false },
          { label: 'formal_order_sync_open', value: result?.formalOrderSyncOpen ?? false },
          { label: 'platform_writes_enabled', value: result?.platformWritesEnabled ?? false },
          { label: 'shipment_writeback_called', value: result?.shipmentWritebackCalled ?? false },
          { label: 'raw_response_saved', value: result?.rawResponseSaved ?? false },
          { label: 'privacy_fields_redacted', value: result?.privacyFieldsRedacted ?? true },
        ]}
      />
    </section>
  );
}

function ShipmentWritebackBoundaryPanel({ boundary }) {
  const missing = boundary?.missingActions || [];
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>Naver 发货回填边界</h2>
          <p>{boundary?.businessMessage || '当前仅展示未来回填前必须满足的审批、备份、审计和人工清单，不会调用 Naver。'}</p>
        </div>
        <span className={statusToneClass(boundary?.shipmentWritebackOpen ? 'warning' : 'neutral')}><i />{boundary?.shipmentWritebackOpen ? '已开放' : '未开放'}</span>
      </div>
      <div className="summary-grid shipping-summary-grid">
        <SummaryCard title="匹配订单" value={boundary?.matchedOrderCount ?? 0} note="只读证据" tone={boundary?.matchedOrderCount ? 'success' : 'default'} />
        <SummaryCard title="待补门禁" value={missing.length} note="回填前检查项" tone={missing.length ? 'warning' : 'success'} />
        <SummaryCard title="Naver 回填" value={boundary?.shipmentWritebackCalled ? '已调用' : '未调用'} note="本阶段保持关闭" tone="default" />
      </div>
      {missing.length ? (
        <div className="mock-sync-error">仍缺少：{missing.join(', ')}</div>
      ) : (
        <div className="mock-sync-success">边界材料可供后续阶段审核；当前仍不执行平台写入。</div>
      )}
      <TechnicalDetails
        title="查看回填边界技术状态"
        description="这里确认平台写入仍关闭；真正回填必须单独阶段批准。"
        items={[
          { label: 'phase', value: boundary?.phase || SHIPPING_SHIPMENT_WRITEBACK_BOUNDARY_PHASE },
          { label: 'status', value: boundary?.status || 'not_checked' },
          { label: 'manual_approval', value: boundary?.manualApproval ?? false },
          { label: 'shipment_writeback_open', value: boundary?.shipmentWritebackOpen ?? false },
          { label: 'shipment_writeback_called', value: boundary?.shipmentWritebackCalled ?? false },
          { label: 'orders_updated', value: boundary?.ordersUpdated ?? false },
          { label: 'platform_writes_enabled', value: boundary?.platformWritesEnabled ?? false },
          { label: 'real_api_called', value: boundary?.realApiCalled ?? false },
          { label: 'real_database_written', value: boundary?.realDatabaseWritten ?? false },
        ]}
      />
    </section>
  );
}

function ShippingOperatorRunbookPanel() {
  const steps = [
    ['1', '下载未发货订单', '确认订单仍处于待发货状态。'],
    ['2', '维护库存编号', '商品名和选项名必须能匹配物流商库存编号。'],
    ['3', '导出 Excel', '把本地生成的发货请求表发给物流商。'],
    ['4', '导入物流单号', '先保存本地导入记录，不更新订单。'],
    ['5', '只读匹配订单', '确认单号和本地订单一一对应。'],
    ['6', '人工审核回填', '备份、审计、权限和清单齐全后，后续阶段再考虑 Naver 回填。'],
  ];
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>发货操作清单</h2>
          <p>给普通运营使用的最小流程；管理员仍可在高级详情里核对技术边界。</p>
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
      <TechnicalDetails
        title="查看操作清单边界"
        description="Shipping-6E 只展示清单，不创建任务、不回填平台。"
        items={[
          { label: 'phase', value: 'Shipping-6E' },
          { label: 'runbook_ui_only', value: true },
          { label: 'shipment_writeback_called', value: false },
          { label: 'orders_updated', value: false },
          { label: 'real_api_called', value: false },
        ]}
      />
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
  const [exportError, setExportError] = useState('');
  const [generatingExport, setGeneratingExport] = useState(false);
  const [exportHistory, setExportHistory] = useState([]);
  const [historyMessage, setHistoryMessage] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const [trackingImportHistory, setTrackingImportHistory] = useState([]);
  const [trackingImportHistoryMessage, setTrackingImportHistoryMessage] = useState('');
  const [trackingImportHistoryError, setTrackingImportHistoryError] = useState('');
  const [trackingImportHistoryLoading, setTrackingImportHistoryLoading] = useState(false);
  const [trackingParserFile, setTrackingParserFile] = useState(null);
  const [trackingParserContentBase64, setTrackingParserContentBase64] = useState('');
  const [trackingParserPreview, setTrackingParserPreview] = useState(null);
  const [trackingParserError, setTrackingParserError] = useState('');
  const [trackingParserLoading, setTrackingParserLoading] = useState(false);
  const [trackingImportSaveResult, setTrackingImportSaveResult] = useState(null);
  const [trackingImportSaveError, setTrackingImportSaveError] = useState('');
  const [trackingImportSaving, setTrackingImportSaving] = useState(false);
  const [trackingMatchEvidence, setTrackingMatchEvidence] = useState(null);
  const [trackingMatchError, setTrackingMatchError] = useState('');
  const [trackingMatchLoading, setTrackingMatchLoading] = useState(false);
  const [latestTrackingImportBatchId, setLatestTrackingImportBatchId] = useState(null);
  const [statusUpdateGate, setStatusUpdateGate] = useState(null);
  const [statusUpdateResult, setStatusUpdateResult] = useState(null);
  const [statusUpdateError, setStatusUpdateError] = useState('');
  const [statusUpdateLoading, setStatusUpdateLoading] = useState(false);
  const [statusUpdateApprovals, setStatusUpdateApprovals] = useState({
    manualApproval: false,
    backupEvidenceAcknowledged: false,
    auditEvidenceAcknowledged: false,
    operatorChecklistAcknowledged: false,
  });
  const [shipmentBoundary, setShipmentBoundary] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveResult, setSaveResult] = useState(null);

  const isNaverStore = normalizePlatform(selectedStore?.platform || selectedStore?.rawPlatform) === 'naver';

  useEffect(() => {
    let cancelled = false;
    setExportPreview(null);
    setExportError('');

    if (storeLoading) return () => { cancelled = true; };
    if (!selectedStoreId || !isNaverStore) {
      setOrders([]);
      setMappings([]);
      setDraftMappings([]);
      setExportHistory([]);
      setHistoryMessage('');
      setHistoryError('');
      setTrackingImportHistory([]);
      setTrackingImportHistoryMessage('');
      setTrackingImportHistoryError('');
      setTrackingParserFile(null);
      setTrackingParserContentBase64('');
      setTrackingParserPreview(null);
      setTrackingParserError('');
      setTrackingImportSaveResult(null);
      setTrackingImportSaveError('');
      setTrackingImportSaving(false);
      setTrackingMatchEvidence(null);
      setTrackingMatchError('');
      setLatestTrackingImportBatchId(null);
      setStatusUpdateGate(null);
      setStatusUpdateResult(null);
      setStatusUpdateError('');
      setStatusUpdateLoading(false);
      setStatusUpdateApprovals({
        manualApproval: false,
        backupEvidenceAcknowledged: false,
        auditEvidenceAcknowledged: false,
        operatorChecklistAcknowledged: false,
      });
      setShipmentBoundary(null);
      setLoadError('');
      return () => { cancelled = true; };
    }

    async function loadOrders() {
      setLoading(true);
      setLoadError('');
      setHistoryLoading(true);
      setHistoryError('');
      setHistoryMessage('');
      setTrackingImportHistoryLoading(true);
      setTrackingImportHistoryError('');
      setTrackingImportHistoryMessage('');
      setTrackingParserPreview(null);
      setTrackingParserError('');
      setTrackingImportSaveResult(null);
      setTrackingImportSaveError('');
      setTrackingMatchLoading(true);
      setTrackingMatchError('');
      setTrackingMatchEvidence(null);
      setLatestTrackingImportBatchId(null);
      setStatusUpdateGate(null);
      setStatusUpdateResult(null);
      setStatusUpdateError('');
      setStatusUpdateApprovals({
        manualApproval: false,
        backupEvidenceAcknowledged: false,
        auditEvidenceAcknowledged: false,
        operatorChecklistAcknowledged: false,
      });
      setShipmentBoundary(null);
      setSaveError('');
      setSaveResult(null);
      try {
        const [orderResult, mappingResult, historyResult, trackingHistoryResult] = await Promise.all([
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
          dataProvider.getShippingExportHistory({
            storeId: selectedStoreId,
            platform: 'naver',
            limit: 10,
            includeRows: false,
          }),
          dataProvider.getShippingTrackingImportHistory({
            storeId: selectedStoreId,
            platform: 'naver',
            limit: 10,
            includeRows: false,
          }),
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
        setExportHistory(historyResult.data || []);
        setHistoryMessage(historyResult.businessMessage || '');
        setTrackingImportHistory(trackingHistoryResult.data || []);
        setTrackingImportHistoryMessage(trackingHistoryResult.businessMessage || '');
        const latestTrackingBatch = (trackingHistoryResult.data || [])[0];
        setLatestTrackingImportBatchId(latestTrackingBatch?.id || null);
        const matchResult = await dataProvider.checkShippingTrackingOrderMatchReadonly({
          storeId: selectedStoreId,
          platform: 'naver',
          importBatchId: latestTrackingBatch?.id || null,
          matchingContractAcknowledged: true,
          actorContext: {
            role: 'admin',
            actor_id: 'shipping-local-operator',
          },
        });
        if (cancelled) return;
        setTrackingMatchEvidence(matchResult);
        const boundaryResult = await dataProvider.checkShippingShipmentWritebackBoundary({
          storeId: selectedStoreId,
          platform: 'naver',
          manualApproval: false,
          matchedOrderCount: matchResult.matchedOrderCount || 0,
          totalTrackingRows: matchResult.totalTrackingRows || 0,
          matchingEvidenceAcknowledged: Boolean(matchResult.matchedOrderCount),
          backupEvidenceAcknowledged: false,
          auditEvidenceAcknowledged: false,
          naverWritebackBoundaryAcknowledged: true,
          operatorChecklistAcknowledged: false,
          actorContext: {
            role: 'admin',
            actor_id: 'shipping-local-operator',
          },
        });
        if (cancelled) return;
        setShipmentBoundary(boundaryResult);
      } catch (error) {
        if (!cancelled) {
          setOrders([]);
          setMappings([]);
          setDraftMappings([]);
          setExportHistory([]);
          setTrackingImportHistory([]);
          setTrackingParserPreview(null);
          setTrackingImportSaveResult(null);
          setTrackingMatchEvidence(null);
          setLatestTrackingImportBatchId(null);
          setStatusUpdateGate(null);
          setStatusUpdateResult(null);
          setShipmentBoundary(null);
          setTrackingMatchError(error.message || 'Tracking order match check failed.');
          setLoadError(error.message || '发货候选加载失败。');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setHistoryLoading(false);
          setTrackingImportHistoryLoading(false);
          setTrackingMatchLoading(false);
        }
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
    setExportError('');
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

  const generateExportPreview = async () => {
    setExportError('');
    setGeneratingExport(true);
    try {
      if (isBackendSource) {
        const exportRows = gate.rows.filter((row) => row.exportReady);
        const result = await dataProvider.generateShippingExcelExport({
          storeId: selectedStoreId,
          platform: 'naver',
          manualApproval: true,
          includeReceiverPrivacy: false,
          actorContext: {
            role: 'admin',
            actor_id: 'shipping-local-operator',
          },
          rows: exportRows.map((row) => ({
            orderReference: row.orderNo,
            productName: row.productName,
            optionName: row.optionName,
            quantity: row.quantity,
            logisticsInventoryCode: row.logisticsInventoryCode,
            logisticsProviderName: row.logisticsProviderName,
            logisticsCurrentStock: row.currentStockQuantity,
            platformProductIdHash: row.platformProductIdHash || null,
            platformOptionIdHash: row.platformOptionIdHash || null,
            internalSku: row.internalSku || '',
          })),
        });
        if (result.status !== 'shipping_excel_local_export_succeeded') {
          throw new Error(result.businessMessage || result.skipReason || '本地 Excel 生成未通过。');
        }
        setExportPreview(result);
        const historyResult = await dataProvider.getShippingExportHistory({
          storeId: selectedStoreId,
          platform: 'naver',
          limit: 10,
          includeRows: false,
        });
        setExportHistory(historyResult.data || []);
        setHistoryMessage(historyResult.businessMessage || '');
        return;
      }
      setExportPreview(buildShippingExcelExportMock({
        rows: gate.rows,
        selectedStore,
        selectedStoreId,
        includeReceiverPrivacy: false,
      }));
    } catch (error) {
      setExportError(error.message || 'Excel 导出生成失败。');
    } finally {
      setGeneratingExport(false);
    }
  };

  const selectTrackingParserFile = async (event) => {
    const file = event.target.files?.[0] || null;
    setTrackingParserPreview(null);
    setTrackingParserError('');
    setTrackingImportSaveResult(null);
    setTrackingImportSaveError('');
    setLatestTrackingImportBatchId(null);
    setStatusUpdateGate(null);
    setStatusUpdateResult(null);
    setStatusUpdateError('');
    setTrackingParserFile(file);
    setTrackingParserContentBase64('');
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      setTrackingParserError('Please select an xlsx file.');
      return;
    }
    try {
      const content = await readFileAsBase64(file);
      setTrackingParserContentBase64(content);
    } catch (error) {
      setTrackingParserError(error.message || 'File read failed.');
    }
  };

  const previewTrackingParserFile = async () => {
    if (!trackingParserFile || !trackingParserContentBase64) {
      setTrackingParserError('Please select an xlsx file first.');
      return;
    }
    setTrackingParserLoading(true);
    setTrackingParserError('');
    try {
      const result = await dataProvider.checkShippingTrackingImportXlsxParserMock({
        storeId: selectedStoreId,
        platform: 'naver',
        sourceFileName: trackingParserFile.name,
        fileContentBase64: trackingParserContentBase64,
        manualApproval: true,
        parserContractAcknowledged: true,
        actorContext: {
          role: 'admin',
          actor_id: 'shipping-local-operator',
        },
      });
      if (result.status !== 'tracking_xlsx_parser_mock_ready') {
        throw new Error(result.businessMessage || result.skipReason || 'Tracking xlsx preview failed.');
      }
      setTrackingParserPreview(result);
      setTrackingImportSaveResult(null);
      setTrackingImportSaveError('');
    } catch (error) {
      setTrackingParserPreview(null);
      setTrackingParserError(error.message || 'Tracking xlsx preview failed.');
    } finally {
      setTrackingParserLoading(false);
    }
  };

  const saveTrackingImportRecord = async () => {
    const rows = trackingParserPreview?.rows || [];
    if (trackingParserPreview?.status !== 'tracking_xlsx_parser_mock_ready' || !rows.length) {
      setTrackingImportSaveError('请先预览通过物流单号 xlsx。');
      return;
    }
    setTrackingImportSaving(true);
    setTrackingImportSaveError('');
    setTrackingImportSaveResult(null);
    setTrackingMatchError('');
    setStatusUpdateGate(null);
    setStatusUpdateResult(null);
    setStatusUpdateError('');
    try {
      const payload = {
        storeId: selectedStoreId,
        platform: 'naver',
        fileType: 'tracking_upload',
        fileFormat: 'xlsx',
        sourceFileName: trackingParserPreview.sourceFileName || trackingParserFile?.name || 'tracking-upload.xlsx',
        manualApproval: true,
        parserContractAcknowledged: true,
        actorContext: {
          role: 'admin',
          actor_id: 'shipping-local-operator',
        },
        rows: rows.map((row) => ({
          orderReference: row.orderNo,
          productOrderReference: row.productOrderNo,
          logisticsInventoryCode: row.logisticsInventoryCode,
          carrier: row.carrier,
          trackingNumber: row.trackingNumber,
          shippedAt: row.shippedAt,
          operatorNote: row.operatorNote,
        })),
      };
      const gateResult = await dataProvider.checkShippingTrackingImportWriteGate(payload);
      if (!['tracking_import_local_write_gate_ready', 'mock_tracking_import_local_record_ready'].includes(gateResult.status)) {
        throw new Error(gateResult.businessMessage || gateResult.skipReason || '物流单号导入记录门禁未通过。');
      }
      const writeResult = await dataProvider.writeShippingTrackingImport(payload);
      if (!['tracking_import_local_write_succeeded', 'mock_tracking_import_local_record_ready'].includes(writeResult.status)) {
        throw new Error(writeResult.businessMessage || writeResult.skipReason || '物流单号导入记录保存失败。');
      }
      setTrackingImportSaveResult(writeResult);

      const historyResult = await dataProvider.getShippingTrackingImportHistory({
        storeId: selectedStoreId,
        platform: 'naver',
        limit: 10,
        includeRows: false,
      });
      setTrackingImportHistory(historyResult.data || []);
      setTrackingImportHistoryMessage(historyResult.businessMessage || '');
      const nextBatchId = writeResult.importBatchId || (historyResult.data || [])[0]?.id || null;
      setLatestTrackingImportBatchId(nextBatchId);

      const matchResult = await dataProvider.checkShippingTrackingOrderMatchReadonly({
        storeId: selectedStoreId,
        platform: 'naver',
        importBatchId: nextBatchId,
        matchingContractAcknowledged: true,
        actorContext: {
          role: 'admin',
          actor_id: 'shipping-local-operator',
        },
      });
      setTrackingMatchEvidence(matchResult);
    } catch (error) {
      setTrackingImportSaveResult(null);
      setTrackingImportSaveError(error.message || '物流单号导入记录保存失败。');
    } finally {
      setTrackingImportSaving(false);
    }
  };

  const changeStatusUpdateApproval = (key, checked) => {
    setStatusUpdateApprovals((current) => ({ ...current, [key]: checked }));
    setStatusUpdateGate(null);
    setStatusUpdateResult(null);
    setStatusUpdateError('');
  };

  const buildStatusUpdatePayload = () => ({
    storeId: selectedStoreId,
    platform: 'naver',
    importBatchId: latestTrackingImportBatchId,
    manualApproval: Boolean(statusUpdateApprovals.manualApproval),
    matchingContractAcknowledged: true,
    backupEvidenceAcknowledged: Boolean(statusUpdateApprovals.backupEvidenceAcknowledged),
    auditEvidenceAcknowledged: Boolean(statusUpdateApprovals.auditEvidenceAcknowledged),
    operatorChecklistAcknowledged: Boolean(statusUpdateApprovals.operatorChecklistAcknowledged),
    targetOrderStatus: 'DISPATCHED',
    actorContext: {
      role: 'admin',
      actor_id: 'shipping-local-operator',
    },
  });

  const checkStatusUpdateGate = async () => {
    if (!latestTrackingImportBatchId) {
      setStatusUpdateError('请先导入物流单号并生成本地导入记录。');
      return null;
    }
    setStatusUpdateLoading(true);
    setStatusUpdateError('');
    setStatusUpdateResult(null);
    try {
      const result = await dataProvider.checkShippingTrackingOrderStatusLocalUpdateGate(buildStatusUpdatePayload());
      setStatusUpdateGate(result);
      return result;
    } catch (error) {
      setStatusUpdateGate(null);
      setStatusUpdateError(error.message || '本地订单状态更新门禁检查失败。');
      return null;
    } finally {
      setStatusUpdateLoading(false);
    }
  };

  const writeStatusUpdate = async () => {
    if (statusUpdateGate?.status !== 'tracking_order_status_update_gate_ready') {
      setStatusUpdateError('请先通过本地状态更新门禁检查。');
      return;
    }
    setStatusUpdateLoading(true);
    setStatusUpdateError('');
    try {
      const result = await dataProvider.writeShippingTrackingOrderStatusLocalUpdate(buildStatusUpdatePayload());
      if (!['tracking_order_status_update_succeeded', 'tracking_order_status_update_noop', 'mock_tracking_order_status_update_ready'].includes(result.status)) {
        throw new Error(result.businessMessage || result.skipReason || '本地订单状态更新未通过。');
      }
      setStatusUpdateResult(result);
      if (result.updatedOrderIds?.length && result.realDatabaseWritten) {
        const updatedIds = new Set(result.updatedOrderIds.map((item) => String(item)));
        setOrders((current) => current.map((order) => (
          updatedIds.has(String(order.id))
            ? {
              ...order,
              rawStatus: 'DISPATCHED',
              status: result.targetOrderStatusLabelZh || '已发货 / 配送中',
              deliveryStatus: 'DISPATCHED',
              deliveryStatusLabelZh: result.targetOrderStatusLabelZh || '已发货 / 配送中',
            }
            : order
        )));
      }
      if (isBackendSource) {
        const trackingHistoryResult = await dataProvider.getShippingTrackingImportHistory({
          storeId: selectedStoreId,
          platform: 'naver',
          limit: 10,
          includeRows: false,
        });
        setTrackingImportHistory(trackingHistoryResult.data || []);
        setTrackingImportHistoryMessage(trackingHistoryResult.businessMessage || '');
      }
    } catch (error) {
      setStatusUpdateResult(null);
      setStatusUpdateError(error.message || '本地订单状态更新失败。');
    } finally {
      setStatusUpdateLoading(false);
    }
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
        <SummaryCard title="可导出行" value={summary.exportReadyCount} note={isBackendSource ? '本地 Excel 文件' : 'Excel mock 预览'} tone={summary.exportReadyCount ? 'success' : 'default'} />
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
        generating={generatingExport}
        exportError={exportError}
        backendMode={isBackendSource}
      />
      <ExportHistoryPanel
        history={exportHistory}
        loading={historyLoading}
        error={historyError}
        businessMessage={historyMessage}
      />
      <TrackingImportParserUploadPanel
        fileName={trackingParserFile?.name || ''}
        fileSize={trackingParserFile?.size || 0}
        preview={trackingParserPreview}
        importResult={trackingImportSaveResult}
        loading={trackingParserLoading}
        saving={trackingImportSaving}
        error={trackingParserError}
        saveError={trackingImportSaveError}
        onFileChange={selectTrackingParserFile}
        onParse={previewTrackingParserFile}
        onSaveImport={saveTrackingImportRecord}
      />
      <TrackingImportHistoryPanel
        history={trackingImportHistory}
        loading={trackingImportHistoryLoading}
        error={trackingImportHistoryError}
        businessMessage={trackingImportHistoryMessage}
      />
      <TrackingOrderMatchEvidencePanel
        evidence={trackingMatchEvidence}
        loading={trackingMatchLoading}
        error={trackingMatchError}
      />
      <TrackingOrderStatusLocalUpdatePanel
        evidence={trackingMatchEvidence}
        gate={statusUpdateGate}
        result={statusUpdateResult}
        approvals={statusUpdateApprovals}
        onToggleApproval={changeStatusUpdateApproval}
        onCheckGate={checkStatusUpdateGate}
        onWrite={writeStatusUpdate}
        loading={statusUpdateLoading}
        error={statusUpdateError}
        latestImportBatchId={latestTrackingImportBatchId}
        backendMode={isBackendSource}
      />
      <ShipmentWritebackBoundaryPanel boundary={shipmentBoundary} />
      <ShippingOperatorRunbookPanel />

      <TechnicalDetails
        title="查看 Excel 生成 mock 门禁"
        description="当前只确认真实 Excel、导出记录、审计联动和物流单号回传的边界；不创建真实文件、不写导出记录。"
        items={[
          { label: 'phase', value: exportPreview?.phase || SHIPPING_EXPORT_MOCK_PHASE },
          { label: 'file_type', value: exportPreview?.fileType || 'shipping_request' },
          { label: 'file_format', value: exportPreview?.fileFormat || 'xlsx' },
          { label: 'export_batch_id', value: exportPreview?.exportBatchId || 'not_created' },
          { label: 'operation_audit_log_id', value: exportPreview?.operationAuditLogId || 'not_created' },
          { label: 'audit_correlation_id', value: exportPreview?.auditCorrelationId || 'not_created' },
          { label: 'file_path', value: exportPreview?.filePath || 'not_created' },
          { label: 'file_sha256', value: exportPreview?.fileSha256 || 'not_created' },
          { label: 'file_size_bytes', value: exportPreview?.fileSizeBytes || 0 },
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
