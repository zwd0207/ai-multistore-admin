import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
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
import { classifyCoreDataSource, getDangerousActionState } from '../utils/coreErpContract';

const PAGE_SIZE = 10;
const NAVER_REPLY_BODY_FIELD = 'answerComment';
const statusOptions = ['待处理', '处理中', '已记录', '需人工处理'];
const priorityOptions = ['普通', '重要', '紧急'];
const platformOptions = ['Naver', 'Coupang', 'Gmarket'];

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function text(value, fallback = '-') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function statusLabel(value) {
  const normalized = comparable(value);
  if (['문의 대기', 'pending', '待处理'].includes(normalized)) return '待处理';
  if (['처리중', 'processing', '处理中', '환불 요청', '교환 요청'].includes(normalized)) return '处理中';
  if (['답변 완료', 'done', 'closed', '已回复', '已记录'].includes(normalized)) return '已记录';
  return value ? '需人工处理' : '待处理';
}

function priorityLabel(value) {
  const normalized = comparable(value);
  if (['긴급', 'urgent', '紧急'].includes(normalized)) return '紧急';
  if (['중요', 'important', '重要'].includes(normalized)) return '重要';
  return '普通';
}

function normalizeMessage(row = {}) {
  const sourceInfo = classifyCoreDataSource(row);
  return {
    ...row,
    ticketNo: row.ticketNo || row.caseNo || `MSG-${row.id}`,
    platform: text(row.platform || row.rawPlatform),
    store: text(row.store || row.storeName || row.store_name),
    customerName: text(row.customerName || row.customer || row.buyerName, '客户'),
    orderNo: text(row.orderNo || row.external_order_id, '未关联订单'),
    productName: text(row.productName || row.product || row.product_name, '未关联商品'),
    inquiryType: text(row.inquiryType || row.type || row.category, '平台消息'),
    summary: text(row.summary || row.content || row.title, '暂无摘要'),
    content: text(row.content || row.summary, '暂无内容'),
    statusLabel: statusLabel(row.status),
    priorityLabel: priorityLabel(row.priority),
    createdAt: row.createdAt || row.created_at || '',
    lastReplyAt: row.lastReplyAt || row.updatedAt || '',
    sourceInfo,
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
    row.statusLabel,
    row.priorityLabel,
  ].map(comparable).join(' ');
  if (keyword && !haystack.includes(keyword)) return false;
  if (query.platform && comparable(row.platform) !== comparable(query.platform)) return false;
  if (query.status && row.statusLabel !== query.status) return false;
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
  { key: 'statusLabel', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'priorityLabel', title: '紧急程度', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '创建时间' },
];

