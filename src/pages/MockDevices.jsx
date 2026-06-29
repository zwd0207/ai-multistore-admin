import { useEffect, useState } from 'react';
import BindingList from '../components/common/BindingList';
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
const deviceTypes = ['PC', 'Laptop', 'Mobile', 'Tablet', 'VPS', 'Proxy Environment'];
const deviceStatuses = ['정상', '사용중', '대기중', '점검 필요', '위험', '차단됨'];
const riskLevels = ['낮음', '보통', '높음', '긴급'];
const storeOptions = ['스마트스토어 뷰티샵', '韩国本土运动鞋店', 'Gmarket 럭셔리 골프관', '11街 韩系生活馆', 'K-Beauty 글로벌샵', '옥션 아웃도어 셀렉트', 'Coupang 키즈 패션랩'];

const columns = [
  { key: 'deviceNo', title: '设备编号', render: (value) => <strong>{value}</strong> },
  { key: 'name', title: '设备名称' },
  { key: 'deviceType', title: '设备类型' },
  { key: 'platform', title: '绑定平台' },
  { key: 'store', title: '绑定店铺' },
  { key: 'loginAccountCount', title: '登录账号数' },
  { key: 'ipAddress', title: 'IP 地址' },
  { key: 'proxyRegion', title: '代理地区' },
  { key: 'lastLoginAt', title: '最近登录时间' },
  { key: 'status', title: '设备状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'riskLevel', title: '风险等级', render: (value) => <StatusBadge value={value} /> },
];

const initialForm = {
  deviceNo: '',
  name: '',
  deviceType: 'Laptop',
  platform: 'Naver',
  store: '',
  loginAccountCount: 1,
  ipAddress: '',
  proxyRegion: '',
  lastLoginAt: '',
  status: '대기중',
  riskLevel: '보통',
  browser: '',
  os: '',
  notes: '',
};

export default function Devices() {
  const [query, setQuery] = useState({ keyword: '', platform: '', store: '', status: '', deviceType: '', riskLevel: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [deviceLogs, setDeviceLogs] = useState([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [deviceModal, setDeviceModal] = useState({ open: false, editing: null });
  const [bindModal, setBindModal] = useState({ open: false, device: null });
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [bindStore, setBindStore] = useState('');

  const load = async (nextQuery = query) => {
    setLoading(true);
    try {
      const response = await mockApi.getDevices(nextQuery);
      setResult(response);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query]);

  const openDetail = async (row) => {
    const [detailData, logs] = await Promise.all([mockApi.getDeviceDetail(row.id), mockApi.getDeviceLogs(row.id)]);
    setDetail(detailData);
    setDeviceLogs(logs);
    setDetailOpen(true);
  };

  const openCreateModal = () => {
    setForm(initialForm);
    setErrors({});
    setDeviceModal({ open: true, editing: null });
  };

  const openEditModal = (row) => {
    setForm({
      deviceNo: row.deviceNo,
      name: row.name,
      deviceType: row.deviceType,
      platform: row.platform,
      store: row.store === '未绑定' ? '' : row.store,
      loginAccountCount: row.loginAccountCount,
      ipAddress: row.ipAddress,
      proxyRegion: row.proxyRegion,
      lastLoginAt: row.lastLoginAt,
      status: row.status,
      riskLevel: row.riskLevel,
      browser: row.browserEnv?.browser || '',
      os: row.browserEnv?.os || '',
      notes: row.remarks || '',
    });
    setErrors({});
    setDeviceModal({ open: true, editing: row });
  };

  const saveDevice = async () => {
    const nextErrors = {};
    ['name', 'deviceType', 'platform', 'ipAddress', 'proxyRegion', 'status', 'riskLevel'].forEach((key) => {
      if (!String(form[key] ?? '').trim()) nextErrors[key] = '该字段不能为空';
    });

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const payload = {
      deviceNo: form.deviceNo,
      name: form.name,
      deviceType: form.deviceType,
      platform: form.platform,
      store: form.store || '未绑定',
      loginAccountCount: Number(form.loginAccountCount || 0),
      ipAddress: form.ipAddress,
      proxyRegion: form.proxyRegion,
      lastLoginAt: form.lastLoginAt || '2026-06-29 16:00',
      status: form.status,
      riskLevel: form.riskLevel,
      remarks: form.notes,
      browserEnv: {
        browser: form.browser || 'Chrome 126',
        os: form.os || 'Windows 11',
        fingerprint: deviceModal.editing?.browserEnv?.fingerprint || `DEV-${Date.now()}`,
        timezone: 'Asia/Seoul',
        language: 'ko-KR',
      },
    };

    if (deviceModal.editing) {
      await mockApi.updateDevice(deviceModal.editing.id, payload);
    } else {
      await mockApi.createDevice(payload);
    }

    setDeviceModal({ open: false, editing: null });
    await load();
  };

  const markAbnormal = async (row) => {
    await mockApi.updateDeviceStatus(row.id, '위험');
    await mockApi.updateDevice(row.id, { riskLevel: '긴급' });
    await load();
  };

  const submitBindStore = async () => {
    if (!bindStore) {
      setErrors({ bindStore: '请选择要绑定的店铺' });
      return;
    }
    await mockApi.bindDeviceStore(bindModal.device.id, { name: bindStore, platform: bindModal.device.platform });
    setBindModal({ open: false, device: null });
    setBindStore('');
    setErrors({});
    await load();
  };

  const unbindStore = async (row) => {
    const target = row.boundStores?.[0];
    if (!target) return;
    await mockApi.unbindDeviceStore(row.id, target.id || target.name);
    await load();
  };

  return (
    <>
      <PageHeader
        title="设备管理"
        description="统一管理多账号运营设备、代理环境和风险状态。"
        actions={<button className="button primary" onClick={openCreateModal}>新增设备</button>}
      />

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', platform: '', store: '', status: '', deviceType: '', riskLevel: '', page: 1, pageSize: 5 };
            setDraftQuery(clean);
            setQuery(clean);
          }}
          placeholder="搜索设备编号、设备名、IP、代理地区或风险提示"
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
            <option value="">全部设备状态</option>
            {deviceStatuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.deviceType} onChange={(event) => setDraftQuery({ ...draftQuery, deviceType: event.target.value })}>
            <option value="">全部设备类型</option>
            {deviceTypes.map((item) => <option key={item}>{item}</option>)}
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
                setBindModal({ open: true, device: row });
                setBindStore('');
                setErrors({});
              }}>绑定店铺</button>
              <button onClick={() => unbindStore(row)}>解绑店铺</button>
              <button onClick={() => markAbnormal(row)}>标记异常</button>
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </section>

      <DetailModal open={detailOpen} title={detail ? `设备详情 · ${detail.deviceNo}` : '设备详情'} onClose={() => setDetailOpen(false)}>
        {detail ? (
          <>
            <section className="detail-section">
              <h3>基础设备信息</h3>
              <InfoGrid items={[
                { label: '设备名称', value: detail.name },
                { label: '设备类型', value: detail.deviceType },
                { label: '绑定平台', value: detail.platform },
                { label: '设备状态', value: <StatusBadge value={detail.status} /> },
                { label: '风险等级', value: <StatusBadge value={detail.riskLevel} /> },
                { label: '最近登录时间', value: detail.lastLoginAt },
              ]} />
            </section>

            <BindingList title="绑定店铺信息" items={detail.boundStores} fields={[{ key: 'name', label: '店铺' }, { key: 'platform', label: '平台' }]} />
            <BindingList title="绑定账号信息" items={detail.boundAccounts} fields={[{ key: 'account', label: '账号' }, { key: 'platform', label: '平台' }, { key: 'role', label: '角色' }]} />

            <section className="detail-section">
              <h3>IP / 代理信息</h3>
              <InfoGrid items={[
                { label: 'IP 地址', value: detail.proxyInfo.ipAddress },
                { label: '代理地区', value: detail.proxyInfo.region },
                { label: '代理服务商', value: detail.proxyInfo.provider },
                { label: '切换策略', value: detail.proxyInfo.rotationPolicy },
              ]} />
            </section>

            <section className="detail-section">
              <h3>浏览器环境信息</h3>
              <InfoGrid items={[
                { label: '浏览器', value: detail.browserEnv.browser },
                { label: '系统', value: detail.browserEnv.os },
                { label: '指纹标识', value: detail.browserEnv.fingerprint },
                { label: '语言', value: detail.browserEnv.language },
              ]} />
            </section>

            <section className="detail-section">
              <h3>最近登录记录</h3>
              <LogList items={detail.loginLogs} emptyText="暂无登录记录" />
            </section>

            <section className="detail-section">
              <h3>设备使用记录</h3>
              <LogList items={deviceLogs} emptyText="暂无设备使用记录" />
            </section>

            <RiskPanel title="风险提示" items={detail.riskTips.map((item, index) => ({ id: index, title: `风险提示 ${index + 1}`, description: item, status: detail.riskLevel }))} />

            <section className="detail-section">
              <h3>备注</h3>
              <p>{detail.remarks || '暂无备注'}</p>
            </section>
          </>
        ) : <EmptyState title="暂无设备详情" description="请选择一台设备查看完整信息。" />}
      </DetailModal>

      <Modal
        open={deviceModal.open}
        title={deviceModal.editing ? '编辑设备' : '新增设备'}
        onClose={() => setDeviceModal({ open: false, editing: null })}
        onConfirm={saveDevice}
        confirmText={deviceModal.editing ? '保存设备' : '创建设备'}
        width="min(960px, 94vw)"
      >
        <div className="form-grid">
          <FormField label="设备编号">
            <input value={form.deviceNo} placeholder="留空则自动生成" onChange={(event) => setForm({ ...form, deviceNo: event.target.value })} />
          </FormField>
          <FormField label="设备名称" required error={errors.name}>
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </FormField>
          <FormField label="设备类型" required error={errors.deviceType}>
            <select value={form.deviceType} onChange={(event) => setForm({ ...form, deviceType: event.target.value })}>
              {deviceTypes.map((item) => <option key={item}>{item}</option>)}
            </select>
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
          <FormField label="登录账号数">
            <input type="number" value={form.loginAccountCount} onChange={(event) => setForm({ ...form, loginAccountCount: event.target.value })} />
          </FormField>
          <FormField label="IP 地址" required error={errors.ipAddress}>
            <input value={form.ipAddress} onChange={(event) => setForm({ ...form, ipAddress: event.target.value })} />
          </FormField>
          <FormField label="代理地区" required error={errors.proxyRegion}>
            <input value={form.proxyRegion} onChange={(event) => setForm({ ...form, proxyRegion: event.target.value })} />
          </FormField>
          <FormField label="最近登录时间">
            <input value={form.lastLoginAt} placeholder="2026-06-29 16:00" onChange={(event) => setForm({ ...form, lastLoginAt: event.target.value })} />
          </FormField>
          <FormField label="设备状态" required error={errors.status}>
            <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {deviceStatuses.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="风险等级" required error={errors.riskLevel}>
            <select value={form.riskLevel} onChange={(event) => setForm({ ...form, riskLevel: event.target.value })}>
              {riskLevels.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="浏览器">
            <input value={form.browser} onChange={(event) => setForm({ ...form, browser: event.target.value })} />
          </FormField>
          <FormField label="系统">
            <input value={form.os} onChange={(event) => setForm({ ...form, os: event.target.value })} />
          </FormField>
        </div>
        <FormField label="备注">
          <textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
        </FormField>
      </Modal>

      <Modal
        open={bindModal.open}
        title={bindModal.device ? `绑定店铺 · ${bindModal.device.name}` : '绑定店铺'}
        onClose={() => setBindModal({ open: false, device: null })}
        onConfirm={submitBindStore}
        confirmText="绑定店铺"
      >
        <FormField label="选择店铺" required error={errors.bindStore}>
          <select value={bindStore} onChange={(event) => setBindStore(event.target.value)}>
            <option value="">请选择店铺</option>
            {storeOptions.map((item) => <option key={item}>{item}</option>)}
          </select>
        </FormField>
      </Modal>
    </>
  );
}
