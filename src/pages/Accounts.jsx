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

const platforms = ['Naver', 'Coupang', 'Gmarket', '11街', '옥션', 'ALL'];
const accountTypes = ['店铺主账号', '店铺子账号', '客服账号', '运营账号', '申诉账号', '财务账号', '管理员账号'];
const roles = ['Super Admin', '운영 관리자', '고객센터 담당자', '상품 관리자', '주문 관리자', '정산 담당자', '申诉处理员', '只读查看'];
const statuses = ['정상', '사용중', '대기중', '인증 필요', '로그인 제한', '사용중지', '위험'];
const riskLevels = ['낮음', '보통', '높음', '긴급'];
const storeOptions = ['스마트스토어 뷰티샵', '韩国本土运动鞋店', 'Gmarket 럭셔리 골프관', '11街 韩系生活馆', 'K-Beauty 글로벌샵', '옥션 아웃도어 셀렉트', 'Coupang 키즈 패션랩', '全部店铺'];
const deviceOptions = ['스마트스토어 운영 노트북', 'Coupang 审核专用环境', '韩国本土代理环境', '11街 客服手机', '管理后台工作站'];
const emailOptions = ['naver.beauty.ops@storepilot.kr', 'coupang.review@storepilot.kr', 'gmarket.golf@storepilot.kr', '11st.life.cs@storepilot.kr', 'admin@storepilot.kr'];
const environmentOptions = ['Naver Beauty 主运营环境', 'Coupang Seller 风控审核环境', '11街 客服专用工作环境', 'Gmarket/ESM 主环境', '系统管理控制台'];

const columns = [
  { key: 'accountNo', title: '账号编号', render: (value) => <strong>{value}</strong> },
  { key: 'name', title: '账号名称' },
  { key: 'loginId', title: '登录 ID' },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '绑定店铺' },
  { key: 'accountType', title: '账号类型' },
  { key: 'role', title: '权限角色' },
  { key: 'email', title: '绑定邮箱' },
  { key: 'device', title: '绑定设备' },
  { key: 'environment', title: '绑定环境' },
  { key: 'lastLoginAt', title: '最近登录时间' },
  { key: 'status', title: '账号状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'riskLevel', title: '风险等级', render: (value) => <StatusBadge value={value} /> },
];

const initialForm = {
  accountNo: '',
  name: '',
  loginId: '',
  platform: 'Naver',
  store: '',
  accountType: '运营账号',
  role: '운영 관리자',
  email: '',
  device: '',
  environment: '',
  lastLoginAt: '',
  status: '대기중',
  riskLevel: '보통',
  permissionNote: '',
  remarks: '',
};

