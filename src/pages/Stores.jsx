import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import OpenStoreBackendButton from '../components/common/OpenStoreBackendButton';
import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
import { useAuthContext } from '../context/AuthContext';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import mockApi from '../services/mockApi';
import { filterVisibleBusinessStores, normalizeStoreDisplay } from '../utils/storeDisplay';

const baseApi = {
  list: dataProvider.getStores,
  create: isBackendSource ? dataProvider.createStore : mockApi.createStore,
  update: isBackendSource ? dataProvider.updateStore : mockApi.updateStore,
  remove: mockApi.deleteStore,
};

function normalizePlatform(value) {
  return String(value || '').trim().toLowerCase();
}

function normalizeCredentialPlatform(value) {
  const platform = normalizePlatform(value);
  if (platform === 'naver') return 'naver';
  if (platform === 'coupang') return 'coupang';
  return platform;
}

function samePlatform(left, right) {
  return normalizeCredentialPlatform(left) === normalizeCredentialPlatform(right);
}

async function findStoreCredential(store = {}) {
  if (!store.id) return null;
  try {
    const result = await dataProvider.getCredentials({
      storeId: store.id,
      page: 1,
      pageSize: 20,
    });
    const rows = result.data || result.items || [];
    const platform = normalizeCredentialPlatform(store.rawPlatform || store.platform);
    return rows.find((item) => samePlatform(item.rawPlatform || item.platform, platform)) || rows[0] || null;
  } catch {
    return null;
  }
}

function apiConnectionStatus(credential) {
  if (!credential) return '未配置';
  const hasMainKey = Boolean(credential.clientId || credential.vendorId || credential.hasAccessKey);
  const hasSecret = Boolean(credential.hasSecretKey);
  if (hasMainKey && hasSecret) return '已配置';
  if (hasMainKey || hasSecret) return '待补齐';
  return '未配置';
}

async function withApiConnectionStatus(store) {
  if (!isBackendSource) return { ...store, apiConnectionStatus: '演示数据' };
  if (store.archived) return { ...store, apiConnectionStatus: '已归档' };
  if (store.openOnly) return { ...store, apiConnectionStatus: '仅打开后台' };
  const credential = await findStoreCredential(store);
  return {
    ...store,
    apiConnectionStatus: apiConnectionStatus(credential),
  };
}

const STORE_PAYLOAD_KEYS = [
  'name', 'platform', 'manager', 'region', 'language', 'status', 'remark',
  'browserProvider', 'browserProfileName',
];

function buildStorePayload({ form }) {
  return STORE_PAYLOAD_KEYS.reduce((payload, key) => ({ ...payload, [key]: form[key] }), {});
}

function hasText(value) {
  return Boolean(String(value || '').trim());
}

function hasCredentialInput(form = {}) {
  return Boolean(
    form.apiCredentialId
    || hasText(form.apiCredentialName)
    || hasText(form.naverClientId)
    || hasText(form.coupangVendorId)
    || hasText(form.coupangAccessKeyInput)
    || hasText(form.apiSecretKeyInput)
    || hasText(form.apiRemark),
  );
}

function credentialPayload(savedStore, form = {}) {
  const platform = normalizeCredentialPlatform(form.platform);
  const storeName = savedStore?.name || form.name || '店铺';
  return {
    storeId: savedStore?.id || form.storeId,
    platform,
    name: form.apiCredentialName || `${storeName} ${platform === 'coupang' ? 'Coupang' : 'Naver'} 接口`,
    clientId: platform === 'naver' ? form.naverClientId : undefined,
    vendorId: platform === 'coupang' ? form.coupangVendorId : undefined,
    accessKeyInput: platform === 'coupang' ? form.coupangAccessKeyInput : undefined,
    secretKeyInput: form.apiSecretKeyInput,
    status: form.apiStatus || 'active',
    apiRemark: form.apiRemark,
  };
}

function readableStoreRemark(value = '') {
  return String(value || '')
    .replaceAll('OpenAPI', '开放接口')
    .replaceAll('vendor_id', '卖家编号')
    .replaceAll('client_id', '客户端编号')
    .replaceAll('API', '接口');
}

