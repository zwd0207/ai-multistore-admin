import { useEffect, useMemo, useState } from 'react';
import DataTable from '../components/common/DataTable';
import EmptyState from '../components/common/EmptyState';
import FormField from '../components/common/FormField';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';

const STORAGE_KEY = 't13_store_onboarding_id';
const TERMINAL = new Set(['blocked', 'partially_synced', 'active_incremental', 'cancelled']);
const initialForm = { storeName: '', clientId: '', clientSecret: '', channelNo: '' };

function safeSessionId() {
  try { return sessionStorage.getItem(STORAGE_KEY) || ''; } catch { return ''; }
}

function saveSessionId(id) {
  try { if (id) sessionStorage.setItem(STORAGE_KEY, String(id)); else sessionStorage.removeItem(STORAGE_KEY); } catch { /* restricted storage */ }
}

function idempotencyKey() {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `t13-naver-${random}`;
}

function sourceState(value) {
  const item = value || {};
  const status = item.status || item.data_status || 'not_started';
  const count = item.created ?? item.count ?? item.total ?? item.items ?? null;
  return { status, count: Number.isFinite(Number(count)) ? Number(count) : null, reason: item.reason || item.error_code || '' };
}

function SourceGrid({ progress = {} }) {
  const sources = ['products', 'orders', 'customer_inquiries', 'logistics'];
  return <div className="onboarding-source-grid">{sources.map((source) => {
    const state = sourceState(progress[source]);
    const mandatory = source === 'products' || source === 'orders';
    return <div className="onboarding-source" key={source}>
      <strong>{source.replaceAll('_', ' ')}</strong>
      <StatusBadge value={state.status} />
      <span>{state.count === null ? 'count pending' : `${state.count} records`}</span>
      {state.reason ? <small>{state.reason}</small> : null}
      {mandatory ? <em>required</em> : <em>optional; not approved</em>}
    </div>;
  })}</div>;
}

const storeColumns = [
  { key: 'name', title: 'Store', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: 'Platform' },
  { key: 'status', title: 'Status', render: (value) => <StatusBadge value={value} /> },
  { key: 'updatedAt', title: 'Updated' },
];

