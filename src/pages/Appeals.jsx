import { useEffect, useMemo, useState } from 'react';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import PageHeader from '../components/common/PageHeader';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import SummaryCard from '../components/common/SummaryCard';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import { classifyCoreDataSource, getDangerousActionState } from '../utils/coreErpContract';

const appealTypes = [
  '正品审核',
  '知识产权 / 侵权',
  '结算冻结',
  '客户投诉',
  '平台处罚',
  '资料补充',
];

const statusOptions = ['资料准备中', '待人工提交', '审核中', '需补充资料', '已完成'];
const platformOptions = ['Naver', 'Coupang', 'Gmarket'];

function comparable(value) {
  return String(value ?? '').trim().toLowerCase();
}

function text(value, fallback = '-') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function typeLabel(value = '') {
  const normalized = comparable(value);
  if (normalized.includes('正品') || normalized.includes('authentic') || normalized.includes('상표')) return '正品审核';
  if (normalized.includes('侵权') || normalized.includes('知识产权') || normalized.includes('ip') || normalized.includes('商标')) return '知识产权 / 侵权';
  if (normalized.includes('结算') || normalized.includes('冻结')) return '结算冻结';
  if (normalized.includes('投诉') || normalized.includes('客户')) return '客户投诉';
  if (normalized.includes('处罚') || normalized.includes('限制')) return '平台处罚';
  return value ? '资料补充' : '资料补充';
}

function statusLabel(value = '') {
  const normalized = comparable(value);
  if (normalized.includes('자료 준비') || normalized.includes('准备')) return '资料准备中';
  if (normalized.includes('제출') || normalized.includes('待提交')) return '待人工提交';
  if (normalized.includes('심사') || normalized.includes('审核')) return '审核中';
  if (normalized.includes('추가') || normalized.includes('补充')) return '需补充资料';
  if (normalized.includes('完成') || normalized.includes('완료') || normalized.includes('resolved')) return '已完成';
  return value ? '资料准备中' : '资料准备中';
}

function nextAction(row = {}) {
  const status = statusLabel(row.status);
  if (status === '资料准备中') return '整理资料清单并人工复核';
  if (status === '待人工提交') return '人工到平台后台提交';
  if (status === '审核中') return '等待平台审核并记录进展';
  if (status === '需补充资料') return '补齐平台要求材料';
  return '归档资料和处理结果';
}

function normalizeCase(row = {}) {
  const sourceInfo = classifyCoreDataSource(row);
  const documents = row.requiredDocuments || row.required_documents || row.documentChecklist || [];
  return {
    ...row,
    caseNo: row.caseNo || row.case_no || `AP-${row.id}`,
    platform: text(row.platform || row.rawPlatform),
    store: text(row.store || row.storeName || row.store_name),
    type: typeLabel(row.appealType || row.type || row.caseType),
    product: text(row.productName || row.product || row.product_name, '未关联商品'),
    statusLabel: statusLabel(row.status),
    documentList: documents.length ? documents : ['营业执照', '采购凭证', '正品说明', '平台通知截图'],
    nextAction: row.actionRequired || row.nextAction || nextAction(row),
    deadline: row.deadline || row.deadlineAt || '',
    summary: text(row.reason || row.summary || row.platformNotice, '暂无摘要'),
    sourceInfo,
  };
}

function matches(row, query = {}) {
  const keyword = comparable(query.keyword);
  const haystack = [
    row.caseNo,
    row.platform,
    row.store,
    row.type,
    row.product,
    row.statusLabel,
    row.summary,
  ].map(comparable).join(' ');
  if (keyword && !haystack.includes(keyword)) return false;
  if (query.platform && comparable(row.platform) !== comparable(query.platform)) return false;
  if (query.type && row.type !== query.type) return false;
  if (query.status && row.statusLabel !== query.status) return false;
  return true;
}

const columns = [
  { key: 'caseNo', title: '案件编号', render: (value) => <strong>{value}</strong> },
  { key: 'type', title: '案件类型' },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'product', title: '商品' },
  { key: 'statusLabel', title: '状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'documentList', title: '资料清单', render: (value) => `${value.length} 项` },
  { key: 'nextAction', title: '下一步动作' },
  { key: 'deadline', title: '截止时间' },
];

