import { useEffect, useMemo, useState } from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource, getDangerousActionState } from '../utils/coreErpContract';

const platformOptions = ['Naver', 'Coupang', 'Gmarket'];
const statusOptions = ['正常', '需检查', '需授权', '收信失败'];

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function text(value, fallback = '-') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function statusLabel(value) {
  const normalized = comparable(value);
  if (['정상', 'active', 'normal', '正常'].includes(normalized)) return '正常';
  if (['확인 필요', 'check', '需检查'].includes(normalized)) return '需检查';
  if (['인증 필요', 'auth_required', '需授权'].includes(normalized)) return '需授权';
  if (['수신 실패', 'failed', '收信失败'].includes(normalized)) return '收信失败';
  return value ? '需检查' : '需检查';
}

function normalizeAccount(row = {}) {
  const sourceInfo = classifyCoreDataSource(row);
  return {
    ...row,
    emailNo: row.emailNo || row.email_no || `EM-${row.id}`,
    address: text(row.address || row.email || row.account),
    platform: text(row.platform || row.rawPlatform),
    store: text(row.store || row.storeName || row.store_name),
    purpose: text(row.purpose || row.emailType || row.type, '平台通知'),
    statusLabel: statusLabel(row.status),
    unreadCount: Number(row.unreadCount || row.unread_count || 0),
    importantCount: Number(row.importantCount || row.important_count || 0),
    lastReceivedAt: row.lastReceivedAt || row.updatedAt || '',
    sourceInfo,
  };
}

function normalizeMail(row = {}) {
  const sourceInfo = classifyCoreDataSource(row);
  return {
    ...row,
    id: row.id || `${row.address}-${row.title}`,
    title: text(row.title || row.subject, '重要邮件'),
    address: text(row.address || row.email || row.account),
    platform: text(row.platform || row.rawPlatform),
    store: text(row.store || row.storeName || row.store_name),
    sender: text(row.sender, '发件人未记录'),
    receivedAt: row.receivedAt || row.lastReceivedAt || '',
    handledStatus: text(row.handledStatus || row.status, '未处理'),
    summary: text(row.summary || row.content, '暂无摘要'),
    sourceLabel: sourceInfo.label,
  };
}

function matches(row, query = {}) {
  const keyword = comparable(query.keyword);
  const haystack = [row.address, row.platform, row.store, row.purpose, row.statusLabel].map(comparable).join(' ');
  if (keyword && !haystack.includes(keyword)) return false;
  if (query.platform && comparable(row.platform) !== comparable(query.platform)) return false;
  if (query.status && row.statusLabel !== query.status) return false;
  return true;
}

const accountColumns = [
  { key: 'emailNo', title: '账号编号', render: (value) => <strong>{value}</strong> },
  { key: 'address', title: '邮箱账号' },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'purpose', title: '用途' },
  { key: 'statusLabel', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'unreadCount', title: '未读' },
  { key: 'importantCount', title: '重要邮件' },
  { key: 'lastReceivedAt', title: '最近收信' },
  { key: 'sourceLabel', title: '数据来源', render: (_value, row) => row.sourceInfo.label },
];