export default function Stores() {
  const { stores, refreshStores, setSelectedStoreId } = useStoreContext();
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [onboarding, setOnboarding] = useState(null);
  const [pollingId, setPollingId] = useState(safeSessionId);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');

  const statusLabel = onboarding?.status || 'not submitted';
  const progress = onboarding?.progressSummary || {};
  const canResume = onboarding && ['retry_wait', 'blocked'].includes(onboarding.status);
  const blockedReason = onboarding?.lastErrorCode || onboarding?.validationSummary?.reason || 'Naver validation needs attention.';
  const restartPolling = (id) => {
    setPollingId('');
    globalThis.setTimeout(() => setPollingId(String(id)), 0);
  };

  async function readStatus(id) {
    const result = await dataProvider.getStoreOnboarding(id);
    setOnboarding(result);
    if (result?.storeId) {
      await refreshStores({ preferredStoreId: result.storeId });
      setSelectedStoreId(result.storeId);
      saveSessionId(result.id);
    }
    return result;
  }

  useEffect(() => {
    if (!isBackendSource) return undefined;
    const id = pollingId;
    if (!id) return undefined;
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const result = await dataProvider.getStoreOnboarding(id);
        if (cancelled) return;
        setOnboarding(result);
        if (result?.storeId) {
          await refreshStores({ preferredStoreId: result.storeId });
          setSelectedStoreId(result.storeId);
        }
        if (!TERMINAL.has(result?.status)) timer = setTimeout(poll, 1500);
      } catch (error) {
        if (!cancelled) setNotice(error.message || 'Unable to read onboarding status.');
      }
    };
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [pollingId, refreshStores, setSelectedStoreId]);

  const validate = () => {
    const next = {};
    if (!form.storeName.trim()) next.storeName = 'Store name is required.';
    if (!form.clientId.trim()) next.clientId = 'Client ID is required.';
    if (!form.clientSecret.trim()) next.clientSecret = 'Client secret is required.';
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!validate() || loading) return;
    setLoading(true); setNotice('');
    try {
      const result = await dataProvider.createStoreOnboarding({
        idempotency_key: idempotencyKey(), store_name: form.storeName.trim(),
        client_id: form.clientId.trim(), client_secret: form.clientSecret,
        channel_no: form.channelNo.trim() || null,
      });
      saveSessionId(result.id);
      restartPolling(result.id);
      setOnboarding(result);
      setForm(initialForm);
      setNotice('Onboarding submitted. The status below is durable and safe to resume after refresh.');
    } catch (error) { setNotice(error.message || 'Onboarding could not be submitted.'); }
    finally { setLoading(false); }
  };

  const resume = async () => {
    if (!onboarding?.id) return;
    setLoading(true); setNotice('Resuming onboarding...');
    try { setOnboarding(await dataProvider.resumeStoreOnboarding(onboarding.id)); restartPolling(onboarding.id); }
    catch (error) { setNotice(error.message || 'Onboarding could not be resumed.'); }
    finally { setLoading(false); }
  };

  const editBlocked = () => {
    if (!onboarding) return;
    setForm({ storeName: onboarding.requestedStoreName || '', clientId: '', clientSecret: '', channelNo: '' });
    setEditing(true);
    setErrors({});
    setNotice('Correct the connection details below. This updates the same onboarding record.');
  };

  const updateBlocked = async (event) => {
    event.preventDefault();
    if (!validate() || loading || !onboarding?.id) return;
    setLoading(true); setNotice('Updating the existing onboarding...');
    try {
      const result = await dataProvider.updateStoreOnboarding(onboarding.id, {
        store_name: form.storeName.trim(), client_id: form.clientId.trim(),
        client_secret: form.clientSecret, channel_no: form.channelNo.trim() || null,
      });
      setOnboarding(result);
      setEditing(false);
      restartPolling(onboarding.id);
      setNotice('Connection details updated. Validation is running again.');
    } catch (error) { setNotice(error.message || 'Connection details could not be updated.'); }
    finally { setLoading(false); }
  };

  const connectedStores = useMemo(() => stores.filter((store) => store.platform?.toLowerCase() === 'naver' || !store.platform), [stores]);

  return <>
    <PageHeader title="Stores" description="Connect one Naver store through a durable, read-only onboarding workflow." />
    <section className="content-card onboarding-card">
      <div className="card-title"><div><h2>Naver onboarding</h2><p>Products and orders are required. Inquiries and logistics remain explicitly partial until approved.</p></div><StatusBadge value={statusLabel} /></div>
      {onboarding?.status === 'blocked' ? <div className="onboarding-blocked" role="alert"><strong>Action needed: {blockedReason}</strong><span>Products and orders cannot be confirmed until Naver validation succeeds.</span><button className="button ghost" type="button" onClick={editBlocked}>Edit connection details</button></div> : null}
      <form className="onboarding-form" onSubmit={editing ? updateBlocked : submit} noValidate>
        <FormField label="Store name" required error={errors.storeName}><input value={form.storeName} onChange={(e) => setForm({ ...form, storeName: e.target.value })} autoComplete="off" /></FormField>
        <FormField label="Client ID" required error={errors.clientId}><input value={form.clientId} onChange={(e) => setForm({ ...form, clientId: e.target.value })} autoComplete="off" /></FormField>
        <FormField label="Client secret" required error={errors.clientSecret}><input type="password" value={form.clientSecret} onChange={(e) => setForm({ ...form, clientSecret: e.target.value })} autoComplete="new-password" /></FormField>
        <FormField label="Channel number"><input value={form.channelNo} onChange={(e) => setForm({ ...form, channelNo: e.target.value })} autoComplete="off" /></FormField>
        <div className="inline-action-group"><button className="button primary" type="submit" disabled={loading}>{loading ? 'Saving...' : editing ? 'Update and validate' : 'Submit onboarding'}</button>{canResume && !editing ? <button className="button ghost" type="button" onClick={resume} disabled={loading}>Resume</button> : null}{editing ? <button className="button ghost" type="button" onClick={() => setEditing(false)}>Cancel</button> : null}</div>
      </form>
      {notice ? <div className="form-info">{notice}</div> : null}
      {onboarding ? <div className="onboarding-progress" aria-live="polite"><div className="card-title"><h3>Progress: {statusLabel}</h3><span>{onboarding.lastErrorCode || 'No secret material is shown here.'}</span></div><SourceGrid progress={progress} /></div> : null}
    </section>
    <section className="content-card"><div className="card-title"><div><h2>Connected stores</h2><p>Existing stores remain available while onboarding runs.</p></div></div><DataTable columns={storeColumns} rows={connectedStores} rowKey="id" renderActions={(row) => <button type="button" onClick={() => setSelectedStoreId(row.id)}>Select</button>} /></section>
  </>;
}
