import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource } from '../utils/coreErpContract';
import { formatKstDateTimeWithLabel } from '../utils/time';

const PAGE_SIZE = 10;
const NAVER_REPLY_BODY_FIELD = 'answerComment';
const PROTECTED_NAVER_INQUIRY_PREFIX = 'pxg_naver_readonly:';
const replyClassificationOptions = [
  { value: 'unanswered', label: '未回复' },
  { value: 'answered', label: '已回复' },
];
const replyClassificationLabels = {
  unanswered: '未回复',
  answered: '已回复',
  unknown: '状态待确认',
};
const priorityOptions = ['普通', '重要', '紧急'];
const platformOptions = ['Naver', 'Coupang', 'Gmarket'];

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function readonlyIdFromProtectedCanonicalId(value) {
  const canonicalId = String(value ?? '').trim();
  if (!canonicalId.startsWith(PROTECTED_NAVER_INQUIRY_PREFIX)) return null;

  const readonlyId = canonicalId.slice(PROTECTED_NAVER_INQUIRY_PREFIX.length).trim();
  return /^\d+$/.test(readonlyId) ? readonlyId : null;
}

function text(value, fallback = '-') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function priorityLabel(value) {
  const normalized = comparable(value);
  if (['긴급', 'urgent', '紧急'].includes(normalized)) return '紧急';
  if (['중요', 'important', '重要'].includes(normalized)) return '重要';
  return '普通';
}

function normalizeMessage(row = {}) {
  const sourceInfo = classifyCoreDataSource(row);
  const replyClassification = ['unanswered', 'answered'].includes(row.replyClassification)
    ? row.replyClassification
    : 'unknown';
  return {
    ...row,
    ticketNo: row.ticketNo || row.caseNo || `MSG-${row.id}`,
    platform: text(row.platform || row.rawPlatform),
    store: text(row.store || row.storeName || row.store_name),
    customerName: text(row.customerName || row.customer || row.buyerName, '客户'),
    orderNo: text(row.orderNo || row.external_order_id, '未关联订单'),
    productName: text(row.productName || row.product || row.product_name, '未关联商品'),
    inquiryType: text(row.inquiryType || row.type || row.category, '客户咨询'),
    summary: text(row.summary || row.content || row.title, '暂无摘要'),
    content: row.content || '',
    conversation: Array.isArray(row.conversation) ? row.conversation : [],
    detailLoaded: Boolean(row.detailLoaded),
    replyClassification,
    replyClassificationLabel: row.replyClassificationLabel
      || replyClassificationLabels[replyClassification],
    priorityLabel: priorityLabel(row.priority),
    createdAt: row.createdAt || row.created_at || '',
    lastReplyAt: row.lastReplyAt || row.updatedAt || '',
    sourceInfo,
    replyEnabled: row.replyEnabled !== false,
    replyDisabledReason: row.replyDisabledReason || '',
    hasRelatedOrder: row.hasRelatedOrder === true,
    logisticsContext: row.logisticsContext || row.logistics_context || {},
    logisticsValidity: row.relatedOrder?.logisticsStale || row.relatedOrder?.isStale
      ? '已过期'
      : (row.relatedOrder?.logisticsUpdatedAt ? '有效' : '尚未发货或平台暂无物流信息'),
  };
}

function matches(row, query = {}) {
  const keyword = comparable(query.keyword);
  const haystack = [
    row.ticketNo,
    row.platform,
    row.store,
    row.customerName,
    row.orderNo,
    row.productName,
    row.inquiryType,
    row.summary,
    row.replyClassificationLabel,
    row.priorityLabel,
  ].map(comparable).join(' ');
  if (keyword && !haystack.includes(keyword)) return false;
  if (query.platform && comparable(row.platform) !== comparable(query.platform)) return false;
  if (query.classification && row.replyClassification !== query.classification) return false;
  if (query.priority && row.priorityLabel !== query.priority) return false;
  return true;
}