const mailColumns = [
  { key: 'title', title: '邮件标题', render: (value) => <strong>{value}</strong> },
  { key: 'address', title: '邮箱账号' },
  { key: 'platform', title: '平台' },
  { key: 'sender', title: '发件人' },
  { key: 'receivedAt', title: '收件时间' },
  { key: 'handledStatus', title: '处理状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'summary', title: '摘要' },
  { key: 'sourceLabel', title: '数据来源' },
];

export default function Emails() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', platform: '', status: '' });
  const [draft, setDraft] = useState(query);
  const [accounts, setAccounts] = useState([]);
  const [importantMails, setImportantMails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({
    address: '',
    platform: 'Naver',
    store: '',
    purpose: '平台通知',
    authCodeInput: '',
    remarks: '',
  });
  const [saveError, setSaveError] = useState('');

  const load = async () => {
    if (isBackendSource && storeLoading) return;
    setLoading(true);
    setError('');
    try {
      if (isBackendSource && storeError) throw new Error(storeError);
      const params = { page: 1, pageSize: 100 };
      if (isBackendSource && selectedStoreId) params.storeId = selectedStoreId;
      const [accountResult, mailResult] = await Promise.all([
        dataProvider.getEmailAccounts(params),
        dataProvider.getImportantEmails({ ...params, pageSize: 20 }),
      ]);
      const normalizedAccounts = (accountResult.data || accountResult.items || []).map(normalizeAccount).filter((item) => matches(item, query));
      const normalizedMails = (mailResult.data || mailResult.items || []).map(normalizeMail);
      setAccounts(normalizedAccounts);
      setImportantMails(normalizedMails);
    } catch (requestError) {
      setAccounts([]);
      setImportantMails([]);
      setError(requestError.message || '邮箱数据加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query, selectedStoreId, storeLoading, storeError]);

  const summary = useMemo(() => ({
    accounts: accounts.length,
    important: importantMails.length,
    authRequired: accounts.filter((item) => item.statusLabel === '需授权').length,
    failed: accounts.filter((item) => item.statusLabel === '收信失败').length,
  }), [accounts, importantMails]);

  const dangerousState = getDangerousActionState('email_auto_send');

  const saveAccount = async () => {
    if (!form.address.trim()) {
      setSaveError('请填写邮箱账号');
      return;
    }
    if (!form.authCodeInput.trim()) {
      setSaveError('请填写邮箱授权码或应用专用密码');
      return;
    }
    setSaveError('');
    try {
      await dataProvider.createEmailAccount({
        ...form,
        status: '需检查',
        recentEmails: [],
        importantAlerts: [],
        riskLogs: ['新邮箱账号已保存，需人工确认收信状态。'],
      });
      setModalOpen(false);
      setForm({ address: '', platform: 'Naver', store: '', purpose: '平台通知', authCodeInput: '', remarks: '' });
      await load();
    } catch (requestError) {
      setSaveError(requestError.message || '邮箱账号保存失败');
    }
  };

  const search = () => setQuery({ ...draft });
  const reset = () => {
    const clean = { keyword: '', platform: '', status: '' };
    setDraft(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="邮箱中心"
        description="维护邮箱账号和重要邮件入口，不做邮箱深度 AI 识别，也不自动发送邮件。"
        actions={<button type="button" className="button primary" onClick={() => setModalOpen(true)}>新增邮箱账号</button>}
      />

      <div className="summary-grid">
        <SummaryCard title="邮箱账号" value={summary.accounts} note="系统已保存账号" tone="info" />
        <SummaryCard title="重要邮件" value={summary.important} note="需要人工查看" tone={summary.important ? 'warning' : 'success'} />
        <SummaryCard title="需授权" value={summary.authRequired} note="检查授权码" tone={summary.authRequired ? 'warning' : 'success'} />
        <SummaryCard title="收信失败" value={summary.failed} note="检查服务商设置" tone={summary.failed ? 'danger' : 'success'} />
      </div>

      <section className="content-card">
        <div className="business-capability-grid compact">
          <article className="business-capability-card info">
            <div className="business-capability-head"><strong>授权码说明</strong><span>必填</span></div>
            <p>不是邮箱登录密码，请填写邮箱服务商提供的授权码或应用专用密码。</p>
          </article>
          <article className="business-capability-card warning">
            <div className="business-capability-head"><strong>邮箱深度 AI 识别</strong><span>暂未开放</span></div>
            <p>当前只展示账号和重要邮件入口，不做自动识别、自动分类或自动回复。</p>
          </article>
          <article className="business-capability-card muted">
            <div className="business-capability-head"><strong>自动发送邮件</strong><span>{dangerousState.label}</span></div>
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
          placeholder="搜索邮箱账号、平台、店铺或用途"
        >
          <select value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {error ? <EmptyState title="邮箱数据加载失败" description={error} /> : null}
        {!error && !loading && !accounts.length ? (
          <EmptyState
            title="当前没有邮箱账号"
            description="可以新增邮箱账号，并填写邮箱服务商提供的授权码或应用专用密码。"
            actions={<button type="button" className="button primary" onClick={() => setModalOpen(true)}>新增邮箱账号</button>}
          />
        ) : <DataTable columns={accountColumns} rows={accounts} loading={loading} />}
      </section>

      <section className="content-card">
        <div className="card-title">
          <div>
            <h2>重要邮件区域</h2>
            <p>当前只做重要邮件入口和人工处理提醒，不做邮箱深度 AI 识别。</p>
          </div>
        </div>
        {!loading && !importantMails.length ? (
          <EmptyState title="暂无重要邮件" description="连接邮箱并收取到重要邮件后，会在这里显示本地保存记录。" />
        ) : (
          <DataTable columns={mailColumns} rows={importantMails} loading={loading} />
        )}
      </section>

      <Modal
        open={modalOpen}
        title="新增邮箱账号"
        onClose={() => setModalOpen(false)}
        onConfirm={saveAccount}
        confirmText="保存邮箱账号"
        width="min(760px, 94vw)"
      >
        {saveError ? <div className="form-error">{saveError}</div> : null}
        <div className="form-grid">
          <FormField label="邮箱账号" required>
            <input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} placeholder="name@example.com" />
          </FormField>
          <FormField label="平台">
            <select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value })}>
              {platformOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="关联店铺">
            <input value={form.store} onChange={(event) => setForm({ ...form, store: event.target.value })} placeholder="用于识别通知归属，可留空后补" />
          </FormField>
          <FormField label="用途">
            <input value={form.purpose} onChange={(event) => setForm({ ...form, purpose: event.target.value })} />
          </FormField>
          <FormField label="邮箱授权码 / 应用专用密码" required>
            <input
              type="password"
              value={form.authCodeInput}
              onChange={(event) => setForm({ ...form, authCodeInput: event.target.value })}
              placeholder="不是邮箱登录密码"
            />
            <small className="form-help">不是邮箱登录密码，请填写邮箱服务商提供的授权码或应用专用密码。保存后不会明文回显。</small>
          </FormField>
          <FormField label="备注">
            <input value={form.remarks} onChange={(event) => setForm({ ...form, remarks: event.target.value })} placeholder="例如：平台通知主邮箱" />
          </FormField>
        </div>
      </Modal>
    </>
  );
}
