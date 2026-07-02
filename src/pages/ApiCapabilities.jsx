import { useEffect, useMemo, useState } from 'react';
import EmptyState from '../components/common/EmptyState';
import PageHeader from '../components/common/PageHeader';
import TechnicalDetails from '../components/common/TechnicalDetails';
import { useStoreContext } from '../context/StoreContext';
import dataProvider, { isBackendSource } from '../services/dataProvider';
import {
  buildPlatformBusinessStatus,
  businessCapabilityTitle,
  findLatestNaverCapabilityIssue,
  CAPABILITY_LABELS,
  statusLabel,
} from '../utils/capabilityStatusMapper';
import { formatKstDateTimeWithLabel } from '../utils/time';

const emptyReadiness = {
  semanticNotice: 'mock 模式不维护后端连接检查记录。',
  platforms: [],
  storeBoundReadiness: null,
};

function BusinessCards({ cards }) {
  if (!cards.length) {
    return <EmptyState title="暂无平台连接状态" description="请选择 Naver 或 Coupang 店铺后查看连接状态。" />;
  }
  return (
    <div className="business-capability-grid">
      {cards.map((card) => (
        <article className={`business-capability-card ${card.tone || 'info'}`} key={card.key}>
          <div className="business-capability-head">
            <strong>{card.title}</strong>
            <span>{card.statusLabel}</span>
          </div>
          <p>{card.reason}</p>
          <small>{card.nextAction}</small>
        </article>
      ))}
    </div>
  );
}

