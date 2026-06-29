import { useEffect, useState } from 'react';
import DataTable from '../components/common/DataTable';
import DetailModal from '../components/common/DetailModal';
import EmptyState from '../components/common/EmptyState';
import FilterPanel from '../components/common/FilterPanel';
import FormField from '../components/common/FormField';
import Modal from '../components/common/Modal';
import PageHeader from '../components/common/PageHeader';
import Pagination from '../components/common/Pagination';
import SearchBar from '../components/common/SearchBar';
import StatusBadge from '../components/common/StatusBadge';
import Timeline from '../components/common/Timeline';
import mockApi from '../services/mockApi';

const platforms = ['Naver', 'Coupang', 'Gmarket', '11街', '옥션'];
const statuses = ['자료 준비중', '제출 대기', '제출 완료', '심사중', '추가 자료 요청', '승인', '반려', '판매중지', '정산보류'];
const riskLevels = ['낮음', '보통', '높음', '긴급'];
const brands = ['ECCO', 'Titleist', 'Sulwhasoo', 'MLB'];
const documentOptions = ['구매 영수증', '카드 결제 내역', '정품 확인서', '매장 사진', '유통 경로 설명서', '사업자등록증', '법인 정보', '소명서'];

const formatWon = (value) => `${Number(value || 0).toLocaleString()}원`;

const columns = [
  { key: 'caseNo', title: '案件编号', render: (value) => <strong>{value}</strong> },
  { key: 'platform', title: '平台' },
  { key: 'store', title: '店铺' },
  { key: 'brand', title: '品牌' },
  { key: 'productName', title: '商品名' },
  { key: 'appealType', title: '申诉类型' },
  { key: 'status', title: '当前状态', render: (value) => <StatusBadge value={value} /> },
  { key: 'riskLevel', title: '风险等级', render: (value) => <StatusBadge value={value} /> },
  { key: 'amount', title: '涉及金额', render: (value) => formatWon(value) },
  { key: 'deadline', title: '截止时间' },
  { key: 'updatedAt', title: '最近更新时间' },
];

const initialCaseForm = {
  caseNo: '',
  platform: '',
  store: '',
  brand: '',
  productName: '',
  appealType: '',
  reason: '',
  status: '자료 준비중',
  riskLevel: '보통',
  amount: '',
  deadline: '',
  platformNotice: '',
  remarks: '',
};

const initialProgressForm = {
  status: '자료 준비중',
  timelineTitle: '',
  timelineDescription: '',
  submittedDocuments: '',
  remarks: '',
};

