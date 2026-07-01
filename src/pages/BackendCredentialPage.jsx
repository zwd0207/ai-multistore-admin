import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider from '../services/dataProvider';

const statusOptions = ['active', 'inactive'];
const authStatusOptions = ['not_configured', 'configured', 'needs_test', 'test_failed', 'test_passed'];
const platformOptions = [
  { value: 'naver', label: 'Naver' },
  { value: 'coupang', label: 'Coupang' },
];

const NAVER_DEFAULT_API_BASE = 'https://api.commerce.naver.com/external';

const initialForm = {
  name: '',
  platform: 'naver',
  status: 'active',
  vendorId: '',
  clientId: '',
  accessKeyInput: '',
  secretKeyInput: '',
  accessTokenInput: '',
  refreshTokenInput: '',
  tokenExpiresAt: '',
  market: 'KR',
  authStatus: 'not_configured',
  apiRemark: '',
};

const columns = [
  { key: 'name', title: '凭证名称', render: (value) => <strong>{value}</strong> },
  { key: 'store', title: '店铺' },
  { key: 'platform', title: '平台' },
  { key: 'identityLabel', title: '平台标识' },
  { key: 'accessKeyStatus', title: '访问配置' },
  { key: 'secretKeyStatus', title: '密钥配置' },
  { key: 'tokenStatus', title: 'Token 配置' },
  { key: 'authStatus', title: 'API 本地状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'status', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'lastTestedAt', title: '上次测试' },
  { key: 'updatedAt', title: '更新时间' },
];

function cleanError(error) {
  const detail = error?.data?.detail || error?.detail;
  if (Array.isArray(detail) && detail.length) {
    const messages = detail
      .map((item) => {
        const field = Array.isArray(item?.loc) ? item.loc.join('.') : item?.field;
        const message = item?.msg || item?.message;
        return [field, message].filter(Boolean).join(': ');
      })
      .filter(Boolean);
    if (messages.length) return `${error?.message || '请求参数校验失败'}：${messages.join('；')}`;
  }
  if (detail?.missing_fields?.length) {
    return `${error?.message || '请求参数校验失败'}：缺少 ${detail.missing_fields.join(', ')}`;
  }
  return error?.message || '后端保存失败，请检查 Codex1 状态或表单内容。';
}

function toDatetimeLocalValue(value) {
  if (!value) return '';
  return String(value).slice(0, 16);
}

function hasInvalidDatetime(value) {
  const raw = String(value || '').trim();
  if (!raw) return false;
  return Number.isNaN(new Date(raw).getTime());
}

function buildRecordForm(record) {
  if (!record) return initialForm;
  return {
    name: record.name || '',
    platform: String(record.rawPlatform || record.platform || 'naver').toLowerCase(),
    status: record.status || 'active',
    vendorId: record.vendorId || '',
    clientId: record.clientId || '',
    accessKeyInput: '',
    secretKeyInput: '',
    accessTokenInput: '',
    refreshTokenInput: '',
    tokenExpiresAt: toDatetimeLocalValue(record.tokenExpiresAt),
    market: record.market || 'KR',
    authStatus: record.authStatus || 'not_configured',
    apiRemark: record.apiRemark || '',
  };
}

function CredentialBusinessStatus({ selectedStoreId, readiness }) {
  const storeBound = readiness?.storeBoundReadiness;
  const platform = String(storeBound?.rawPlatform || storeBound?.platform || '').toLowerCase();
  if (!selectedStoreId) return null;

  const title = platform === 'naver' ? 'Naver 凭证状态' : platform === 'coupang' ? 'Coupang 凭证状态' : 'API 凭证状态';
  const items = platform === 'naver'
    ? [
      { label: 'Client ID', value: storeBound?.clientIdConfigured ? '已配置' : '未配置' },
      { label: 'Client Secret', value: storeBound?.secretKeyConfigured && storeBound?.secretKeyDecryptable ? '已配置' : '未配置完整' },
      { label: '店铺频道编号', value: storeBound?.channelNoConfigured ? '已识别' : '暂未识别' },
      { label: '下一步', value: storeBound?.channelNoConfigured ? '可进入商品/订单前置设计' : '先完成店铺频道信息读取检测' },
    ]
    : [
      { label: '平台连接', value: '请在平台能力页查看最近检测状态' },
      { label: '商品/订单', value: 'Coupang 读取与同步入口已按阶段开放' },
      { label: '销售/结算', value: '销售与结算口径在销售页和 Dashboard 分区展示' },
      { label: '下一步', value: '按业务页面核对商品、订单、销售与结算数据' },
    ];

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>{title}</h2>
          <p>只展示配置状态和下一步建议，不显示密钥、token、Authorization、签名或 raw response。</p>
        </div>
      </div>
      <div className="business-capability-grid compact">
        {items.map((item) => (
          <article className="business-capability-card info" key={item.label}>
            <div className="business-capability-head">
              <strong>{item.label}</strong>
              <span>{item.value}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function BackendCredentialPage({ embedded = false }) {
  const {
    selectedStoreId,
    loading: storeLoading,
    error: storeError,
  } = useStoreContext();
  const [query, setQuery] = useState({
    keyword: '',
    status: '',
    platform: '',
    page: 1,
    pageSize: 5,
  });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({
    data: [],
    total: 0,
    page: 1,
    pageSize: 5,
  });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [notice, setNotice] = useState('');
  const [modal, setModal] = useState({ open: false, record: null });
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [saveError, setSaveError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [readiness, setReadiness] = useState(null);

  const canWrite = Boolean(selectedStoreId) && !storeLoading && !storeError;
  const isNaverForm = String(form.platform || '').toLowerCase() === 'naver';
  const isCoupangForm = String(form.platform || '').toLowerCase() === 'coupang';

  const params = useMemo(() => ({ ...query, storeId: selectedStoreId }), [query, selectedStoreId]);

  const load = useCallback(async () => {
    if (storeLoading) return;
    if (storeError) {
      setLoadError(storeError);
      setLoading(false);
      return;
    }
    if (!selectedStoreId) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError('');
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError('');
    try {
      setResult(await dataProvider.getCredentials(params));
    } catch (error) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError(error.message || 'API 凭证数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [params, query.page, query.pageSize, selectedStoreId, storeError, storeLoading]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedStoreId || storeLoading || storeError) {
      setReadiness(null);
      return;
    }
    let cancelled = false;
    dataProvider.getApiCredentialReadiness({ storeId: selectedStoreId })
      .then((result) => {
        if (!cancelled) setReadiness(result);
      })
      .catch(() => {
        if (!cancelled) setReadiness(null);
      });
    return () => { cancelled = true; };
  }, [selectedStoreId, storeError, storeLoading]);

  const resetSensitiveInputs = (nextForm = form) => ({
    ...nextForm,
    accessKeyInput: '',
    secretKeyInput: '',
    accessTokenInput: '',
    refreshTokenInput: '',
  });

  const openModal = (record = null) => {
    setModal({ open: true, record });
    setForm(buildRecordForm(record));
    setErrors({});
    setSaveError('');
    setNotice('');
  };

  const closeModal = () => {
    if (submitting) return;
    setModal({ open: false, record: null });
    setForm(initialForm);
    setErrors({});
    setSaveError('');
  };

  const validate = () => {
    const nextErrors = {};
    if (!selectedStoreId) nextErrors.form = '请先选择店铺';
    if (!String(form.name || '').trim()) nextErrors.name = '请填写凭证名称';
    if (!String(form.platform || '').trim()) nextErrors.platform = '请选择平台';
    if (!String(form.status || '').trim()) nextErrors.status = '请选择状态';
    if (!String(form.authStatus || '').trim()) nextErrors.authStatus = '请选择 API 本地状态';
    if (isNaverForm && !String(form.clientId || '').trim()) nextErrors.clientId = '请填写 Client ID';
    if (isCoupangForm && !modal.record && !String(form.accessKeyInput || '').trim()) nextErrors.accessKeyInput = '请填写访问配置';
    if (!modal.record && !String(form.secretKeyInput || '').trim()) {
      nextErrors.secretKeyInput = isNaverForm ? '请填写 Client Secret' : '请填写密钥配置';
    }
    if (isNaverForm && hasInvalidDatetime(form.tokenExpiresAt)) nextErrors.tokenExpiresAt = '请填写有效的 Token 到期时间';
    setErrors(nextErrors);
    return !Object.keys(nextErrors).length;
  };

  const save = async () => {
    if (submitting) return;
    setSaveError('');
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload = { ...form, storeId: selectedStoreId };
      if (modal.record) {
        await dataProvider.updateCredential(modal.record.id, payload);
      } else {
        await dataProvider.createCredential(payload);
      }
      setModal({ open: false, record: null });
      setForm(initialForm);
      await load();
    } catch (error) {
      setForm((current) => resetSensitiveInputs(current));
      setSaveError(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const disableCredential = async (record) => {
    if (!canWrite || submitting) return;
    setSubmitting(true);
    setNotice('');
    try {
      await dataProvider.disableCredential(record.id, { storeId: selectedStoreId });
      await load();
      setNotice('凭证已停用，本地列表已刷新。');
    } catch (error) {
      setNotice(cleanError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const showTestNotice = () => {
    setNotice('真实 API 联调仍在后端只读阶段，这里当前只保存本地配置，不会展示敏感字段。');
  };

  const handlePlatformChange = (value) => {
    setForm((current) => ({
      ...current,
      platform: value,
      accessKeyInput: value === 'coupang' ? current.accessKeyInput : '',
    }));
    setErrors((current) => ({
      ...current,
      platform: '',
      clientId: '',
      accessKeyInput: '',
      secretKeyInput: '',
    }));
  };

  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => {
    const clean = {
      keyword: '',
      status: '',
      platform: '',
      page: 1,
      pageSize: 5,
    };
    setDraftQuery(clean);
    setQuery(clean);
  };

  const pageTitle = '账号管理';
  const pageDescription = storeError
    || (!selectedStoreId && !storeLoading
      ? '请先选择店铺'
      : '维护当前店铺的本地 API 凭证配置，不会在这里执行真实平台写操作。');

  return (
    <>
      {!embedded && (
        <PageHeader
          title={pageTitle}
          description={pageDescription}
          actions={(
            <>
              <button className="button ghost" onClick={load}>刷新</button>
              <span className="period-chip">本地后端写入</span>
              {canWrite && <button className="button primary" onClick={() => openModal()}>新增 API 凭证</button>}
            </>
          )}
        />
      )}

      <CredentialBusinessStatus selectedStoreId={selectedStoreId} readiness={readiness} />

      <section className="content-card">
        {embedded && (
          <div className="section-heading">
            <div>
              <h2>API 开发凭证</h2>
              <p>{pageDescription}</p>
            </div>
            <div className="page-actions">
              <button className="button ghost" onClick={load}>刷新</button>
              {canWrite && <button className="button primary" onClick={() => openModal()}>新增 API 凭证</button>}
            </div>
          </div>
        )}

        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索凭证名称或平台"
        >
          <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </SearchBar>

        {notice && <div className="form-info">{notice}</div>}

        {loadError ? (
          <EmptyState title="API 凭证数据加载失败" description={loadError} />
        ) : !selectedStoreId && !storeLoading ? (
          <EmptyState title="暂无店铺数据" description="请先选择店铺后再维护 API 凭证。" />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={(result.data || []).map((row) => ({
                ...row,
                identityLabel: row.rawPlatform === 'coupang'
                  ? row.vendorId || '未配置 Vendor ID'
                  : row.clientId || '未配置 Client ID',
                accessKeyStatus: row.rawPlatform === 'naver'
                  ? '不适用'
                  : row.accessKeyStatus,
                tokenStatus: row.rawPlatform === 'naver'
                  ? `${row.accessTokenStatus} / ${row.refreshTokenStatus}`
                  : '不适用',
              }))}
              loading={loading || storeLoading}
              renderActions={(row) => (
                <>
                  <button onClick={() => openModal(row)} disabled={!canWrite || submitting}>编辑</button>
                  {row.status !== 'inactive' && (
                    <button
                      className="danger-text"
                      onClick={() => disableCredential(row)}
                      disabled={!canWrite || submitting}
                    >
                      停用
                    </button>
                  )}
                  <button onClick={showTestNotice}>测试连接</button>
                </>
              )}
            />
            <Pagination
              page={query.page}
              pageSize={query.pageSize}
              total={result.total}
              onChange={(page) => setQuery({ ...query, page })}
            />
          </>
        )}
      </section>

      <Modal
        open={modal.open}
        title={`${modal.record ? '编辑' : '新增'} API 凭证`}
        onClose={closeModal}
        onConfirm={save}
        confirmText={submitting ? '保存中...' : '保存'}
        confirmDisabled={submitting}
      >
        {(saveError || errors.form) && <div className="form-error">{saveError || errors.form}</div>}

        <div className="form-grid">
          <FormField label="凭证名称" required error={errors.name}>
            <input
              value={form.name}
              disabled={submitting}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="请输入凭证名称"
            />
          </FormField>

          <FormField label="平台" required error={errors.platform}>
            <select
              value={form.platform}
              disabled={submitting}
              onChange={(event) => handlePlatformChange(event.target.value)}
            >
              {platformOptions.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </FormField>

          {isCoupangForm ? (
            <FormField label="Vendor ID">
              <input
                value={form.vendorId}
                disabled={submitting}
                onChange={(event) => setForm({ ...form, vendorId: event.target.value })}
                placeholder="请输入 Coupang Vendor ID"
              />
            </FormField>
          ) : (
            <FormField label="Client ID" required error={errors.clientId}>
              <input
                value={form.clientId}
                disabled={submitting}
                onChange={(event) => setForm({ ...form, clientId: event.target.value })}
                placeholder="请输入 Naver Client ID"
              />
            </FormField>
          )}

          <FormField label="Market">
            <input
              value={form.market}
              disabled={submitting}
              onChange={(event) => setForm({ ...form, market: event.target.value })}
              placeholder="例如 KR"
            />
          </FormField>

          <FormField label="状态" required error={errors.status}>
            <select
              value={form.status}
              disabled={submitting}
              onChange={(event) => setForm({ ...form, status: event.target.value })}
            >
              {statusOptions.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </FormField>

          <FormField label="API 本地状态" required error={errors.authStatus}>
            <select
              value={form.authStatus}
              disabled={submitting}
              onChange={(event) => setForm({ ...form, authStatus: event.target.value })}
            >
              {authStatusOptions.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </FormField>

          {isCoupangForm ? (
            <FormField label="访问配置" required={!modal.record} error={errors.accessKeyInput}>
              <input
                type="password"
                value={form.accessKeyInput}
                disabled={submitting}
                onChange={(event) => setForm({ ...form, accessKeyInput: event.target.value })}
                placeholder={modal.record ? '留空则不更新' : '请输入访问配置'}
              />
            </FormField>
          ) : (
            <FormField label="访问配置">
              <input value="Naver 不适用" disabled readOnly />
            </FormField>
          )}

          <FormField
            label={isNaverForm ? '密钥配置 / Client Secret' : '密钥配置'}
            required={!modal.record}
            error={errors.secretKeyInput}
          >
            <input
              type="password"
              value={form.secretKeyInput}
              disabled={submitting}
              onChange={(event) => setForm({ ...form, secretKeyInput: event.target.value })}
              placeholder={modal.record ? '留空则不更新' : (isNaverForm ? '请输入 Naver Client Secret' : '请输入密钥配置')}
            />
          </FormField>

          {isNaverForm && (
            <>
              <FormField label="API Base">
                <input value={NAVER_DEFAULT_API_BASE} disabled readOnly />
              </FormField>
              <FormField label="Access Token">
                <input
                  type="password"
                  value={form.accessTokenInput}
                  disabled={submitting}
                  onChange={(event) => setForm({ ...form, accessTokenInput: event.target.value })}
                  placeholder={modal.record ? '留空则不更新' : '可选填写 Access Token'}
                />
              </FormField>
              <FormField label="Refresh Token">
                <input
                  type="password"
                  value={form.refreshTokenInput}
                  disabled={submitting}
                  onChange={(event) => setForm({ ...form, refreshTokenInput: event.target.value })}
                  placeholder={modal.record ? '留空则不更新' : '可选填写 Refresh Token'}
                />
              </FormField>
              <FormField label="Token 到期时间" error={errors.tokenExpiresAt}>
                <input
                  type="datetime-local"
                  value={form.tokenExpiresAt}
                  disabled={submitting}
                  onChange={(event) => setForm({ ...form, tokenExpiresAt: event.target.value })}
                />
              </FormField>
            </>
          )}

          <FormField label="API 备注">
            <input
              value={form.apiRemark}
              disabled={submitting}
              onChange={(event) => setForm({ ...form, apiRemark: event.target.value })}
              placeholder="填写本地备注，不要粘贴真实密钥或 Token"
            />
          </FormField>
        </div>
      </Modal>
    </>
  );
}
