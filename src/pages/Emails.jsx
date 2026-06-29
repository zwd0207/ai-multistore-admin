import { useEffect, useState } from 'react';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import FormField from '../components/common/FormField';
import InfoGrid from '../components/common/InfoGrid';
import LogList from '../components/common/LogList';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import RiskPanel from '../components/common/RiskPanel';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import mockApi from '../services/mockApi';

const platforms = ['Naver', 'Coupang', 'Gmarket', '11街', '옥션'];
const emailStatuses = ['정상', '확인 필요', '인증 필요', '수신 실패', '위험', '사용중지'];
const emailTypes = ['平台通知', '客服咨询', '申诉通知', '结算通知', '订单通知', '风险提醒', '기타'];
const riskLevels = ['낮음', '보통', '높음', '긴급'];
const storeOptions = ['스마트스토어 뷰티샵', '韩国本土运动鞋店', 'Gmarket 럭셔리 골프관', '11街 韩系生活馆', 'K-Beauty 글로벌샵', '옥션 아웃도어 셀렉트', 'Coupang 키즈 패션랩'];

const columns = [
  { key: 'emailNo', title: '邮箱编号', render: (value) => <strong>{value}</strong> },
  { key: 'address', title: '邮箱地址' },
  { key: 'platform', title: '绑定平台' },
  { key: 'store', title: '绑定店铺' },
  { key: 'purpose', title: '邮箱用途' },
  { key: 'lastReceivedAt', title: '最近收件时间' },
  { key: 'unreadCount', title: '未读数量' },
  { key: 'importantCount', title: '重要邮件数量' },
  { key: 'status', title: '邮箱状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'riskLevel', title: '风险等级', render: (value) => <StatusBadge value={value} /> },
];

const initialForm = {
  emailNo: '',
  address: '',
  platform: 'Naver',
  store: '',
  purpose: '平台通知',
  lastReceivedAt: '',
  status: '정상',
  riskLevel: '보통',
  remarks: '',
};

export default function Emails() {
  const [query, setQuery] = useState({ keyword: '', platform: '', store: '', status: '', emailType: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [recentEmails, setRecentEmails] = useState({ data: [], total: 0 });
  const [detailOpen, setDetailOpen] = useState(false);
  const [accountModal, setAccountModal] = useState({ open: false, editing: null });
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});

  const load = async (nextQuery = query) => {
    setLoading(true);
    try {
      const response = await mockApi.getEmails(nextQuery);
      setResult(response);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query]);

  const openDetail = async (row) => {
    const [detailData, mailData] = await Promise.all([
      mockApi.getEmailDetail(row.id),
      mockApi.getRecentEmails({ accountId: row.id, page: 1, pageSize: 10 }),
    ]);
    setDetail(detailData);
    setRecentEmails(mailData);
    setDetailOpen(true);
  };

  const openCreateModal = () => {
    setForm(initialForm);
    setErrors({});
    setAccountModal({ open: true, editing: null });
  };

  const openEditModal = (row) => {
    setForm({
      emailNo: row.emailNo,
      address: row.address,
      platform: row.platform,
      store: row.store,
      purpose: row.purpose,
      lastReceivedAt: row.lastReceivedAt,
      status: row.status,
      riskLevel: row.riskLevel,
      remarks: row.remarks || '',
    });
    setErrors({});
    setAccountModal({ open: true, editing: row });
  };

  const saveAccount = async () => {
    const nextErrors = {};
    ['address', 'platform', 'purpose', 'status', 'riskLevel'].forEach((key) => {
      if (!String(form[key] ?? '').trim()) nextErrors[key] = '该字段不能为空';
    });
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const payload = {
      emailNo: form.emailNo,
      address: form.address,
      platform: form.platform,
      store: form.store || '未绑定',
      purpose: form.purpose,
      lastReceivedAt: form.lastReceivedAt || '2026-06-29 16:00',
      status: form.status,
      riskLevel: form.riskLevel,
      remarks: form.remarks,
    };

    if (accountModal.editing) {
      await mockApi.updateEmail(accountModal.editing.id, payload);
    } else {
      await mockApi.createEmail(payload);
    }

    setAccountModal({ open: false, editing: null });
    await load();
  };

  const refreshDetail = async (accountId) => {
    const [detailData, mailData] = await Promise.all([
      mockApi.getEmailDetail(accountId),
      mockApi.getRecentEmails({ accountId, page: 1, pageSize: 10 }),
    ]);
    setDetail(detailData);
    setRecentEmails(mailData);
    await load();
  };

  const markImportant = async (mailId) => {
    await mockApi.markEmailImportant(mailId);
    if (detail) await refreshDetail(detail.id);
  };

  const markHandled = async (mailId) => {
    await mockApi.markEmailHandled(mailId);
    if (detail) await refreshDetail(detail.id);
  };

  return (
    <>
      <PageHeader
        title="邮箱管理"
        description="集中管理平台通知邮箱、申诉邮箱、客服邮箱和提醒记录。"
        actions={<button className="button primary" onClick={openCreateModal}>新增邮箱</button>}
      />

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', platform: '', store: '', status: '', emailType: '', page: 1, pageSize: 5 };
            setDraftQuery(clean);
            setQuery(clean);
          }}
          placeholder="搜索邮箱编号、邮箱地址、邮件标题或提醒摘要"
        >
          <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platforms.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.store} onChange={(event) => setDraftQuery({ ...draftQuery, store: event.target.value })}>
            <option value="">全部店铺</option>
            {storeOptions.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部邮箱状态</option>
            {emailStatuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.emailType} onChange={(event) => setDraftQuery({ ...draftQuery, emailType: event.target.value })}>
            <option value="">全部邮件类型</option>
            {emailTypes.map((item) => <option key={item}>{item}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        <DataTable
          columns={columns}
          rows={result.data}
          loading={loading}
          renderActions={(row) => (
            <>
              <button onClick={() => openDetail(row)}>详情</button>
              <button onClick={() => openDetail(row)}>查看邮件</button>
              <button onClick={() => openEditModal(row)}>编辑</button>
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </section>

      <DetailModal open={detailOpen} title={detail ? `邮箱详情 · ${detail.emailNo}` : '邮箱详情'} onClose={() => setDetailOpen(false)} width="min(980px, 94vw)">
        {detail ? (
          <>
            <section className="detail-section">
              <h3>邮箱基础信息</h3>
              <InfoGrid items={[
                { label: '邮箱地址', value: detail.address },
                { label: '绑定平台', value: detail.platform },
                { label: '绑定店铺', value: detail.store },
                { label: '邮箱用途', value: detail.purpose },
                { label: '邮箱状态', value: <StatusBadge value={detail.status} /> },
                { label: '风险等级', value: <StatusBadge value={detail.riskLevel} /> },
              ]} />
            </section>

            <section className="detail-section">
              <h3>最近邮件列表</h3>
              {recentEmails.data.length ? (
                <div className="reply-list">
                  {recentEmails.data.map((mail) => (
                    <article key={mail.id} className="mail-card">
                      <div className="mail-card-header">
                        <div>
                          <strong>{mail.title}</strong>
                          <div className="ranking-meta">{mail.sender} · {mail.emailType}</div>
                        </div>
                        <div className="badge-row">
                          <StatusBadge value={mail.handledStatus} />
                          {mail.important && <StatusBadge value="重要" />}
                        </div>
                      </div>
                      <p>{mail.summary}</p>
                      <footer>
                        <time>{mail.receivedAt}</time>
                        <div className="detail-toolbar">
                          {!mail.important && <button className="button ghost" onClick={() => markImportant(mail.id)}>标记重要</button>}
                          {mail.handledStatus !== '已处理' && <button className="button ghost" onClick={() => markHandled(mail.id)}>标记已处理</button>}
                        </div>
                      </footer>
                    </article>
                  ))}
                </div>
              ) : <EmptyState title="暂无最近邮件" description="当前邮箱还没有可展示的 mock 邮件。" />}
            </section>

            <RiskPanel title="重要邮件提醒" items={detail.importantAlerts.map((item, index) => ({ id: index, title: `重要提醒 ${index + 1}`, description: item, status: '확인 필요' }))} />
            <RiskPanel title="风险记录" items={detail.riskLogs.map((item, index) => ({ id: index, title: `风险记录 ${index + 1}`, description: item, status: detail.riskLevel }))} />

            <section className="detail-section">
              <h3>备注</h3>
              <p>{detail.remarks || '暂无备注'}</p>
            </section>
          </>
        ) : <EmptyState title="暂无邮箱详情" description="请选择一个邮箱账号查看详细信息。" />}
      </DetailModal>

      <Modal
        open={accountModal.open}
        title={accountModal.editing ? '编辑邮箱账号' : '新增邮箱账号'}
        onClose={() => setAccountModal({ open: false, editing: null })}
        onConfirm={saveAccount}
        confirmText={accountModal.editing ? '保存邮箱' : '创建邮箱'}
        width="min(920px, 94vw)"
      >
        <div className="form-grid">
          <FormField label="邮箱编号">
            <input value={form.emailNo} placeholder="留空则自动生成" onChange={(event) => setForm({ ...form, emailNo: event.target.value })} />
          </FormField>
          <FormField label="邮箱地址" required error={errors.address}>
            <input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} />
          </FormField>
          <FormField label="绑定平台" required error={errors.platform}>
            <select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value })}>
              {platforms.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="绑定店铺">
            <select value={form.store} onChange={(event) => setForm({ ...form, store: event.target.value })}>
              <option value="">未绑定</option>
              {storeOptions.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="邮箱用途" required error={errors.purpose}>
            <select value={form.purpose} onChange={(event) => setForm({ ...form, purpose: event.target.value })}>
              {emailTypes.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="最近收件时间">
            <input value={form.lastReceivedAt} placeholder="2026-06-29 16:00" onChange={(event) => setForm({ ...form, lastReceivedAt: event.target.value })} />
          </FormField>
          <FormField label="邮箱状态" required error={errors.status}>
            <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {emailStatuses.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="风险等级" required error={errors.riskLevel}>
            <select value={form.riskLevel} onChange={(event) => setForm({ ...form, riskLevel: event.target.value })}>
              {riskLevels.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
        </div>
        <FormField label="备注">
          <textarea value={form.remarks} onChange={(event) => setForm({ ...form, remarks: event.target.value })} />
        </FormField>
      </Modal>
    </>
  );
}