async function saveStoreCredential({ saved, form }) {
  if (!hasCredentialInput(form)) return;
  const payload = credentialPayload(saved, form);
  if (!payload.storeId || !['naver', 'coupang'].includes(payload.platform)) return;
  if (form.apiCredentialId) {
    await dataProvider.updateCredential(form.apiCredentialId, payload);
  } else {
    await dataProvider.createCredential(payload);
  }
}

async function prepareStoreForm({ record, form }) {
  const credential = record ? await findStoreCredential(record) : null;
  return {
    ...form,
    remark: readableStoreRemark(form.remark),
    apiCredentialId: credential?.id || '',
    apiCredentialName: credential?.name || '',
    naverClientId: credential?.clientId || '',
    coupangVendorId: credential?.vendorId || '',
    coupangAccessKeyInput: '',
    apiSecretKeyInput: '',
    apiStatus: credential?.status || 'active',
    apiRemark: readableStoreRemark(credential?.apiRemark || ''),
    apiSecretExistingStatus: credential?.hasSecretKey ? '已保存，更新时重新填写' : '未保存',
    coupangAccessKeyExistingStatus: credential?.hasAccessKey ? '已保存，更新时重新填写' : '未保存',
  };
}

const api = {
  ...baseApi,
  list: async (params = {}) => {
    const page = Math.max(Number(params.page) || 1, 1);
    const pageSize = Math.max(Number(params.pageSize) || 5, 1);
    const result = await baseApi.list({ ...params, page: 1, pageSize: 100 });
    let rows = params.includeArchived
      ? (result.data || result.items || []).map(normalizeStoreDisplay)
      : filterVisibleBusinessStores(result.data || result.items || []);
    const keyword = String(params.keyword || '').trim().toLowerCase();
    const platform = String(params.platform || '').trim().toLowerCase();
    const status = String(params.status || '').trim();
    if (keyword) {
      rows = rows.filter((item) => `${item.name || ''} ${item.manager || ''} ${item.platform || ''}`.toLowerCase().includes(keyword));
    }
    if (platform) {
      rows = rows.filter((item) => String(item.platform || '').trim().toLowerCase() === platform);
    }
    if (status) {
      rows = rows.filter((item) => String(item.status || '').trim() === status);
    }
    const total = rows.length;
    const start = (page - 1) * pageSize;
    const pageRows = await Promise.all(rows.slice(start, start + pageSize).map(withApiConnectionStatus));
    return {
      ...result,
      data: pageRows,
      items: pageRows,
      total,
      page,
      pageSize,
    };
  },
};

const platformOptions = ['Naver', 'Coupang', 'Custom', 'Gmarket'];
const statusOptions = ['正常运营', '审核中', '申诉中', '暂停使用', '已归档'];
const apiStatusOptions = [
  { value: 'active', label: '启用' },
  { value: 'inactive', label: '停用' },
];
const languageOptions = [
  { value: 'ko-KR', label: '韩文' },
  { value: 'zh-CN', label: '中文' },
];
const isNaverForm = (form) => normalizeCredentialPlatform(form.platform) === 'naver';
const isCoupangForm = (form) => normalizeCredentialPlatform(form.platform) === 'coupang';

function displaySyncedProductCount(_value, row = {}) {
  if (row.openOnly) return '不接入业务数据';
  if (row.archived) return '历史数据保留';
  const formalCount = row.platformProductCount
    ?? row.syncedProductCount
    ?? row.formalProductCount
    ?? row.formalSyncedProductCount;
  if (formalCount === undefined || formalCount === null || formalCount === '') return '待同步';
  const count = Number(formalCount);
  if (!Number.isFinite(count) || count <= 0) return '待同步';
  return `${count.toLocaleString()} 条`;
}

function directoryStatusLabel(value, row = {}) {
  if (row.archived || value === 'removed') return '已从紫鸟移除';
  if (value === 'active') return row.openOnly ? '已同步，仅打开' : '同步正常';
  return '本地店铺';
}