function CapabilityTechnicalTable({ capabilities = [] }) {
  if (!capabilities.length) return null;
  return (
    <TechnicalDetails title="查看平台能力定义" description="这里保留接口路径、方法和文档记录，仅供管理员维护。">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>平台</th>
              <th>业务能力</th>
              <th>状态</th>
              <th>方法</th>
              <th>路径</th>
              <th>最近确认</th>
            </tr>
          </thead>
          <tbody>
            {capabilities.map((item) => (
              <tr key={item.id}>
                <td>{item.platform}</td>
                <td><strong>{CAPABILITY_LABELS[item.capabilityKey] || item.capabilityName}</strong><small className="cell-subtitle">{item.capabilityKey}</small></td>
                <td>{statusLabel(item.testStatus)}</td>
                <td>{item.method || '-'}</td>
                <td>{item.endpointPath || '-'}</td>
                <td>{formatKstDateTimeWithLabel(item.lastCheckedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TechnicalDetails>
  );
}

function ResultTechnicalTable({ results = [] }) {
  if (!results.length) return null;
  return (
    <TechnicalDetails title="查看店铺检测记录" description="技术检测记录默认折叠，不作为普通卖家的主判断依据。">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>业务能力</th>
              <th>状态</th>
              <th>错误码</th>
              <th>HTTP</th>
              <th>记录时间</th>
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <tr key={item.id}>
                <td>{CAPABILITY_LABELS[item.capabilityKey] || item.capabilityLabel || `Capability #${item.capabilityId}`}</td>
                <td>{statusLabel(item.testStatus, item.errorCode)}</td>
                <td>{item.errorCode || '-'}</td>
                <td>{item.httpStatus || '-'}</td>
                <td>{formatKstDateTimeWithLabel(item.testedAt || item.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TechnicalDetails>
  );
}

function ReadinessSummary({ readiness, capabilities, results }) {
  const storeBound = readiness?.storeBoundReadiness;
  const platform = String(storeBound?.rawPlatform || storeBound?.platform || '').toLowerCase();
  const isNaver = platform === 'naver';
  const title = isNaver ? 'Naver 连接资料' : platform === 'coupang' ? 'Coupang 连接资料' : '平台连接资料';
  const configured = Boolean(storeBound?.configured);
  const channelReady = Boolean(storeBound?.channelNoConfigured);
  const connectionIssue = isNaver
    ? findLatestNaverCapabilityIssue({
      capabilities,
      results,
      capabilityKeys: ['naver.token_auth', 'naver.seller_channels_read', 'naver.seller_account_read'],
    })
    : null;
  const authTone = connectionIssue ? connectionIssue.tone : configured ? 'success' : 'warning';
  const authStatus = connectionIssue ? connectionIssue.statusLabel : configured ? '正常' : '待确认';
  const authReason = connectionIssue ? connectionIssue.title : '授权状态正常。';
  const authNextAction = connectionIssue ? connectionIssue.description : '敏感连接信息已隐藏。';
  const channelTone = connectionIssue ? 'warning' : isNaver && channelReady ? 'success' : 'info';
  const channelStatus = connectionIssue ? '待确认' : isNaver ? (channelReady ? '成功' : '待确认') : '正常';
  const channelReason = connectionIssue
    ? '当前连接检测没有完成，暂时无法确认店铺频道状态。'
    : isNaver
      ? 'Naver 店铺频道状态只显示是否识别，不展示完整编号。'
      : 'Coupang 店铺连接资料已进入业务页面使用。';

  return (
    <section className="content-card">
      <div className="card-title">
        <div>
          <h2>{title}</h2>
          <p>默认只展示连接是否可用，不显示密钥、Token、请求头或完整店铺频道编号。</p>
        </div>
      </div>
      <div className="business-capability-grid compact">
        <article className={`business-capability-card ${configured ? 'success' : 'warning'}`}>
          <div className="business-capability-head">
            <strong>{title}</strong>
            <span>{configured ? '已配置' : '待配置'}</span>
          </div>
          <p>{configured ? '平台连接资料已配置。' : '请先补齐平台连接资料。'}</p>
        </article>
        <article className={`business-capability-card ${authTone}`}>
          <div className="business-capability-head">
            <strong>授权状态</strong>
            <span>{authStatus}</span>
          </div>
          <p>{authReason}</p>
          <small>{authNextAction}</small>
        </article>
        <article className={`business-capability-card ${channelTone}`}>
          <div className="business-capability-head">
            <strong>店铺连接</strong>
            <span>{channelStatus}</span>
          </div>
          <p>{channelReason}</p>
        </article>
        <article className="business-capability-card warning">
          <div className="business-capability-head">
            <strong>正式批量同步</strong>
            <span>未开放</span>
          </div>
          <p>商品或订单批量同步必须单独确认，不会因为连接成功而自动开放。</p>
        </article>
      </div>
      <TechnicalDetails
        items={[
          { label: 'credential_id', value: storeBound?.credentialId || '-' },
          { label: 'auth_status', value: storeBound?.authStatus || '-' },
          { label: 'real_api_test_enabled', value: readiness?.realApiTestEnabled },
          { label: 'real_api_write_enabled', value: readiness?.realApiWriteEnabled },
          { label: 'channel_no_configured', value: channelReady },
          ...(connectionIssue
            ? connectionIssue.technicalItems.map((item) => ({
              label: `connection_issue.${item.label}`,
              value: item.value,
            }))
            : []),
        ]}
      />
    </section>
  );
}

export default function ApiCapabilities() {
  const {
    selectedStoreId, selectedStore, stores, loading: storeLoading, error: storeError,
  } = useStoreContext();
  const [capabilities, setCapabilities] = useState([]);
  const [results, setResults] = useState([]);
  const [readiness, setReadiness] = useState(emptyReadiness);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const currentStore = useMemo(
    () => selectedStore || stores.find((item) => String(item.id) === String(selectedStoreId)),
    [selectedStore, selectedStoreId, stores],
  );

  useEffect(() => {
    if (storeLoading) return;
    if (storeError) {
      setError(storeError);
      setLoading(false);
      return;
    }
    if (!selectedStoreId) {
      setCapabilities([]);
      setResults([]);
      setReadiness(emptyReadiness);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');
    Promise.all([
      dataProvider.getApiCapabilities({ page: 1, pageSize: 100 }),
      dataProvider.getApiCapabilityResults({ storeId: selectedStoreId, page: 1, pageSize: 100 }),
      isBackendSource ? dataProvider.getApiCredentialReadiness({ storeId: selectedStoreId }) : Promise.resolve(emptyReadiness),
    ])
      .then(([capabilityResponse, resultResponse, readinessResponse]) => {
        const capabilityRows = capabilityResponse.data || capabilityResponse.items || [];
        const capabilityMap = new Map(capabilityRows.map((item) => [String(item.id), item]));
        const resultRows = (resultResponse.data || resultResponse.items || []).map((item) => ({
          ...item,
          capabilityKey: capabilityMap.get(String(item.capabilityId))?.capabilityKey,
        }));
        setCapabilities(capabilityRows);
        setResults(resultRows);
        setReadiness(readinessResponse || emptyReadiness);
      })
      .catch((requestError) => {
        setError(requestError.message || '平台连接状态加载失败。');
        setCapabilities([]);
        setResults([]);
        setReadiness(emptyReadiness);
      })
      .finally(() => setLoading(false));
  }, [selectedStoreId, storeError, storeLoading]);

  const platform = String(currentStore?.rawPlatform || currentStore?.platform || '').toLowerCase();
  const cards = buildPlatformBusinessStatus({
    platform,
    capabilities,
    results,
    readiness,
  });

  return (
    <>
      <PageHeader
        title="平台连接状态"
        description="用业务语言确认平台授权、店铺连接、商品读取、订单读取和批量同步保护状态。"
        actions={<span className="period-chip">技术详情默认折叠</span>}
      />

      {loading ? (
        <div className="table-state"><span className="spinner" />正在加载平台连接状态...</div>
      ) : error ? (
        <EmptyState title="平台连接状态加载失败" description={error} />
      ) : (
        <>
          <section className="content-card">
            <div className="card-title">
              <div>
                <h2>{businessCapabilityTitle(platform)}</h2>
                <p>默认展示卖家需要知道的状态：平台授权、店铺连接、商品读取、订单读取和正式批量同步是否开放。</p>
              </div>
              <span className="period-chip">{currentStore?.name || '当前店铺'}</span>
            </div>
            <BusinessCards cards={cards} />
          </section>

          <ReadinessSummary readiness={readiness} capabilities={capabilities} results={results} />

          <CapabilityTechnicalTable capabilities={capabilities} />
          <ResultTechnicalTable results={results} />
        </>
      )}
    </>
  );
}