export default function Accounts() {
  const [query, setQuery] = useState({ keyword: '', platform: '', store: '', status: '', role: '', riskLevel: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [loginLogs, setLoginLogs] = useState([]);
  const [riskLogs, setRiskLogs] = useState([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [accountModal, setAccountModal] = useState({ open: false, editing: null });
  const [bindModal, setBindModal] = useState({ open: false, account: null, mode: 'store' });
  const [bindValue, setBindValue] = useState('');
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});

  const load = async (nextQuery = query) => {
    setLoading(true);
    try {
      setResult(await mockApi.getAccounts(nextQuery));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query]);

  const openDetail = async (row) => {
    const [detailData, accountLoginLogs, accountRiskLogs] = await Promise.all([
      mockApi.getAccountDetail(row.id),
      mockApi.getAccountLoginLogs(row.id),
      mockApi.getAccountRiskLogs(row.id),
    ]);
    setDetail(detailData);
    setLoginLogs(accountLoginLogs);
    setRiskLogs(accountRiskLogs);
    setDetailOpen(true);
  };

  const openCreateModal = () => {
    setForm(initialForm);
    setErrors({});
    setAccountModal({ open: true, editing: null });
  };

  const openEditModal = (row) => {
    setForm({
      accountNo: row.accountNo,
      name: row.name,
      loginId: row.loginId,
      platform: row.platform,
      store: row.store === '未绑定' ? '' : row.store,
      accountType: row.accountType,
      role: row.role,
      email: row.email || '',
      device: row.device || '',
      environment: row.environment || '',
      lastLoginAt: row.lastLoginAt,
      status: row.status,
      riskLevel: row.riskLevel,
      permissionNote: row.permissionNote || '',
      remarks: row.remarks || '',
    });
    setErrors({});
    setAccountModal({ open: true, editing: row });
  };

  const saveAccount = async () => {
    const nextErrors = {};
    ['name', 'loginId', 'platform', 'accountType', 'role', 'status', 'riskLevel'].forEach((key) => {
      if (!String(form[key] ?? '').trim()) nextErrors[key] = '该字段不能为空';
    });
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const payload = {
      accountNo: form.accountNo,
      name: form.name,
      loginId: form.loginId,
      platform: form.platform,
      store: form.store || '未绑定',
      accountType: form.accountType,
      role: form.role,
      email: form.email || '未绑定',
      device: form.device || '未绑定',
      environment: form.environment || '未绑定',
      lastLoginAt: form.lastLoginAt || '2026-06-29 16:30',
      status: form.status,
      riskLevel: form.riskLevel,
      permissionNote: form.permissionNote,
      remarks: form.remarks,
    };

    if (accountModal.editing) {
      await mockApi.updateAccount(accountModal.editing.id, payload);
    } else {
      await mockApi.createAccount(payload);
    }

    setAccountModal({ open: false, editing: null });
    await load();
  };

  const updateStatus = async (row, status) => {
    await mockApi.updateAccountStatus(row.id, status);
    await load();
  };

  const submitBind = async () => {
    if (!bindValue) {
      setErrors({ bindValue: '请选择绑定对象' });
      return;
    }
    if (bindModal.mode === 'store') await mockApi.bindAccountStore(bindModal.account.id, { store: bindValue });
    if (bindModal.mode === 'device') await mockApi.bindAccountDevice(bindModal.account.id, { device: bindValue });
    if (bindModal.mode === 'email') await mockApi.bindAccountEmail(bindModal.account.id, { email: bindValue });
    if (bindModal.mode === 'environment') await mockApi.bindAccountEnvironment(bindModal.account.id, { environment: bindValue });
    setBindModal({ open: false, account: null, mode: 'store' });
    setBindValue('');
    setErrors({});
    await load();
  };

  const bindOptionsMap = {
    store: storeOptions,
    device: deviceOptions,
    email: emailOptions,
    environment: environmentOptions,
  };

  return (
    <>
      <PageHeader
        title="账号管理"
        description="统一管理平台账号、权限角色、绑定对象和风险记录。"
        actions={<button className="button primary" onClick={openCreateModal}>新增账号</button>}
      />

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', platform: '', store: '', status: '', role: '', riskLevel: '', page: 1, pageSize: 5 };
            setDraftQuery(clean);
            setQuery(clean);
          }}
          placeholder="搜索账号名称、登录 ID、平台、店铺或权限说明"
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
            <option value="">全部账号状态</option>
            {statuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.role} onChange={(event) => setDraftQuery({ ...draftQuery, role: event.target.value })}>
            <option value="">全部权限角色</option>
            {roles.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.riskLevel} onChange={(event) => setDraftQuery({ ...draftQuery, riskLevel: event.target.value })}>
            <option value="">全部风险等级</option>
            {riskLevels.map((item) => <option key={item}>{item}</option>)}
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
              <button onClick={() => openEditModal(row)}>编辑</button>
              <button onClick={() => updateStatus(row, row.status === '사용중지' ? '사용중' : '사용중지')}>{row.status === '사용중지' ? '启用' : '停用'}</button>
              <button onClick={() => { setBindModal({ open: true, account: row, mode: 'store' }); setBindValue(''); setErrors({}); }}>绑定店铺</button>
              <button onClick={() => { setBindModal({ open: true, account: row, mode: 'device' }); setBindValue(''); setErrors({}); }}>绑定设备</button>
              <button onClick={() => { setBindModal({ open: true, account: row, mode: 'email' }); setBindValue(''); setErrors({}); }}>绑定邮箱</button>
              <button onClick={() => { setBindModal({ open: true, account: row, mode: 'environment' }); setBindValue(''); setErrors({}); }}>绑定环境</button>
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </section>

      <DetailModal open={detailOpen} title={detail ? `账号详情 · ${detail.accountNo}` : '账号详情'} onClose={() => setDetailOpen(false)} width="min(980px, 94vw)">
        {detail ? (
          <>
            <section className="detail-section">
              <h3>基础账号信息</h3>
              <InfoGrid items={[
                { label: '账号名称', value: detail.name },
                { label: '登录 ID', value: detail.loginId },
                { label: '平台', value: detail.platform },
                { label: '账号类型', value: detail.accountType },
                { label: '权限角色', value: detail.role },
                { label: '账号状态', value: <StatusBadge value={detail.status} /> },
                { label: '风险等级', value: <StatusBadge value={detail.riskLevel} /> },
                { label: '最近登录时间', value: detail.lastLoginAt },
              ]} />
            </section>
            <section className="detail-section">
              <h3>绑定信息</h3>
              <InfoGrid items={[
                { label: '绑定店铺', value: detail.store },
                { label: '绑定邮箱', value: detail.email || '未绑定' },
                { label: '绑定设备', value: detail.device || '未绑定' },
                { label: '绑定环境', value: detail.environment || '未绑定' },
              ]} />
            </section>
            <section className="detail-section">
              <h3>权限角色说明</h3>
              <p>{detail.permissionNote || '暂无权限补充说明'}</p>
            </section>
            <section className="detail-section">
              <h3>最近登录记录</h3>
              <LogList items={loginLogs} emptyText="暂无登录记录" />
            </section>
            <RiskPanel title="风险记录" items={riskLogs} />
            <section className="detail-section">
              <h3>备注</h3>
              <p>{detail.remarks || '暂无备注'}</p>
            </section>
          </>
        ) : <EmptyState title="暂无账号详情" description="请选择一条账号记录查看详情。" />}
      </DetailModal>

      <Modal
        open={accountModal.open}
        title={accountModal.editing ? '编辑账号' : '新增账号'}
        onClose={() => setAccountModal({ open: false, editing: null })}
        onConfirm={saveAccount}
        confirmText={accountModal.editing ? '保存账号' : '创建账号'}
        width="min(980px, 94vw)"
      >
        <div className="form-grid">
          <FormField label="账号编号">
            <input value={form.accountNo} placeholder="留空则自动生成" onChange={(event) => setForm({ ...form, accountNo: event.target.value })} />
          </FormField>
          <FormField label="账号名称" required error={errors.name}>
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </FormField>
          <FormField label="登录 ID" required error={errors.loginId}>
            <input value={form.loginId} onChange={(event) => setForm({ ...form, loginId: event.target.value })} />
          </FormField>
          <FormField label="平台" required error={errors.platform}>
            <select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value })}>{platforms.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="绑定店铺">
            <select value={form.store} onChange={(event) => setForm({ ...form, store: event.target.value })}><option value="">未绑定</option>{storeOptions.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="账号类型" required error={errors.accountType}>
            <select value={form.accountType} onChange={(event) => setForm({ ...form, accountType: event.target.value })}>{accountTypes.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="权限角色" required error={errors.role}>
            <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>{roles.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="绑定邮箱">
            <select value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })}><option value="">未绑定</option>{emailOptions.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="绑定设备">
            <select value={form.device} onChange={(event) => setForm({ ...form, device: event.target.value })}><option value="">未绑定</option>{deviceOptions.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="绑定环境">
            <select value={form.environment} onChange={(event) => setForm({ ...form, environment: event.target.value })}><option value="">未绑定</option>{environmentOptions.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="最近登录时间">
            <input value={form.lastLoginAt} placeholder="2026-06-29 16:30" onChange={(event) => setForm({ ...form, lastLoginAt: event.target.value })} />
          </FormField>
          <FormField label="账号状态" required error={errors.status}>
            <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>{statuses.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
          <FormField label="风险等级" required error={errors.riskLevel}>
            <select value={form.riskLevel} onChange={(event) => setForm({ ...form, riskLevel: event.target.value })}>{riskLevels.map((item) => <option key={item}>{item}</option>)}</select>
          </FormField>
        </div>
        <FormField label="权限说明">
          <textarea value={form.permissionNote} onChange={(event) => setForm({ ...form, permissionNote: event.target.value })} />
        </FormField>
        <FormField label="备注">
          <textarea value={form.remarks} onChange={(event) => setForm({ ...form, remarks: event.target.value })} />
        </FormField>
      </Modal>

      <Modal
        open={bindModal.open}
        title={bindModal.account ? `绑定${bindModal.mode === 'store' ? '店铺' : bindModal.mode === 'device' ? '设备' : bindModal.mode === 'email' ? '邮箱' : '环境'} · ${bindModal.account.name}` : '绑定'}
        onClose={() => setBindModal({ open: false, account: null, mode: 'store' })}
        onConfirm={submitBind}
        confirmText="保存绑定"
      >
        <FormField label="选择绑定对象" required error={errors.bindValue}>
          <select value={bindValue} onChange={(event) => setBindValue(event.target.value)}>
            <option value="">请选择</option>
            {bindOptionsMap[bindModal.mode].map((item) => <option key={item}>{item}</option>)}
          </select>
        </FormField>
      </Modal>
    </>
  );
}