export default function Appeals() {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', platform: '', type: '', status: '' });
  const [draft, setDraft] = useState(query);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeCase, setActiveCase] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (isBackendSource && storeLoading) return;
      setLoading(true);
      setError('');
      try {
        if (isBackendSource && storeError) throw new Error(storeError);
        const params = { page: 1, pageSize: 100 };
        if (isBackendSource && selectedStoreId) params.storeId = selectedStoreId;
        const result = await dataProvider.getAppealCases(params);
        const normalized = (result.data || result.items || []).map(normalizeCase).filter((item) => matches(item, query));
        if (!cancelled) setRows(normalized);
      } catch (requestError) {
        if (!cancelled) {
          setRows([]);
          setError(requestError.message || '申诉案件加载失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [query, selectedStoreId, storeLoading, storeError]);

  const summary = useMemo(() => ({
    total: rows.length,
    preparing: rows.filter((item) => item.statusLabel === '资料准备中').length,
    submit: rows.filter((item) => item.statusLabel === '待人工提交').length,
    supplement: rows.filter((item) => item.statusLabel === '需补充资料').length,
  }), [rows]);

  const dangerousState = getDangerousActionState('appeal_auto_submit');

  const search = () => setQuery({ ...draft });
  const reset = () => {
    const clean = { keyword: '', platform: '', type: '', status: '' };
    setDraft(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title="申诉中心"
        description="当前先做申诉案件和资料清单管理入口；自动提交申诉暂未开放，需人工到平台后台处理。"
        actions={(
          <>
            <button type="button" className="button primary" disabled>新建申诉案件（暂未开放）</button>
            <span className="period-chip">{dangerousState.label}</span>
          </>
        )}
      />

      <div className="summary-grid">
        <SummaryCard title="申诉案件" value={summary.total} note="本地资料管理" tone="info" />
        <SummaryCard title="资料准备中" value={summary.preparing} note="整理凭证和说明" tone={summary.preparing ? 'warning' : 'success'} />
        <SummaryCard title="待人工提交" value={summary.submit} note="需到平台后台处理" tone={summary.submit ? 'warning' : 'success'} />
        <SummaryCard title="需补充资料" value={summary.supplement} note="优先补齐" tone={summary.supplement ? 'danger' : 'success'} />
      </div>

      <section className="content-card">
        <div className="business-capability-grid compact">
          {appealTypes.map((type) => (
            <article className="business-capability-card info" key={type}>
              <div className="business-capability-head"><strong>{type}</strong><span>资料入口</span></div>
              <p>用于整理案件材料、下一步动作和人工处理记录。</p>
            </article>
          ))}
        </div>
      </section>

      <FilterPanel>
        <SearchBar
          value={draft.keyword}
          onChange={(keyword) => setDraft({ ...draft, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder="搜索案件编号、平台、店铺、商品或摘要"
        >
          <select value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platformOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value })}>
            <option value="">全部案件类型</option>
            {appealTypes.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
            <option value="">全部状态</option>
            {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </SearchBar>
      </FilterPanel>

      <section className="content-card">
        {error ? <EmptyState title="申诉案件加载失败" description={error} /> : null}
        {!error && !loading && !rows.length ? (
          <EmptyState
            title="当前没有申诉案件"
            description="可以先保留入口，后续新建功能开放后用于整理正品审核、侵权、结算冻结、客户投诉、平台处罚和资料补充案件。"
            actions={<button type="button" className="button primary" disabled>新建申诉案件（暂未开放）</button>}
          />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            renderActions={(row) => (
              <>
                <button type="button" onClick={() => setActiveCase(row)}>详情</button>
                <button type="button" disabled title="需人工到平台后台处理">提交申诉暂未开放</button>
              </>
            )}
          />
        )}
      </section>

      <DetailModal open={Boolean(activeCase)} title={activeCase ? `申诉详情 · ${activeCase.caseNo}` : '申诉详情'} onClose={() => setActiveCase(null)}>
        {activeCase ? (
          <>
            <div className="detail-grid">
              {[
                ['案件类型', activeCase.type],
                ['平台', activeCase.platform],
                ['店铺', activeCase.store],
                ['商品', activeCase.product],
                ['状态', <StatusBadge value={activeCase.statusLabel} />],
                ['下一步动作', activeCase.nextAction],
                ['数据来源', activeCase.sourceInfo.label],
                ['处理方式', '需人工到平台后台处理'],
              ].map(([label, value]) => (
                <div className="detail-item" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <section className="detail-section">
              <h3>资料清单</h3>
              <ul className="compact-list">
                {activeCase.documentList.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>
            <section className="detail-section">
              <h3>案件摘要</h3>
              <p>{activeCase.summary}</p>
              <p>{dangerousState.note}</p>
            </section>
          </>
        ) : <EmptyState title="暂无申诉详情" description="请选择案件查看详情。" />}
      </DetailModal>
    </>
  );
}
