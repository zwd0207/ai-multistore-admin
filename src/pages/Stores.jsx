import ResourcePage from '../components/common/ResourcePage';
import StatusBadge from '../components/common/StatusBadge';
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
  const credential = await findStoreCredential(store);
  return {
    ...store,
    apiConnectionStatus: apiConnectionStatus(credential),
  };
}

const STORE_PAYLOAD_KEYS = ['name', 'platform', 'manager', 'region', 'language', 'status', 'remark'];

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
    let rows = filterVisibleBusinessStores(result.data || result.items || []);
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

const platformOptions = ['Naver', 'Coupang', 'Gmarket'];
const statusOptions = ['正常运营', '审核中', '申诉中', '暂停使用'];
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
  const formalCount = row.platformProductCount
    ?? row.syncedProductCount
    ?? row.formalProductCount
    ?? row.formalSyncedProductCount;
  if (formalCount === undefined || formalCount === null || formalCount === '') return '待同步';
  const count = Number(formalCount);
  if (!Number.isFinite(count) || count <= 0) return '待同步';
  return `${count.toLocaleString()} 条`;
}

const columns = [
  { key: 'name', title: '店铺名称', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
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
];

export default function Stores() {
  const { selectedStoreId, refreshStores } = useStoreContext();

  return (
    <ResourcePage
      title="店铺管理"
      description="新增或编辑店铺时，可以在同一个窗口填写 Naver / Coupang API 连接资料。普通店铺信息和 API 密钥分区展示，保存后密钥不会明文回显。"
      resourceName="店铺"
      api={api}
      columns={columns}
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
      }}
      canCreate
      canEdit
      canDelete={!isBackendSource}
      prepareForm={prepareStoreForm}
      buildSavePayload={buildStorePayload}
      afterSave={saveStoreCredential}
      modalWidth="min(820px, 94vw)"
      onSaved={(store) => refreshStores({ preferredStoreId: selectedStoreId || normalizeStoreDisplay(store)?.id })}
    />
  );
}
