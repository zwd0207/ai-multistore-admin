import { useEffect, useState } from 'react';
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
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';

const platforms = ['Naver', 'Coupang', 'Gmarket', '11街', '옥션'];
const statuses = ['문의 대기', '답변 완료', '처리중', '환불 요청', '교환 요청'];
const priorities = ['일반', '중요', '긴급'];

const columns = [
  { key: 'ticketNo', title: '咨询编号', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'customerName', title: '客户名' },
  { key: 'orderNo', title: '订单号' },
  { key: 'productName', title: '商品名' },
  { key: 'inquiryType', title: '咨询类型' },
  { key: 'summary', title: '咨询内容摘要' },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'priority', title: '紧急程度', render: (value) => <StatusBadge value={value} /> },
  { key: 'createdAt', title: '创建时间' },
  { key: 'lastReplyAt', title: '最后回复时间' },
];

export default function CustomerService() {
  const [query, setQuery] = useState({ keyword: '', platform: '', status: '', priority: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [loading, setLoading] = useState(true);
  const [templates, setTemplates] = useState([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [replyOpen, setReplyOpen] = useState(false);
  const [activeTicket, setActiveTicket] = useState(null);
  const [replyForm, setReplyForm] = useState({ content: '', nextStatus: '답변 완료' });
  const [replyError, setReplyError] = useState('');
  const [loadError, setLoadError] = useState('');

  const load = async (nextQuery = query) => {
    setLoading(true);
    setLoadError('');
    try {
      const response = await dataProvider.getCustomerInquiries(nextQuery);
      setResult(response);
    } catch (error) {
      setResult({ data: [], total: 0, page: nextQuery.page, pageSize: nextQuery.pageSize });
      setLoadError(error.message || '客服咨询加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query]);

  useEffect(() => {
    if (!isBackendSource) mockApi.getReplyTemplates().then(setTemplates);
  }, []);

  const openDetail = async (row) => {
    const detail = isBackendSource ? row : await mockApi.getCustomerTicketDetail(row.id);
    setActiveTicket(detail);
    setDetailOpen(true);
  };

  const openReply = async (row) => {
    const detail = await mockApi.getCustomerTicketDetail(row.id);
    setActiveTicket(detail);
    setReplyForm({ content: '', nextStatus: '답변 완료' });
    setReplyError('');
    setReplyOpen(true);
  };

  const applyStatus = async (row, status) => {
    await mockApi.updateCustomerTicketStatus(row.id, status);
    if (activeTicket?.id === row.id) {
      setActiveTicket(await mockApi.getCustomerTicketDetail(row.id));
    }
    await load();
  };

  const submitReply = async () => {
    const content = replyForm.content.trim();
    if (!content) {
      setReplyError('回复内容不能为空');
      return;
    }
    if (content.length < 5) {
      setReplyError('回复内容至少需要 5 个字符');
      return;
    }

    await mockApi.replyCustomerTicket(activeTicket.id, replyForm);
    setReplyOpen(false);
    if (detailOpen) {
      setActiveTicket(await mockApi.getCustomerTicketDetail(activeTicket.id));
    }
    await load();
  };

  return (
    <>
      <PageHeader
        title="客服管理"
        description="集中处理多平台咨询、回复、退款与换货流转。"
        actions={<><button className="button ghost" onClick={() => load()}>刷新列表</button>{isBackendSource && <span className="period-chip">后端只读</span>}</>}
      />

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', platform: '', status: '', priority: '', page: 1, pageSize: 5 };
            setDraftQuery(clean);
            setQuery(clean);
          }}
          placeholder="搜索客户名、订单号、商品名或咨询内容"
        >
          <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platforms.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {statuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.priority} onChange={(event) => setDraftQuery({ ...draftQuery, priority: event.target.value })}>
            <option value="">全部紧急程度</option>
            {priorities.map((item) => <option key={item}>{item}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {loadError ? <EmptyState title="客服咨询加载失败" description={loadError} /> : <><DataTable
          columns={columns}
          rows={result.data || []}
          loading={loading}
          renderActions={(row) => (
            <>
              <button onClick={() => openDetail(row)}>详情</button>
              {!isBackendSource && <><button onClick={() => openReply(row)}>回复</button>
                <button onClick={() => applyStatus(row, '답변 완료')}>标记完成</button>
                <button onClick={() => applyStatus(row, '환불 요청')}>转退款</button>
                <button onClick={() => applyStatus(row, '교환 요청')}>转换货</button></>}
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
        </>}
      </section>

      <DetailModal open={detailOpen} title={activeTicket ? `咨询详情 · ${activeTicket.ticketNo}` : '咨询详情'} onClose={() => setDetailOpen(false)}>
        {activeTicket ? (
          <>
            <section className="detail-section">
              <h3>完整咨询内容</h3>
              <div className="badge-row">
                <StatusBadge value={activeTicket.status} />
                <StatusBadge value={activeTicket.priority} />
              </div>
              <p>{activeTicket.content}</p>
            </section>

            <section className="detail-section">
              <h3>订单信息</h3>
              <div className="detail-grid">
                <div className="detail-item"><span>订单号</span><strong>{activeTicket.orderInfo.orderNo}</strong></div>
                <div className="detail-item"><span>支付方式</span><strong>{activeTicket.orderInfo.paymentMethod}</strong></div>
                <div className="detail-item"><span>收件人</span><strong>{activeTicket.orderInfo.receiver}</strong></div>
                <div className="detail-item"><span>订单金额</span><strong>{activeTicket.orderInfo.amount.toLocaleString()}원</strong></div>
                <div className="detail-item"><span>收货地址</span><strong>{activeTicket.orderInfo.address}</strong></div>
              </div>
            </section>

            <section className="detail-section">
              <h3>商品信息</h3>
              <div className="detail-grid">
                <div className="detail-item"><span>商品名</span><strong>{activeTicket.productInfo.productName}</strong></div>
                <div className="detail-item"><span>SKU</span><strong>{activeTicket.productInfo.sku}</strong></div>
                <div className="detail-item"><span>数量</span><strong>{activeTicket.productInfo.quantity}</strong></div>
                <div className="detail-item"><span>店铺</span><strong>{activeTicket.productInfo.store}</strong></div>
              </div>
            </section>

            <section className="detail-section">
              <h3>历史回复记录</h3>
              <div className="reply-list">
                {activeTicket.replies.length ? activeTicket.replies.map((reply) => (
                  <article key={reply.id} className="reply-item">
                    <header>
                      <strong>{reply.author}</strong>
                      <time>{reply.createdAt}</time>
                    </header>
                    <p>{reply.content}</p>
                  </article>
                )) : <EmptyState title="暂无历史回复" description="这条咨询还没有人工回复记录。" />}
              </div>
            </section>
          </>
        ) : <EmptyState title="暂无详情" description="请选择一条咨询记录查看详情。" />}
      </DetailModal>

      <Modal
        open={replyOpen}
        title={activeTicket ? `回复咨询 · ${activeTicket.ticketNo}` : '回复咨询'}
        onClose={() => setReplyOpen(false)}
        onConfirm={submitReply}
        confirmText="发送回复"
        width="min(900px, 94vw)"
      >
        <div className="detail-section">
          <h3>常用回复模板</h3>
          <div className="template-list">
            {templates.map((item) => (
              <article key={item.id} className="template-item">
                <strong>{item.title}</strong>
                <p>{item.content}</p>
                <button className="button ghost" onClick={() => setReplyForm({ ...replyForm, content: item.content })}>使用模板</button>
              </article>
            ))}
          </div>
        </div>

        <div className="form-grid">
          <FormField label="回复后状态" required>
            <select value={replyForm.nextStatus} onChange={(event) => setReplyForm({ ...replyForm, nextStatus: event.target.value })}>
              {statuses.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="当前咨询摘要">
            <input value={activeTicket?.summary || ''} readOnly />
          </FormField>
        </div>

        <FormField label="回复内容" required error={replyError}>
          <textarea
            value={replyForm.content}
            onChange={(event) => {
              setReplyForm({ ...replyForm, content: event.target.value });
              if (replyError) setReplyError('');
            }}
            placeholder="请输入回复内容，至少 5 个字符"
          />
        </FormField>
      </Modal>
    </>
  );
}