export default function CustomerService() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', platform: '', status: '', priority: '', page: 1 });
  const [draft, setDraft] = useState(query);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [syncMessage, setSyncMessage] = useState('');
  const [activeMessage, setActiveMessage] = useState(null);
  const [draftModal, setDraftModal] = useState({ open: false, message: null, content: '' });
  const [replyConfirm, setReplyConfirm] = useState(false);
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [draftReplies, setDraftReplies] = useState({});

  const load = async (nextQuery = query) => {
    if (isBackendSource && storeLoading) return [];
    setLoading(true);
    setError('');
    try {
      if (isBackendSource && storeError) throw new Error(storeError);
      const params = { page: 1, pageSize: 100, platform: nextQuery.platform };
      if (isBackendSource && selectedStoreId) params.storeId = selectedStoreId;
      const result = await dataProvider.getCustomerInquiries(params);
      const normalized = (result.data || result.items || []).map(normalizeMessage).filter((item) => matches(item, nextQuery));
      setRows(normalized);
      return normalized;
    } catch (requestError) {
      setRows([]);
      setError(requestError.message || '平台消息加载失败');
      return [];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query, selectedStoreId, storeLoading, storeError]);

  const summary = useMemo(() => ({
    total: rows.length,
    pending: rows.filter((item) => item.statusLabel === '待处理').length,
    urgent: rows.filter((item) => item.priorityLabel === '紧急').length,
    manual: rows.filter((item) => item.statusLabel === '需人工处理' || item.priorityLabel === '紧急').length,
  }), [rows]);

  const dangerousState = getDangerousActionState('customer_auto_reply');
  const pageRows = rows.slice((query.page - 1) * PAGE_SIZE, query.page * PAGE_SIZE);

  const syncPlatformMessages = async () => {
    if (!selectedStoreId) {
      setSyncMessage('请先选择 Naver 店铺，再同步客服消息。');
      window.setTimeout(() => setSyncMessage(''), 3200);
      return;
    }
    try {
      const syncResult = await dataProvider.syncNaverCustomerInquiries({
        storeId: selectedStoreId,
        page: 1,
        size: 50,
      });
      const latestRows = await load(query);
      setSyncMessage(syncResult.message || `已接入 Naver 官方 API 读取，当前显示 ${latestRows.length} 条消息。`);
    } catch (syncError) {
      setSyncMessage(syncError.message || 'Naver 客服消息同步失败，请检查店铺 API 权限或 IP 白名单。');
    }
    window.setTimeout(() => setSyncMessage(''), 3200);
  };

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
      setSyncMessage(replyError.message || 'Naver 客服回复提交失败，请检查 API 权限或消息状态。');
    } finally {
      setReplySubmitting(false);
      window.setTimeout(() => setSyncMessage(''), 3600);
    }
  };

  const search = () => setQuery({ ...draft, page: 1 });
  const reset = () => {
    const clean = { keyword: '', platform: '', status: '', priority: '', page: 1 };
    setDraft(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="平台消息"
        description="已接入 Naver 官方 API 读取；Coupang / Gmarket 消息仍作为本地入口。回复必须由运营人工确认后提交。"
        actions={(
          <>
            <button type="button" className="button primary" onClick={syncPlatformMessages}>同步平台消息</button>
            <Link className="button ghost" to="/stores">检查店铺连接</Link>
            <Link className="button ghost" to="/emails">检查邮箱连接</Link>
          </>
        )}
      />

      <div className="summary-grid">
        <SummaryCard title="平台消息" value={summary.total} note="读取自本地保存记录" tone="info" />
        <SummaryCard title="待处理" value={summary.pending} note="需人工查看" tone={summary.pending ? 'warning' : 'success'} />
        <SummaryCard title="紧急消息" value={summary.urgent} note="优先处理" tone={summary.urgent ? 'danger' : 'success'} />
        <SummaryCard title="需人工到平台后台处理" value={summary.manual} note="不自动回复客户" tone="warning" />
      </div>

      <section className="content-card">
        <div className="business-capability-grid compact">
          <article className="business-capability-card warning">
            <div className="business-capability-head"><strong>Naver 客服消息</strong><span>已接入读取</span></div>
            <p>已接入 Naver 官方 API 读取，写入本地 ERP；Coupang / Gmarket 暂未接入真实平台消息。</p>
          </article>
          <article className="business-capability-card info">
            <div className="business-capability-head"><strong>回复处理</strong><span>人工确认</span></div>
            <p>Naver 回复可以在人工确认发送后提交到平台；本地草稿仍可单独保存。</p>
          </article>
          <article className="business-capability-card muted">
            <div className="business-capability-head"><strong>自动回复客户</strong><span>{dangerousState.label}</span></div>
            <p>{dangerousState.note}</p>
          </article>
        </div>
      </section>

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
          <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })}>
            <option value="">全部紧急程度</option>
            {priorityOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {syncMessage ? <div className="form-info">{syncMessage}</div> : null}
        {error ? <EmptyState title="平台消息加载失败" description={error} /> : null}
        {!error && !loading && !rows.length ? (
          <EmptyState
            title="当前没有平台消息"
            description="可以同步 Naver 客服消息；如果仍为空，请检查店铺连接、API 权限或 IP 白名单。"
            actions={(
              <>
                <button type="button" className="button primary" onClick={syncPlatformMessages}>同步平台消息</button>
                <Link className="button ghost" to="/stores">检查店铺连接</Link>
                <Link className="button ghost" to="/emails">检查邮箱连接</Link>
              </>
            )}
          />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={pageRows}
              loading={loading}
              renderActions={(row) => (
                <>
                  <button type="button" onClick={() => setActiveMessage(row)}>详情</button>
                  <button type="button" onClick={() => openDraft(row)}>回复</button>
                  <button type="button" disabled title="需人工到平台后台处理">平台后台处理</button>
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
                ['状态', <StatusBadge value={activeMessage.statusLabel} />],
                ['紧急程度', <StatusBadge value={activeMessage.priorityLabel} />],
                ['数据来源', activeMessage.sourceInfo.label],
              ].map(([label, value]) => (
                <div className="detail-item" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <section className="detail-section">
              <h3>消息内容</h3>
              <p>{activeMessage.content}</p>
            </section>
            <section className="detail-section">
              <h3>处理边界</h3>
              <p>Naver 客服回复支持人工确认后提交；退款、换货、投诉处理仍需人工到平台后台处理。</p>
            </section>
          </>
        ) : <EmptyState title="暂无消息详情" description="请选择消息查看详情。" />}
      </DetailModal>

      <Modal
        open={draftModal.open}
        title={draftModal.message ? `回复 · ${draftModal.message.ticketNo}` : '回复'}
        onClose={() => setDraftModal({ open: false, message: null, content: '' })}
        onConfirm={submitNaverReply}
        confirmText={replySubmitting ? '提交中...' : '提交到 Naver'}
        confirmDisabled={replySubmitting || !replyConfirm || !draftModal.content.trim()}
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
            checked={replyConfirm}
            onChange={(event) => setReplyConfirm(event.target.checked)}
          />
          <span>人工确认发送：我已核对回复内容，并确认提交到 Naver。</span>
        </label>
        <div className="modal-actions-inline">
          <button type="button" className="button ghost" onClick={saveDraft} disabled={replySubmitting}>保存本地草稿</button>
        </div>
        <p className="mock-sync-note">自动回复客户仍未开放；这里只允许运营人工确认后提交单条 Naver 回复。</p>
      </Modal>
    </>
  );
}
