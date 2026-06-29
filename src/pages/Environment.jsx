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
const environmentTypes = ['Naver SmartStore 环境', 'Coupang Seller 环境', 'Gmarket/ESM 环境', '11街 Seller 环境', '옥션 Seller 环境', '申诉专用环境', '客服专用环境'];
const environmentStatuses = ['정상 운영', '대기중', '점검 필요', '위험 감지', '로그인 제한', '사용중지'];
const riskLevels = ['낮음', '보통', '높음', '긴급'];
const storeOptions = ['스마트스토어 뷰티샵', '韩国本土运动鞋店', 'Gmarket 럭셔리 골프관', '11街 韩系生活馆', 'K-Beauty 글로벌샵', '옥션 아웃도어 셀렉트', 'Coupang 키즈 패션랩'];
const deviceOptions = ['스마트스토어 운영 노트북', 'Coupang 审核专用环境', '韩国本土代理环境', '11街 客服手机'];
const emailOptions = ['naver.beauty.ops@storepilot.kr', 'coupang.review@storepilot.kr', 'gmarket.golf@storepilot.kr', '11st.life.cs@storepilot.kr'];

const columns = [
  { key: 'environmentNo', title: '环境编号', render: (value) => <strong>{value}</strong> },
  { key: 'name', title: '环境名称' },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '绑定店铺' },
  { key: 'deviceName', title: '绑定设备' },
  { key: 'emailAddress', title: '绑定邮箱' },
  { key: 'ipRegion', title: 'IP 地区' },
  { key: 'browserType', title: '浏览器类型' },
  { key: 'cookieStatus', title: 'Cookie 状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'lastLoginAt', title: '最近登录时间' },
  { key: 'status', title: '环境状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'riskLevel', title: '风险等级', render: (value) => <StatusBadge value={value} /> },
];

const initialForm = {
  environmentNo: '',
  name: '',
  environmentType: 'Naver SmartStore 环境',
  platform: 'Naver',
  store: '',
  deviceName: '',
  emailAddress: '',
  ipRegion: '',
  browserType: '',
  cookieStatus: '정상',
  lastLoginAt: '',
  status: '대기중',
  riskLevel: '보통',
  remarks: '',
};

export default function Environment() {
  const [query, setQuery] = useState({ keyword: '', platform: '', store: '', status: '', riskLevel: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [riskLogs, setRiskLogs] = useState([]);
  const [actionLogs, setActionLogs] = useState([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [environmentModal, setEnvironmentModal] = useState({ open: false, editing: null });
  const [bindModal, setBindModal] = useState({ open: false, environment: null, mode: 'device' });
  const [form, setForm] = useState(initialForm);
  const [bindValue, setBindValue] = useState('');
  const [errors, setErrors] = useState({});

  const load = async (nextQuery = query) => {
    setLoading(true);
    try {
      const response = await mockApi.getEnvironments(nextQuery);
      setResult(response);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query]);

  const openDetail = async (row) => {
    const [detailData, nextRiskLogs, nextActionLogs] = await Promise.all([
      mockApi.getEnvironmentDetail(row.id),
      mockApi.getEnvironmentRiskLogs(row.id),
      mockApi.getEnvironmentActionLogs(row.id),
    ]);
    setDetail(detailData);
    setRiskLogs(nextRiskLogs);
    setActionLogs(nextActionLogs);
    setDetailOpen(true);
  };

  const openCreateModal = () => {
    setForm(initialForm);
    setErrors({});
    setEnvironmentModal({ open: true, editing: null });
  };

  const openEditModal = (row) => {
    setForm({
      environmentNo: row.environmentNo,
      name: row.name,
      environmentType: row.environmentType,
      platform: row.platform,
      store: row.store === '未绑定' ? '' : row.store,
      deviceName: row.deviceName || '',
      emailAddress: row.emailAddress || '',
      ipRegion: row.ipRegion,
      browserType: row.browserType,
      cookieStatus: row.cookieStatus,
      lastLoginAt: row.lastLoginAt,
      status: row.status,
      riskLevel: row.riskLevel,
      remarks: row.remarks || '',
    });
    setErrors({});
    setEnvironmentModal({ open: true, editing: row });
  };

  const saveEnvironment = async () => {
    const nextErrors = {};
    ['name', 'environmentType', 'platform', 'ipRegion', 'browserType', 'cookieStatus', 'status', 'riskLevel'].forEach((key) => {
      if (!String(form[key] ?? '').trim()) nextErrors[key] = '该字段不能为空';
    });
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const payload = {
      environmentNo: form.environmentNo,
      name: form.name,
      environmentType: form.environmentType,
      platform: form.platform,
      store: form.store || '未绑定',
      deviceName: form.deviceName || '未绑定',
      emailAddress: form.emailAddress || '未绑定',
      ipRegion: form.ipRegion,
      browserType: form.browserType,
      cookieStatus: form.cookieStatus,
      lastLoginAt: form.lastLoginAt || '2026-06-29 16:00',
      status: form.status,
      riskLevel: form.riskLevel,
      remarks: form.remarks,
      proxyInfo: {
        ipAddress: environmentModal.editing?.proxyInfo?.ipAddress || '未配置',
        region: form.ipRegion,
        provider: environmentModal.editing?.proxyInfo?.provider || 'Mock Proxy',
        rotationPolicy: environmentModal.editing?.proxyInfo?.rotationPolicy || '固定策略',
      },
      browserInfo: {
        browser: form.browserType,
        fingerprint: environmentModal.editing?.browserInfo?.fingerprint || `ENV-${Date.now()}`,
        userAgent: form.browserType,
        language: 'ko-KR',
      },
    };

    if (environmentModal.editing) {
      await mockApi.updateEnvironment(environmentModal.editing.id, payload);
    } else {
      await mockApi.createEnvironment(payload);
    }

    setEnvironmentModal({ open: false, editing: null });
    await load();
  };

  const submitBind = async () => {
    if (!bindValue) {
      setErrors({ bindValue: '请选择绑定对象' });
      return;
    }

    if (bindModal.mode === 'device') {
      await mockApi.bindEnvironmentDevice(bindModal.environment.id, { deviceName: bindValue });
    } else {
      await mockApi.bindEnvironmentEmail(bindModal.environment.id, { emailAddress: bindValue });
    }

    setBindModal({ open: false, environment: null, mode: 'device' });
    setBindValue('');
    setErrors({});
    await load();
  };

  return (
    <>
      <PageHeader
        title="环境管理"
        description="管理多店铺登录环境、代理/IP、浏览器指纹和平台风险状态。"
        actions={<button className="button primary" onClick={openCreateModal}>新增环境</button>}
      />

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', platform: '', store: '', status: '', riskLevel: '', page: 1, pageSize: 5 };
            setDraftQuery(clean);
            setQuery(clean);
          }}
          placeholder="搜索环境编号、环境名、店铺、设备、邮箱或风险描述"
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
            <option value="">全部环境状态</option>
            {environmentStatuses.map((item) => <option key={item}>{item}</option>)}
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
              <button onClick={() => {
                setBindModal({ open: true, environment: row, mode: 'device' });
                setBindValue('');
                setErrors({});
              }}>绑定设备</button>
              <button onClick={() => {
                setBindModal({ open: true, environment: row, mode: 'email' });
                setBindValue('');
                setErrors({});
              }}>绑定邮箱</button>
              <button onClick={() => mockApi.updateEnvironmentStatus(row.id, '위험 감지').then(() => load())}>标记风险</button>
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </section>

      <DetailModal open={detailOpen} title={detail ? `环境详情 · ${detail.environmentNo}` : '环境详情'} onClose={() => setDetailOpen(false)} width="min(980px, 94vw)">
        {detail ? (
          <>
            <section className="detail-section">
              <h3>基础环境信息</h3>
              <InfoGrid items={[
                { label: '环境名称', value: detail.name },
                { label: '环境类型', value: detail.environmentType },
                { label: '平台', value: detail.platform },
                { label: '绑定店铺', value: detail.store },
                { label: '环境状态', value: <StatusBadge value={detail.status} /> },
                { label: '风险等级', value: <StatusBadge value={detail.riskLevel} /> },
              ]} />
            </section>

            <section className="detail-section">
              <h3>绑定信息</h3>
              <InfoGrid items={[
                { label: '绑定设备', value: detail.deviceName || '未绑定' },
                { label: '绑定邮箱', value: detail.emailAddress || '未绑定' },
                { label: 'IP 地区', value: detail.ipRegion },
                { label: 'Cookie 状态', value: <StatusBadge value={detail.cookieStatus} /> },
              ]} />
            </section>

            <section className="detail-section">
              <h3>IP / 代理信息</h3>
              <InfoGrid items={[
                { label: 'IP 地址', value: detail.proxyInfo.ipAddress },
                { label: '代理地区', value: detail.proxyInfo.region },
                { label: '服务商', value: detail.proxyInfo.provider },
                { label: '切换策略', value: detail.proxyInfo.rotationPolicy },
              ]} />
            </section>

            <section className="detail-section">
              <h3>浏览器环境信息</h3>
              <InfoGrid items={[
                { label: '浏览器', value: detail.browserInfo.browser },
                { label: '指纹', value: detail.browserInfo.fingerprint },
                { label: 'User-Agent', value: detail.browserInfo.userAgent },
                { label: '语言', value: detail.browserInfo.language },
              ]} />
            </section>

            <section className="detail-section">
              <h3>登录记录</h3>
              <LogList items={detail.loginLogs} emptyText="暂无登录记录" />
            </section>

            <RiskPanel title="风险检测记录" items={riskLogs} />

            <section className="detail-section">
              <h3>环境操作记录</h3>
              <LogList items={actionLogs} emptyText="暂无操作记录" />
            </section>

            <section className="detail-section">
              <h3>备注</h3>
              <p>{detail.remarks || '暂无备注'}</p>
            </section>
          </>
        ) : <EmptyState title="暂无环境详情" description="请选择一条环境记录查看详细信息。" />}
      </DetailModal>

      <Modal
        open={environmentModal.open}
        title={environmentModal.editing ? '编辑环境' : '新增环境'}
        onClose={() => setEnvironmentModal({ open: false, editing: null })}
        onConfirm={saveEnvironment}
        confirmText={environmentModal.editing ? '保存环境' : '创建环境'}
        width="min(980px, 94vw)"
      >
        <div className="form-grid">
          <FormField label="环境编号">
            <input value={form.environmentNo} placeholder="留空则自动生成" onChange={(event) => setForm({ ...form, environmentNo: event.target.value })} />
          </FormField>
          <FormField label="环境名称" required error={errors.name}>
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </FormField>
          <FormField label="环境类型" required error={errors.environmentType}>
            <select value={form.environmentType} onChange={(event) => setForm({ ...form, environmentType: event.target.value })}>
              {environmentTypes.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="平台" required error={errors.platform}>
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
          <FormField label="绑定设备">
            <select value={form.deviceName} onChange={(event) => setForm({ ...form, deviceName: event.target.value })}>
              <option value="">未绑定</option>
              {deviceOptions.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="绑定邮箱">
            <select value={form.emailAddress} onChange={(event) => setForm({ ...form, emailAddress: event.target.value })}>
              <option value="">未绑定</option>
              {emailOptions.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="IP 地区" required error={errors.ipRegion}>
            <input value={form.ipRegion} onChange={(event) => setForm({ ...form, ipRegion: event.target.value })} />
          </FormField>
          <FormField label="浏览器类型" required error={errors.browserType}>
            <input value={form.browserType} onChange={(event) => setForm({ ...form, browserType: event.target.value })} />
          </FormField>
          <FormField label="Cookie 状态" required error={errors.cookieStatus}>
            <select value={form.cookieStatus} onChange={(event) => setForm({ ...form, cookieStatus: event.target.value })}>
              {['정상', '확인 필요', '위험', '쿠키 만료'].map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="最近登录时间">
            <input value={form.lastLoginAt} placeholder="2026-06-29 16:00" onChange={(event) => setForm({ ...form, lastLoginAt: event.target.value })} />
          </FormField>
          <FormField label="环境状态" required error={errors.status}>
            <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {environmentStatuses.map((item) => <option key={item}>{item}</option>)}
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

      <Modal
        open={bindModal.open}
        title={bindModal.environment ? `${bindModal.mode === 'device' ? '绑定设备' : '绑定邮箱'} · ${bindModal.environment.name}` : '绑定'}
        onClose={() => setBindModal({ open: false, environment: null, mode: 'device' })}
        onConfirm={submitBind}
        confirmText={bindModal.mode === 'device' ? '绑定设备' : '绑定邮箱'}
      >
        <FormField label={bindModal.mode === 'device' ? '选择设备' : '选择邮箱'} required error={errors.bindValue}>
          <select value={bindValue} onChange={(event) => setBindValue(event.target.value)}>
            <option value="">请选择</option>
            {(bindModal.mode === 'device' ? deviceOptions : emailOptions).map((item) => <option key={item}>{item}</option>)}
          </select>
        </FormField>
      </Modal>
    </>
  );
}