const columns = [
  { key: 'ticketNo', title: '消息编号', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'customerName', title: '客户' },
  { key: 'orderNo', title: '订单号' },
  { key: 'productName', title: '商品' },
  { key: 'inquiryType', title: '消息类型' },
  { key: 'summary', title: '内容摘要' },
  { key: 'replyClassificationLabel', title: '回复状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'priorityLabel', title: '紧急程度', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '创建时间' },
];

export default function CustomerService() {
  const [searchParams] = useSearchParams();
  const deepLinkInquiryId = searchParams.get('inquiryId');
  const protectedDeepLinkReadonlyId = readonlyIdFromProtectedCanonicalId(deepLinkInquiryId);
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', platform: '', classification: '', priority: '', page: 1 });
  const [draft, setDraft] = useState(query);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [syncMessage, setSyncMessage] = useState('');
  const [activeMessage, setActiveMessage] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [draftModal, setDraftModal] = useState({ open: false, message: null, content: '' });
  const [replyConfirm, setReplyConfirm] = useState(false);
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [draftReplies, setDraftReplies] = useState({});
  const platformReplyEnabled = false;

  const load = async (nextQuery = query) => {
    if (isBackendSource && storeLoading) return [];
    setLoading(true);
    setError('');
    try {
      if (isBackendSource && storeError) throw new Error(storeError);
      const params = {
        page: 1,
        pageSize: 100,
        platform: nextQuery.platform,
        classification: nextQuery.classification,
      };
      if (isBackendSource && selectedStoreId) params.storeId = selectedStoreId;
      const result = await dataProvider.getCustomerInquiries(params);
      const normalized = (result.data || result.items || []).map(normalizeMessage).filter((item) => matches(item, nextQuery));
      setRows(normalized);
      if (deepLinkInquiryId && !protectedDeepLinkReadonlyId) {
        setActiveMessage(normalized.find((item) => String(item.id ?? item.ticketNo) === deepLinkInquiryId) || null);
      }
      return normalized;
    } catch (requestError) {
      setRows([]);
      setError(requestError.message || '客户咨询加载失败');
      return [];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query, selectedStoreId, storeLoading, storeError, deepLinkInquiryId]);

  useEffect(() => {
    if (
      !protectedDeepLinkReadonlyId
      || !isBackendSource
      || storeLoading
      || storeError
      || !selectedStoreId
    ) return;

    setActiveMessage(normalizeMessage({
      id: deepLinkInquiryId,
      ticketNo: deepLinkInquiryId,
      readonlyId: protectedDeepLinkReadonlyId,
      storeId: selectedStoreId,
      platform: 'Naver',
      source: 'pxg_naver_readonly_local_v1',
      replyEnabled: false,
      detailLoaded: false,
    }));
  }, [deepLinkInquiryId, protectedDeepLinkReadonlyId, selectedStoreId, storeLoading, storeError]);

  const summary = useMemo(() => ({
    total: rows.length,
    unanswered: rows.filter((item) => item.replyClassification === 'unanswered').length,
    answered: rows.filter((item) => item.replyClassification === 'answered').length,
    urgent: rows.filter((item) => item.priorityLabel === '紧急').length,
  }), [rows]);

  const pageRows = rows.slice((query.page - 1) * PAGE_SIZE, query.page * PAGE_SIZE);

  const syncPlatformMessages = async () => {
    if (!selectedStoreId) {
      setSyncMessage('请先选择 Naver 店铺，再更新客户咨询。');
      window.setTimeout(() => setSyncMessage(''), 3200);
      return;
    }
    try {
      const syncResult = await dataProvider.refreshNaverCustomerInquiries({
        storeId: selectedStoreId,
      });
      const latestRows = await load(query);
      setSyncMessage(syncResult.message || `客户咨询已更新，当前显示 ${latestRows.length} 条。`);
    } catch (syncError) {
      setSyncMessage('Naver 客服消息暂不可用，请稍后重试');
    }
    window.setTimeout(() => setSyncMessage(''), 3200);
  };

  const openMessage = (message) => {
    setActiveMessage(message);
    setDetailError('');
  };

  useEffect(() => {
    if (
      !activeMessage
      || !activeMessage.readonlyId
      || activeMessage.detailLoaded
      || !isBackendSource
      || storeLoading
      || storeError
      || !selectedStoreId
    ) return undefined;
    let cancelled = false;
    setDetailLoading(true);
    setDetailError('');
    dataProvider.getCustomerInquiryDetail({
      readonlyId: activeMessage.readonlyId || activeMessage.id,
      storeId: selectedStoreId,
    }).then((detail) => {
      if (!cancelled) {
        setActiveMessage((current) => normalizeMessage({ ...current, ...detail, detailLoaded: true }));
      }
    }).catch(() => {
      if (!cancelled) setDetailError('客服消息详情暂不可用，请稍后重试');
    }).finally(() => {
      if (!cancelled) setDetailLoading(false);
    });
    return () => { cancelled = true; };
  }, [activeMessage?.id, activeMessage?.detailLoaded, selectedStoreId, storeLoading, storeError]);

  const openDraft = (message) => {
    setDraftModal({
      open: true,
      message,
      content: draftReplies[message.ticketNo] || '',
    });
    setReplyConfirm(false);
  };

  const saveDraft = () => {
    if (draftModal.message?.ticketNo) {
      setDraftReplies((current) => ({
        ...current,
        [draftModal.message.ticketNo]: draftModal.content,
      }));
    }
    setDraftModal({ open: false, message: null, content: '' });
  };

  const submitNaverReply = async () => {
    if (!draftModal.message || replySubmitting) return;
    setReplySubmitting(true);
    try {
      const result = await dataProvider.replyNaverCustomerInquiry({
        storeId: selectedStoreId,
        inquiryId: draftModal.message.id,
        externalInquiryId: draftModal.message.externalInquiryId || draftModal.message.ticketNo,
        [NAVER_REPLY_BODY_FIELD]: draftModal.content,
        manualApproval: true,
        finalOperatorConfirmation: replyConfirm,
        actorContext: { role: 'operator', action: 'manual_naver_customer_reply' },
      });
      setSyncMessage(result.message || 'Naver 客服回复处理完成。');
      setDraftModal({ open: false, message: null, content: '' });
      setReplyConfirm(false);
      await load(query);
    } catch (replyError) {
      setSyncMessage(replyError.message || '客户回复提交失败，请确认咨询状态或联系管理员。');
    } finally {
      setReplySubmitting(false);
      window.setTimeout(() => setSyncMessage(''), 3600);
    }
  };

  const search = () => setQuery({ ...draft, page: 1 });
  const reset = () => {
    const clean = { keyword: '', platform: '', classification: '', priority: '', page: 1 };
    setDraft(clean);
    setQuery(clean);
  };

  const activeConversation = activeMessage?.conversation || [];
  const hasStoreReply = activeConversation.some((message) => message.actor === 'store');
  const platformReplyContentUnavailable = activeMessage?.replyClassification === 'answered'
    && !hasStoreReply;

  return (
    <div className="customer-service-page">
      <PageHeader
        title="客户咨询"
        description="查看客户问题、订单和物流进度。当前只读，不发送平台回复。"
      />

      <div className="summary-grid">
        <SummaryCard title="客户咨询" value={summary.total} note="当前咨询总数" tone="info" />
        <SummaryCard title="未回复" value={summary.unanswered} note="等待店铺回复" tone={summary.unanswered ? 'warning' : 'success'} />
        <SummaryCard title="已回复" value={summary.answered} note="已有店铺答复" tone="success" />
        <SummaryCard title="紧急消息" value={summary.urgent} note="优先处理" tone={summary.urgent ? 'danger' : 'success'} />
      </div>

      <FilterPanel>
        <SearchBar
          value={draft.keyword}
          onChange={(keyword) => setDraft({ ...draft, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索客户、订单号、商品名或消息内容"
        >
          <select value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={draft.classification} onChange={(event) => setDraft({ ...draft, classification: event.target.value })}>
            <option value="">全部</option>
            {replyClassificationOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })}>
            <option value="">全部紧急程度</option>
            {priorityOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {syncMessage ? <div className="form-info">{syncMessage}</div> : null}
        {error ? <EmptyState title="客户咨询加载失败" description={error} /> : null}
        {!error && !loading && !rows.length ? (
          <EmptyState
            title="当前没有客户咨询"
            description="当前读取窗口暂无关联订单或客户咨询。"
          />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={pageRows}
              loading={loading}
              renderActions={(row) => (
                <>
                  <button type="button" onClick={() => openMessage(row)}>详情</button>
                  <button type="button" className="inquiry-reply-button" disabled={!platformReplyEnabled || !row.replyEnabled} title="当前咨询仅供查看，不能发送">回复</button>
                </>
              )}
            />
            <Pagination page={query.page} pageSize={PAGE_SIZE} total={rows.length} onChange={(page) => setQuery({ ...query, page })} />
          </>
        )}
      </section>

      <DetailModal open={Boolean(activeMessage)} title={activeMessage ? `消息详情 · ${activeMessage.ticketNo}` : '消息详情'} onClose={() => setActiveMessage(null)}>
        {activeMessage ? (
          <>
            <div className="detail-grid">
              {[
                ['平台', activeMessage.platform],
                ['店铺', activeMessage.store],
                ['客户', activeMessage.customerName],
                ['订单号', activeMessage.orderNo],
                ['商品', activeMessage.productName],
                ['订单状态', activeMessage.hasRelatedOrder ? (activeMessage.relatedOrder?.orderStatus || '待确认') : '当前读取窗口暂无关联订单'],
                ['发货批次', activeMessage.hasRelatedOrder ? (activeMessage.relatedOrder?.batchNo || '尚未进入批次') : '当前读取窗口暂无关联订单'],
                ['仓库进度', activeMessage.hasRelatedOrder ? (activeMessage.relatedOrder?.warehouseStatus || activeMessage.relatedOrder?.batchStatus || '待处理') : '当前读取窗口暂无关联订单'],
                ['快递公司', activeMessage.relatedOrder?.carrier || '尚未发货或平台暂无物流信息'],
                ['物流单号', activeMessage.relatedOrder?.trackingNumber || '尚未发货或平台暂无物流信息'],
                ['物流状态', activeMessage.relatedOrder?.deliveryStatusLabelZh || activeMessage.relatedOrder?.deliveryStatus || '尚未发货或平台暂无物流信息'],
                ['物流更新时间', activeMessage.relatedOrder?.logisticsUpdatedAt || '-'],
                ['物流有效期', activeMessage.logisticsValidity],
                ['回复状态', <StatusBadge value={activeMessage.replyClassificationLabel} />],
                ['紧急程度', <StatusBadge value={activeMessage.priorityLabel} />],
                ['记录状态', activeMessage.sourceInfo.label],
              ].map(([label, value]) => (
                <div className="detail-item" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <section className="detail-section inquiry-conversation-section">
              <h3>咨询对话</h3>
              {detailLoading ? <p>正在加载客服消息详情...</p> : null}
              {detailError ? <p className="detail-error">{detailError}</p> : null}
              {!detailLoading && !detailError ? (
                <div className="conversation-timeline" role="list" aria-label="客户咨询对话">
                  {activeConversation.length ? activeConversation.map((message, index) => (
                    <article
                      className={`conversation-message conversation-message-${message.actor}`}
                      key={`${message.actor}-${message.sentAt || 'unknown'}-${index}`}
                      role="listitem"
                    >
                      <div className="conversation-bubble">
                        <div className="conversation-meta">
                          <strong>{message.actor === 'store' ? '店铺' : '客户'}</strong>
                          <time>{message.sentAt ? formatKstDateTimeWithLabel(message.sentAt) : '时间未提供'}</time>
                        </div>
                        <p>{message.content}</p>
                      </div>
                    </article>
                  )) : <p className="conversation-empty">暂无可显示的对话内容</p>}
                  {platformReplyContentUnavailable ? (
                    <div className="conversation-answer-unavailable" role="status">
                      <strong>已回复</strong>
                      <span>Naver 已记录店铺回复{activeMessage.answeredAt ? `，回复时间为 ${formatKstDateTimeWithLabel(activeMessage.answeredAt)}` : ''}，但平台未提供历史回复正文。</span>
                    </div>
                  ) : null}
                  {!hasStoreReply && !platformReplyContentUnavailable ? (
                    <div className="conversation-unanswered" role="status">
                      <strong>未回复</strong>
                      <span>当前对话中没有店铺回复。</span>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>
          </>
        ) : <EmptyState title="暂无消息详情" description="请选择消息查看详情。" />}
      </DetailModal>

      <Modal
        open={draftModal.open}
        title={draftModal.message ? `回复 · ${draftModal.message.ticketNo}` : '回复'}
        onClose={() => setDraftModal({ open: false, message: null, content: '' })}
        onConfirm={submitNaverReply}
        confirmText={!platformReplyEnabled ? '试运营中禁止发送' : replySubmitting ? '提交中...' : '提交到 Naver'}
        confirmDisabled={!platformReplyEnabled || replySubmitting || !replyConfirm || !draftModal.content.trim()}
        width="min(860px, 94vw)"
      >
        <FormField label="草稿内容">
          <textarea
            value={draftModal.content}
            onChange={(event) => setDraftModal({ ...draftModal, content: event.target.value })}
            placeholder="填写给客户的回复内容。提交到 Naver 前请再次核对。"
          />
        </FormField>
        <label className="checkbox-line">
          <input
            type="checkbox"
            disabled={!platformReplyEnabled}
            checked={replyConfirm}
            onChange={(event) => setReplyConfirm(event.target.checked)}
          />
          <span>人工确认发送：我已核对回复内容，并确认提交到 Naver。</span>
        </label>
        {!platformReplyEnabled ? <div className="form-info">当前为模拟试运营，只能保存或复制回复草稿，不能发送到真实 Naver。</div> : null}
        <div className="modal-actions-inline">
          <button type="button" className="button ghost" onClick={saveDraft} disabled={replySubmitting}>保存本地草稿</button>
        </div>
        <p className="mock-sync-note">当前每条客户咨询都需要运营人员核对后单独发送。</p>
      </Modal>
    </div>
  );
}