function storeNetworkLabel(row = {}) {
  const network = row.network || {};
  const location = [network.country, network.region, network.city].filter(Boolean).join(' / ');
  const statuses = {
    success: location || '归属已确认',
    failed: '归属查询失败',
    pending: '归属查询中',
    no_ip: '暂无 IP',
    dynamic: '动态网络，打开时分配 IP',
    not_applicable: '私网或保留地址',
    not_configured: '待同步',
  };
  return [network.ipAddress || '暂无 IP', statuses[network.status] || '待同步'].join(' · ');
}

const columns = [
  { key: 'name', title: '店铺名称', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'ziniaoDirectoryStatus', title: '紫鸟目录', render: (value, row) => <StatusBadge value={directoryStatusLabel(value, row)} /> },
  { key: 'network', title: 'IP / 归属', render: (_value, row) => storeNetworkLabel(row) },
  { key: 'manager', title: '负责人' },
  { key: 'region', title: '地区' },
  { key: 'products', title: '同步商品数', render: displaySyncedProductCount },
  { key: 'apiConnectionStatus', title: '接口连接', render: (value) => <StatusBadge value={value || '未配置'} /> },
  { key: 'status', title: '运营状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'updatedAt', title: '最近更新' },
];
const fields = [
  { key: 'store-section', type: 'section', label: '店铺基础信息', description: '店铺名称、平台、负责人和运营状态。' },
  { key: 'name', label: '店铺名称', required: true },
  { key: 'platform', label: '平台', type: 'select', required: true, options: platformOptions },
  { key: 'manager', label: '负责人' },
  { key: 'region', label: '地区', required: true },
  { key: 'language', label: '语言', type: 'select', required: true, options: languageOptions },
  { key: 'status', label: '运营状态', type: 'select', required: true, options: statusOptions },
  { key: 'remark', label: '备注' },
  {
    key: 'api-section',
    type: 'section',
    label: '平台 API 连接资料',
    description: 'Naver / Coupang 官方接口资料可在这里和店铺一起填写。密钥不会明文回显，需要更新时重新输入。',
  },
  { key: 'apiCredentialName', label: '接口连接名称', placeholder: '例如：pxg球包店 Naver 接口', showWhen: (form) => isNaverForm(form) || isCoupangForm(form) },
  { key: 'apiStatus', label: '接口启用状态', type: 'select', options: apiStatusOptions, showWhen: (form) => isNaverForm(form) || isCoupangForm(form) },
  {
    key: 'naverClientId',
    label: 'Naver 客户端编号',
    placeholder: '填写 Naver Commerce API Center 的客户端编号',
    showWhen: isNaverForm,
  },
  {
    key: 'coupangVendorId',
    label: 'Coupang 卖家编号',
    placeholder: '填写 Coupang 卖家编号',
    showWhen: isCoupangForm,
  },
  {
    key: 'coupangAccessKeyInput',
    label: 'Coupang 访问密钥',
    type: 'password',
    placeholder: '不修改可留空',
    showWhen: isCoupangForm,
    help: (form) => `当前状态：${form.coupangAccessKeyExistingStatus || '未保存'}。`,
  },
  {
    key: 'apiSecretKeyInput',
    label: '接口密钥',
    type: 'password',
    placeholder: '不修改可留空',
    showWhen: (form) => isNaverForm(form) || isCoupangForm(form),
    help: (form) => `当前状态：${form.apiSecretExistingStatus || '未保存'}。保存后不会在页面明文显示。`,
  },
  {
    key: 'apiRemark',
    label: '接口备注',
    placeholder: '例如：主账号接口资料，仅用于商品/订单读取',
    showWhen: (form) => isNaverForm(form) || isCoupangForm(form),
  },
  {
    key: 'browser-section',
    type: 'section',
    label: '紫鸟浏览器绑定',
    description: '绑定后，运营人员可从系统打开该店铺既有的紫鸟浏览器、登录会话和 IP 设备环境。',
  },
  {
    key: 'browserProvider',
    label: '浏览器服务',
    type: 'select',
    options: [{ value: 'ziniao', label: '紫鸟浏览器' }],
  },
  {
    key: 'browserProfileName',
    label: '紫鸟店铺名称',
    placeholder: '必须与紫鸟店铺列表中的名称完全一致',
    showWhen: (form) => form.browserProvider === 'ziniao',
    help: '紫鸟目录店铺由系统自动维护绑定；此字段仅用于未接入目录的人工店铺。',
  },
];

const ONBOARDING_STORAGE_KEY = 't13_store_onboarding_id';
const ONBOARDING_TERMINAL_STATUSES = new Set(['blocked', 'partially_synced', 'active_incremental', 'cancelled']);
const EMPTY_ONBOARDING_FORM = { storeName: '', clientId: '', clientSecret: '', channelNo: '' };
const ONBOARDING_SOURCE_LABELS = {
  products: '商品',
  orders: '订单',
  customer_inquiries: '客服咨询',
  logistics: '物流',
};
const ONBOARDING_REASON_LABELS = {
  auth_failed: '客户端编号或密钥验证失败，请检查后重新提交。',
  channel_missing: '未找到可用频道，请填写正确的频道编号。',
  channel_not_found: '频道编号不可用，请确认 Naver 店铺频道。',
  ip_not_allowed: '当前服务器 IP 未加入 Naver 白名单，请配置后重试。',
  permission_denied: '当前 Naver 应用权限不足，请补齐商品和订单读取权限。',
  channel_identity_mismatch: '频道与当前卖家身份不一致，请确认频道编号。',
  channel_identity_unresolved: '无法识别当前卖家频道，请填写频道编号后重试。',
  network_timeout: '连接 Naver 超时，可以稍后继续重试。',
  network_error: '暂时无法连接 Naver，可以稍后继续重试。',
  naver_read_retryable: 'Naver 读取暂时受限，可以稍后继续重试。',
  naver_validation_not_ready: 'Naver 连接尚未通过验证，请检查连接资料和应用权限。',
  naver_validation_unexpected_failure: 'Naver 验证暂时不可用，请稍后重试。',
  not_approved: '该数据源尚未批准接入。',
  optional_not_approved: '该可选数据源尚未批准接入。',
};
const ONBOARDING_STATUS_LABELS = {
  validating: '验证中',
  blocked: '需要处理',
  provisioning: '正在创建店铺',
  backfilling: '正在同步初始数据',
  partially_synced: '必需数据已同步',
  active_incremental: '已连接',
  retry_wait: '等待重试',
  cancelled: '已取消',
  success: '同步成功',
  failed: '同步失败',
  not_approved: '尚未批准',
  not_started: '等待同步',
};

function readStoredOnboardingId() {
  try {
    return sessionStorage.getItem(ONBOARDING_STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

function storeOnboardingId(onboardingId) {
  try {
    if (onboardingId) sessionStorage.setItem(ONBOARDING_STORAGE_KEY, String(onboardingId));
    else sessionStorage.removeItem(ONBOARDING_STORAGE_KEY);
  } catch {
    // Session storage may be unavailable in restricted browser contexts.
  }
}

function generateIdempotencyKey() {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `t13-naver-${random}`;
}

function onboardingReason(onboarding) {
  const code = onboarding?.lastErrorCode || '';
  return ONBOARDING_REASON_LABELS[code] || (code ? '连接未通过，请检查客户端资料、频道编号、IP 白名单和应用读取权限。' : '等待 Naver 返回验证结果。');
}

function onboardingStatusLabel(status, fallback = '等待同步') {
  return ONBOARDING_STATUS_LABELS[status] || fallback;
}

function OnboardingProgress({ onboarding }) {
  const progress = onboarding?.progressSummary || {};
  const validation = onboarding?.validationSummary || {};
  const validationItems = [
    ['身份验证', validation.token_authenticated],
    ['卖家身份', validation.seller_identity_verified],
    ['频道', validation.channel_verified],
    ['IP 白名单', validation.ip_ready],
    ['读取权限', validation.permission_ready],
  ];
  return (
    <div className="onboarding-progress" aria-live="polite">
      <div className="card-title">
        <div>
          <h3>连接进度</h3>
          <p>当前状态：{onboardingStatusLabel(onboarding?.status, '尚未提交')}</p>
        </div>
        <StatusBadge value={onboardingStatusLabel(onboarding?.status, '等待提交')} />
      </div>
      {Object.keys(validation).length ? (
        <div className="onboarding-validation" aria-label="Naver 连接验证结果">
          {validationItems.map(([label, passed]) => (
            <span key={label}><strong>{label}</strong>：{passed ? '已通过' : '未通过'}</span>
          ))}
        </div>
      ) : null}
      <div className="onboarding-source-grid">
        {Object.entries(ONBOARDING_SOURCE_LABELS).map(([key, label]) => {
          const source = progress[key] || {};
          const count = Number(source.created ?? 0) + Number(source.updated ?? 0);
          const mandatory = key === 'products' || key === 'orders';
          const reasonCode = source.reason || source.error_code || '';
          const reason = ONBOARDING_REASON_LABELS[reasonCode] || (reasonCode ? '该数据源暂时不可用，请检查连接权限。' : '');
          return (
            <div className="onboarding-source" key={key}>
              <strong>{label}</strong>
              <StatusBadge value={onboardingStatusLabel(source.status)} />
              <span>{source.status === 'success' ? `${count} 条` : '数量待确认'}</span>
              {reason ? <small>{reason}</small> : null}
              <em>{mandatory ? '必需数据源' : '可选数据源，尚未批准接入'}</em>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Stores() {
  const { selectedStoreId, setSelectedStoreId, refreshStores } = useStoreContext();
  const { stores: authorizedStores, refreshSession } = useAuthContext();
  const [searchParams] = useSearchParams();
  const queryStoreId = searchParams.get('storeId') || '';
  const queryFocus = searchParams.get('focus') || '';
  const [wizardOpen, setWizardOpen] = useState(false);
  const [onboardingId, setOnboardingId] = useState(readStoredOnboardingId);
  const [onboarding, setOnboarding] = useState(null);
  const [onboardingForm, setOnboardingForm] = useState(EMPTY_ONBOARDING_FORM);
  const [onboardingErrors, setOnboardingErrors] = useState({});
  const [onboardingNotice, setOnboardingNotice] = useState('');
  const [onboardingSubmitting, setOnboardingSubmitting] = useState(false);
  const [editingBlocked, setEditingBlocked] = useState(false);
  const [pollVersion, setPollVersion] = useState(0);
  const [includeArchived, setIncludeArchived] = useState(false);
  const idempotencyKeyRef = useRef(generateIdempotencyKey());
  const canViewArchived = authorizedStores.some((store) => (
    store.permissions?.includes('*')
    || store.permissions?.includes('store_membership.assign')
    || store.permissions?.includes('store.manage')
  ));

  useEffect(() => {
    if (queryStoreId) setSelectedStoreId(queryStoreId);
  }, [queryStoreId, setSelectedStoreId]);

  useEffect(() => {
    if (!canViewArchived) setIncludeArchived(false);
  }, [canViewArchived]);

  useEffect(() => {
    if (!isBackendSource || !onboardingId) return undefined;
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const result = await dataProvider.getStoreOnboarding(onboardingId);
        if (cancelled) return;
        setOnboarding(result);
        if (result?.storeId) {
          await refreshSession();
          await refreshStores({ preferredStoreId: result.storeId });
          if (!cancelled) setSelectedStoreId(result.storeId);
        }
        if (!ONBOARDING_TERMINAL_STATUSES.has(result?.status)) timer = setTimeout(poll, 1500);
      } catch (error) {
        if (!cancelled) setOnboardingNotice(error.message || '店铺连接进度读取失败，请稍后刷新。');
      }
    };
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [onboardingId, pollVersion, refreshSession, refreshStores, setSelectedStoreId]);

  const validateOnboarding = (correction = false) => {
    const errors = {};
    if (!correction && !onboardingForm.storeName.trim()) errors.storeName = '请填写店铺名称';
    if (!onboardingForm.clientId.trim()) errors.clientId = '请填写 Naver 客户端编号';
    if (!onboardingForm.clientSecret.trim()) errors.clientSecret = '请填写 Naver 客户端密钥';
    setOnboardingErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const submitOnboarding = async () => {
    if (onboardingSubmitting || !validateOnboarding(editingBlocked)) return;
    setOnboardingSubmitting(true);
    setOnboardingNotice('');
    try {
      const payload = {
        client_id: onboardingForm.clientId.trim(),
        client_secret: onboardingForm.clientSecret,
        channel_no: onboardingForm.channelNo.trim() || null,
      };
      const result = editingBlocked
        ? await dataProvider.updateStoreOnboarding(onboarding.id, payload)
        : await dataProvider.createStoreOnboarding({
          ...payload,
          idempotency_key: idempotencyKeyRef.current,
          store_name: onboardingForm.storeName.trim(),
        });
      const safeId = result.id || onboarding?.id;
      storeOnboardingId(safeId);
      setOnboardingId(String(safeId));
      setOnboarding(result);
      setOnboardingForm(EMPTY_ONBOARDING_FORM);
      setEditingBlocked(false);
      setPollVersion((value) => value + 1);
      setOnboardingNotice(editingBlocked ? '连接资料已更新，正在使用同一任务重新验证。' : '已提交 Naver 店铺连接，系统正在验证并同步本地数据。');
    } catch (error) {
      setOnboardingNotice(error.message || 'Naver 店铺连接提交失败，请检查后重试。');
    } finally {
      setOnboardingSubmitting(false);
    }
  };

  const openOnboardingWizard = () => {
    setWizardOpen(true);
    setOnboardingErrors({});
    setOnboardingNotice('');
  };

  const closeOnboardingWizard = () => {
    setWizardOpen(false);
    setOnboardingForm((current) => ({ ...current, clientId: '', clientSecret: '' }));
    setOnboardingErrors({});
  };

  const editBlockedOnboarding = () => {
    setOnboardingForm({
      storeName: onboarding?.requestedStoreName || '',
      clientId: '',
      clientSecret: '',
      channelNo: '',
    });
    setEditingBlocked(true);
    setOnboardingErrors({});
  };

  const resumeOnboarding = async () => {
    if (!onboarding?.id || onboardingSubmitting) return;
    setOnboardingSubmitting(true);
    setOnboardingNotice('正在继续同一店铺连接任务...');
    try {
      const result = await dataProvider.resumeStoreOnboarding(onboarding.id);
      setOnboarding(result);
      setPollVersion((value) => value + 1);
      setOnboardingNotice('连接任务已继续，正在读取最新进度。');
    } catch (error) {
      setOnboardingNotice(error.message || '连接任务继续失败，请稍后重试。');
    } finally {
      setOnboardingSubmitting(false);
    }
  };

  const startAnotherOnboarding = () => {
    storeOnboardingId('');
    setOnboardingId('');
    setOnboarding(null);
    setEditingBlocked(false);
    setOnboardingForm(EMPTY_ONBOARDING_FORM);
    idempotencyKeyRef.current = generateIdempotencyKey();
  };

  return (
    <>
      <ResourcePage
      title="店铺与平台连接"
      description="仅管理员维护店铺资料和平台连接。日常运营请在今日工作台、订单处理和仓库发货中完成工作。"
      resourceName="店铺"
      api={api}
      columns={columns}
      initialQuery={{ pageSize: 100 }}
      initialQueryKey={`${queryStoreId}:${queryFocus}:${includeArchived}`}
      extraParams={{ includeArchived }}
      openRecordId={queryFocus === 'connection' ? queryStoreId : ''}
      openRecordKey={queryFocus}
      fields={fields}
      statuses={statusOptions}
      platforms={platformOptions}
      initialForm={{
        name: '',
        platform: 'Naver',
        manager: '',
        region: '韩国',
        language: 'ko-KR',
        status: '正常运营',
        remark: '',
        apiCredentialId: '',
        apiCredentialName: '',
        naverClientId: '',
        coupangVendorId: '',
        coupangAccessKeyInput: '',
        apiSecretKeyInput: '',
        apiStatus: 'active',
        apiRemark: '',
        apiSecretExistingStatus: '未保存',
        coupangAccessKeyExistingStatus: '未保存',
        browserProvider: '',
        browserProfileName: '',
      }}
      canCreate
      canEdit
      canDelete={!isBackendSource}
      prepareForm={prepareStoreForm}
      buildSavePayload={buildStorePayload}
      afterSave={saveStoreCredential}
      modalWidth="min(820px, 94vw)"
      extraActions={(
        <>
          {canViewArchived ? (
            <button className="button ghost" type="button" onClick={() => setIncludeArchived((value) => !value)}>
              {includeArchived ? '隐藏归档店铺' : '查看归档店铺'}
            </button>
          ) : null}
          <button className="button ghost" type="button" onClick={openOnboardingWizard}>添加 Naver 店铺</button>
        </>
      )}
      renderExtraActions={(store) => (
        <>
          <OpenStoreBackendButton store={store} compact />
          {store.archived ? (
            <Link className="button ghost compact" to={`/orders?view=historical&storeId=${encodeURIComponent(store.id)}`}>
              查询历史订单
            </Link>
          ) : null}
        </>
      )}
      onSaved={(store) => refreshStores({ preferredStoreId: normalizeStoreDisplay(store)?.id || selectedStoreId })}
      />
      <Modal
        open={wizardOpen}
        title={editingBlocked ? '修改 Naver 连接资料' : '添加 Naver 店铺'}
        onClose={closeOnboardingWizard}
        onConfirm={submitOnboarding}
        confirmText={onboardingSubmitting ? '正在提交...' : editingBlocked ? '更新并重新验证' : '提交连接'}
        confirmDisabled={onboardingSubmitting || Boolean(onboarding && !editingBlocked)}
        width="min(760px, calc(100vw - 24px))"
      >
        {onboarding?.status === 'blocked' && !editingBlocked ? (
          <div className="onboarding-blocked" role="alert">
            <strong>连接需要处理</strong>
            <span>{onboardingReason(onboarding)}</span>
            <button className="button ghost" type="button" onClick={editBlockedOnboarding}>修改连接资料</button>
          </div>
        ) : null}
        {!onboarding || editingBlocked ? (
          <div className="onboarding-form">
            <FormField label="店铺名称" required={!editingBlocked} error={onboardingErrors.storeName}>
              <input value={onboardingForm.storeName} disabled={editingBlocked} onChange={(event) => setOnboardingForm({ ...onboardingForm, storeName: event.target.value })} autoComplete="off" />
            </FormField>
            <FormField label="Naver 客户端编号" required error={onboardingErrors.clientId}>
              <input value={onboardingForm.clientId} onChange={(event) => setOnboardingForm({ ...onboardingForm, clientId: event.target.value })} autoComplete="off" />
            </FormField>
            <FormField label="Naver 客户端密钥" required error={onboardingErrors.clientSecret}>
              <input type="password" value={onboardingForm.clientSecret} onChange={(event) => setOnboardingForm({ ...onboardingForm, clientSecret: event.target.value })} autoComplete="new-password" />
            </FormField>
            <FormField label="频道编号（选填）">
              <input value={onboardingForm.channelNo} onChange={(event) => setOnboardingForm({ ...onboardingForm, channelNo: event.target.value })} autoComplete="off" />
            </FormField>
          </div>
        ) : null}
        {onboardingNotice ? <div className="form-info">{onboardingNotice}</div> : null}
        {onboarding ? <OnboardingProgress onboarding={onboarding} /> : null}
        {onboarding?.status === 'retry_wait' ? (
          <button className="button ghost" type="button" onClick={resumeOnboarding} disabled={onboardingSubmitting}>继续重试</button>
        ) : null}
        {onboarding && ['partially_synced', 'active_incremental', 'cancelled'].includes(onboarding.status) ? (
          <button className="button ghost" type="button" onClick={startAnotherOnboarding}>添加另一家 Naver 店铺</button>
        ) : null}
      </Modal>
    </>
  );
}