export default function Appeals() {
  const [query, setQuery] = useState({ keyword: '', platform: '', status: '', riskLevel: '', brand: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [loading, setLoading] = useState(true);
  const [detailOpen, setDetailOpen] = useState(false);
  const [caseModal, setCaseModal] = useState({ open: false, editing: null });
  const [progressOpen, setProgressOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [caseForm, setCaseForm] = useState(initialCaseForm);
  const [progressForm, setProgressForm] = useState(initialProgressForm);
  const [errors, setErrors] = useState({});

  const load = async (nextQuery = query) => {
    setLoading(true);
    try {
      const response = await mockApi.getAppeals(nextQuery);
      setResult(response);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [query]);

  const openDetail = async (row) => {
    const nextDetail = await mockApi.getAppealDetail(row.id);
    setDetail(nextDetail);
    setDetailOpen(true);
  };

  const openCreateModal = () => {
    setCaseForm(initialCaseForm);
    setErrors({});
    setCaseModal({ open: true, editing: null });
  };

  const openEditModal = (row) => {
    setCaseForm({
      caseNo: row.caseNo,
      platform: row.platform,
      store: row.store,
      brand: row.brand,
      productName: row.productName,
      appealType: row.appealType,
      reason: row.reason,
      status: row.status,
      riskLevel: row.riskLevel,
      amount: row.amount,
      deadline: row.deadline,
      platformNotice: row.platformNotice || '',
      remarks: row.remarks || '',
    });
    setErrors({});
    setCaseModal({ open: true, editing: row });
  };

  const openProgressModal = async (row) => {
    const nextDetail = await mockApi.getAppealDetail(row.id);
    setDetail(nextDetail);
    setProgressForm({
      status: nextDetail.status,
      timelineTitle: '',
      timelineDescription: '',
      submittedDocuments: nextDetail.submittedDocuments.join(', '),
      remarks: nextDetail.remarks || '',
    });
    setErrors({});
    setProgressOpen(true);
  };

  const validateCaseForm = () => {
    const nextErrors = {};
    ['platform', 'store', 'brand', 'productName', 'appealType', 'reason', 'status', 'riskLevel', 'deadline'].forEach((key) => {
      if (!String(caseForm[key] ?? '').trim()) {
        nextErrors[key] = '该字段不能为空';
      }
    });
    if (!caseForm.amount || Number(caseForm.amount) <= 0) {
      nextErrors.amount = '涉及金额必须大于 0';
    }
    return nextErrors;
  };

  const saveCase = async () => {
    const nextErrors = validateCaseForm();
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const payload = {
      ...caseForm,
      amount: Number(caseForm.amount),
      requiredDocuments: documentOptions.filter((item) => includesReason(caseForm.reason, item)),
    };

    if (caseModal.editing) {
      await mockApi.updateAppeal(caseModal.editing.id, payload);
    } else {
      await mockApi.createAppeal(payload);
    }

    setCaseModal({ open: false, editing: null });
    await load();
  };

  const saveProgress = async () => {
    const nextErrors = {};
    if (!progressForm.status) nextErrors.status = '请选择状态';
    if (!progressForm.timelineTitle.trim()) nextErrors.timelineTitle = '请输入进度标题';
    if (!progressForm.timelineDescription.trim()) nextErrors.timelineDescription = '请输入进度说明';

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    const documents = progressForm.submittedDocuments
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);

    await mockApi.updateAppealStatus(detail.id, progressForm.status);
    await mockApi.updateAppeal(detail.id, { submittedDocuments: documents, remarks: progressForm.remarks });
    await mockApi.addAppealTimeline(detail.id, {
      title: progressForm.timelineTitle,
      description: progressForm.timelineDescription,
      status: progressForm.status,
    });

    setProgressOpen(false);
    if (detailOpen) {
      setDetail(await mockApi.getAppealDetail(detail.id));
    }
    await load();
  };

  return (
    <>
      <PageHeader
        title="申诉管理"
        description="管理多平台申诉案件、资料准备、提交进度与时间线记录。"
        actions={<button className="button primary" onClick={openCreateModal}>新增申诉案件</button>}
      />

      <FilterPanel>
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={() => setQuery({ ...draftQuery, page: 1 })}
          onReset={() => {
            const clean = { keyword: '', platform: '', status: '', riskLevel: '', brand: '', page: 1, pageSize: 5 };
            setDraftQuery(clean);
            setQuery(clean);
          }}
          placeholder="搜索案件编号、平台、店铺、商品名、品牌或申诉原因"
        >
          <select value={draftQuery.platform} onChange={(event) => setDraftQuery({ ...draftQuery, platform: event.target.value })}>
            <option value="">全部平台</option>
            {platforms.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.status} onChange={(event) => setDraftQuery({ ...draftQuery, status: event.target.value })}>
            <option value="">全部状态</option>
            {statuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.riskLevel} onChange={(event) => setDraftQuery({ ...draftQuery, riskLevel: event.target.value })}>
            <option value="">全部风险等级</option>
            {riskLevels.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draftQuery.brand} onChange={(event) => setDraftQuery({ ...draftQuery, brand: event.target.value })}>
            <option value="">全部品牌</option>
            {brands.map((item) => <option key={item}>{item}</option>)}
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
              <button onClick={() => openProgressModal(row)}>进度</button>
            </>
          )}
        />
        <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
      </section>

      <DetailModal open={detailOpen} title={detail ? `案件详情 · ${detail.caseNo}` : '案件详情'} onClose={() => setDetailOpen(false)}>
        {detail ? (
          <>
            <section className="detail-section">
              <h3>基础案件信息</h3>
              <div className="detail-grid">
                <div className="detail-item"><span>平台</span><strong>{detail.platform}</strong></div>
                <div className="detail-item"><span>店铺</span><strong>{detail.store}</strong></div>
                <div className="detail-item"><span>品牌</span><strong>{detail.brand}</strong></div>
                <div className="detail-item"><span>申诉类型</span><strong>{detail.appealType}</strong></div>
                <div className="detail-item"><span>当前处理状态</span><strong><StatusBadge value={detail.status} /></strong></div>
                <div className="detail-item"><span>风险等级</span><strong><StatusBadge value={detail.riskLevel} /></strong></div>
                <div className="detail-item"><span>涉及金额</span><strong>{formatWon(detail.amount)}</strong></div>
                <div className="detail-item"><span>截止时间</span><strong>{detail.deadline}</strong></div>
              </div>
            </section>

            <section className="detail-section">
              <h3>商品信息</h3>
              <div className="detail-grid">
                <div className="detail-item"><span>商品名</span><strong>{detail.productName}</strong></div>
                <div className="detail-item"><span>申诉原因</span><strong>{detail.reason}</strong></div>
              </div>
            </section>

            <section className="detail-section">
              <h3>平台通知内容</h3>
              <p>{detail.platformNotice}</p>
            </section>

            <section className="detail-section">
              <h3>需要准备的资料清单</h3>
              <div className="badge-row">
                {detail.requiredDocuments.map((item) => <StatusBadge key={item} value={item} />)}
              </div>
            </section>

            <section className="detail-section">
              <h3>已提交资料清单</h3>
              {detail.submittedDocuments.length ? (
                <div className="badge-row">
                  {detail.submittedDocuments.map((item) => <StatusBadge key={item} value={item} />)}
                </div>
              ) : <EmptyState title="尚未提交资料" description="当前案件还没有已提交资料记录。" />}
            </section>

            <section className="detail-section">
              <h3>上传资料记录预留</h3>
              <div className="upload-shell">
                前端结构已预留，后续可接入真实上传接口、文件列表和回传凭证。
              </div>
            </section>

            <section className="detail-section">
              <h3>申诉时间线展示</h3>
              <Timeline items={detail.timeline} />
            </section>

            <section className="detail-section">
              <h3>备注</h3>
              <p>{detail.remarks || '暂无备注'}</p>
            </section>
          </>
        ) : <EmptyState title="暂无案件详情" description="请选择一条申诉案件查看详细内容。" />}
      </DetailModal>

      <Modal
        open={caseModal.open}
        title={caseModal.editing ? '编辑申诉案件' : '新增申诉案件'}
        onClose={() => setCaseModal({ open: false, editing: null })}
        onConfirm={saveCase}
        confirmText={caseModal.editing ? '保存修改' : '创建案件'}
        width="min(980px, 94vw)"
      >
        <div className="form-grid">
          <FormField label="案件编号" error={errors.caseNo}>
            <input value={caseForm.caseNo} placeholder="留空则自动生成" onChange={(event) => setCaseForm({ ...caseForm, caseNo: event.target.value })} />
          </FormField>
          <FormField label="平台" required error={errors.platform}>
            <select value={caseForm.platform} onChange={(event) => setCaseForm({ ...caseForm, platform: event.target.value })}>
              <option value="">请选择平台</option>
              {platforms.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="店铺" required error={errors.store}>
            <input value={caseForm.store} onChange={(event) => setCaseForm({ ...caseForm, store: event.target.value })} />
          </FormField>
          <FormField label="品牌" required error={errors.brand}>
            <select value={caseForm.brand} onChange={(event) => setCaseForm({ ...caseForm, brand: event.target.value })}>
              <option value="">请选择品牌</option>
              {brands.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="商品名" required error={errors.productName}>
            <input value={caseForm.productName} onChange={(event) => setCaseForm({ ...caseForm, productName: event.target.value })} />
          </FormField>
          <FormField label="申诉类型" required error={errors.appealType}>
            <input value={caseForm.appealType} onChange={(event) => setCaseForm({ ...caseForm, appealType: event.target.value })} />
          </FormField>
          <FormField label="当前状态" required error={errors.status}>
            <select value={caseForm.status} onChange={(event) => setCaseForm({ ...caseForm, status: event.target.value })}>
              {statuses.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="风险等级" required error={errors.riskLevel}>
            <select value={caseForm.riskLevel} onChange={(event) => setCaseForm({ ...caseForm, riskLevel: event.target.value })}>
              {riskLevels.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="涉及金额" required error={errors.amount}>
            <input type="number" value={caseForm.amount} onChange={(event) => setCaseForm({ ...caseForm, amount: event.target.value })} />
          </FormField>
          <FormField label="截止时间" required error={errors.deadline}>
            <input value={caseForm.deadline} placeholder="2026-07-03 18:00" onChange={(event) => setCaseForm({ ...caseForm, deadline: event.target.value })} />
          </FormField>
        </div>
        <FormField label="申诉原因" required error={errors.reason}>
          <textarea value={caseForm.reason} onChange={(event) => setCaseForm({ ...caseForm, reason: event.target.value })} />
        </FormField>
        <FormField label="平台通知内容">
          <textarea value={caseForm.platformNotice} onChange={(event) => setCaseForm({ ...caseForm, platformNotice: event.target.value })} />
        </FormField>
        <FormField label="备注">
          <textarea value={caseForm.remarks} onChange={(event) => setCaseForm({ ...caseForm, remarks: event.target.value })} />
        </FormField>
      </Modal>

      <Modal
        open={progressOpen}
        title={detail ? `编辑申诉进度 · ${detail.caseNo}` : '编辑申诉进度'}
        onClose={() => setProgressOpen(false)}
        onConfirm={saveProgress}
        confirmText="保存进度"
        width="min(900px, 94vw)"
      >
        <div className="form-grid">
          <FormField label="当前状态" required error={errors.status}>
            <select value={progressForm.status} onChange={(event) => setProgressForm({ ...progressForm, status: event.target.value })}>
              {statuses.map((item) => <option key={item}>{item}</option>)}
            </select>
          </FormField>
          <FormField label="已提交资料（逗号分隔）">
            <input value={progressForm.submittedDocuments} onChange={(event) => setProgressForm({ ...progressForm, submittedDocuments: event.target.value })} placeholder="구매 영수증, 사업자등록증" />
          </FormField>
        </div>
        <FormField label="进度标题" required error={errors.timelineTitle}>
          <input value={progressForm.timelineTitle} onChange={(event) => setProgressForm({ ...progressForm, timelineTitle: event.target.value })} placeholder="例如：已补充采购发票" />
        </FormField>
        <FormField label="进度说明" required error={errors.timelineDescription}>
          <textarea value={progressForm.timelineDescription} onChange={(event) => setProgressForm({ ...progressForm, timelineDescription: event.target.value })} />
        </FormField>
        <FormField label="备注">
          <textarea value={progressForm.remarks} onChange={(event) => setProgressForm({ ...progressForm, remarks: event.target.value })} />
        </FormField>
      </Modal>
    </>
  );
}

function includesReason(reason, document) {
  const rules = {
    영수증: ['购买', '采购', '供货'],
    카드: ['支付', '结算', '退款'],
    정품: ['正品', '商标', '品牌'],
    매장: ['图片', '照片', '门店'],
    유통: ['渠道', '供货', '流通'],
    사업자: ['主体', '营业', '公司'],
    법인: ['法人', '公司'],
    소명서: ['申诉', '限制', '说明'],
  };

  const tokens = Object.entries(rules).find(([key]) => document.includes(key))?.[1] || [];
  return tokens.some((token) => reason.includes(token));
}
