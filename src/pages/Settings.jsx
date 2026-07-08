import { useEffect, useState } from 'react';
import FormField from '../components/common/FormField';
import PageHeader from '../components/common/PageHeader';
import SettingsSection from '../components/common/SettingsSection';
import StatusBadge from '../components/common/StatusBadge';
import ToggleSwitch from '../components/common/ToggleSwitch';
import mockApi from '../services/mockApi';

const tabs = [
  ['basic', '基础设置'],
  ['platforms', '平台设置'],
  ['notifications', '通知设置'],
  ['risks', '风险规则'],
  ['templates', '模板设置'],
];

function normalizeBasicSettings(data = {}) {
  return {
    ...data,
    systemName: data.systemName && !data.systemName.includes('环境管理') ? data.systemName : 'AI 多店铺运营工作台',
    defaultTimezone: data.defaultTimezone === 'Asia/Shanghai' ? 'Asia/Seoul' : (data.defaultTimezone || 'Asia/Seoul'),
    defaultCurrency: data.defaultCurrency || 'KRW',
  };
}

function platformStatusLabel(value) {
  const labels = {
    '정상': '正常运营',
    '확인 필요': '需要检查',
    '중지': '暂停使用',
  };
  return labels[value] || value || '正常运营';
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState('basic');
  const [basic, setBasic] = useState(null);
  const [platforms, setPlatforms] = useState([]);
  const [notifications, setNotifications] = useState(null);
  const [riskRules, setRiskRules] = useState(null);
  const [templates, setTemplates] = useState(null);
  const [errors, setErrors] = useState({});

  const load = async () => {
    const [basicData, platformData, notificationData, riskData, templateData] = await Promise.all([
      mockApi.getSystemSettings(),
      mockApi.getPlatformSettings(),
      mockApi.getNotificationSettings(),
      mockApi.getRiskRules(),
      mockApi.getTemplateSettings(),
    ]);
    setBasic(normalizeBasicSettings(basicData));
    setPlatforms(platformData);
    setNotifications(notificationData);
    setRiskRules(riskData);
    setTemplates(templateData);
  };

  useEffect(() => {
    load();
  }, []);

  const validateBasic = () => {
    const nextErrors = {};
    if (!basic.systemName.trim()) nextErrors.systemName = '系统名称不能为空';
    if (!Number.isInteger(Number(basic.defaultPageSize)) || Number(basic.defaultPageSize) <= 0) nextErrors.defaultPageSize = '每页默认条数必须为正整数';
    return nextErrors;
  };

  const validateRiskRules = () => {
    const nextErrors = {};
    Object.entries(riskRules).forEach(([key, rule]) => {
      if (!Number.isInteger(Number(rule.days)) || Number(rule.days) <= 0) nextErrors[key] = '提醒天数必须为正整数';
    });
    return nextErrors;
  };

  const validateTemplates = () => {
    const nextErrors = {};
    Object.entries(templates).forEach(([key, value]) => {
      if (!String(value).trim()) nextErrors[key] = '模板内容不能为空';
    });
    return nextErrors;
  };

  const saveCurrent = async () => {
    let nextErrors = {};
    if (activeTab === 'basic') {
      nextErrors = validateBasic();
      if (!Object.keys(nextErrors).length) await mockApi.updateSystemSettings({ ...basic, defaultPageSize: Number(basic.defaultPageSize) });
    }
    if (activeTab === 'platforms') {
      await mockApi.updatePlatformSettings(platforms);
    }
    if (activeTab === 'notifications') {
      await mockApi.updateNotificationSettings(notifications);
    }
    if (activeTab === 'risks') {
      nextErrors = validateRiskRules();
      if (!Object.keys(nextErrors).length) {
        const normalized = Object.fromEntries(Object.entries(riskRules).map(([key, value]) => [key, { ...value, days: Number(value.days) }]));
        await mockApi.updateRiskRules(normalized);
      }
    }
    if (activeTab === 'templates') {
      nextErrors = validateTemplates();
      if (!Object.keys(nextErrors).length) await mockApi.updateTemplateSettings(templates);
    }
    setErrors(nextErrors);
    if (!Object.keys(nextErrors).length) await load();
  };

  const resetAll = async () => {
    await mockApi.resetSystemSettings();
    setErrors({});
    await load();
  };

  if (!basic || !notifications || !riskRules || !templates) return null;

  return (
    <>
      <PageHeader
        title="系统设置"
        description="维护系统名称、韩国业务时间、默认币种、平台开关和提醒规则。高级排查信息不在普通页面展示。"
        actions={<><button type="button" className="button ghost" onClick={resetAll}>恢复默认设置</button><button type="button" className="button primary" onClick={saveCurrent}>保存设置</button></>}
      />

      <div className="tab-row">
        {tabs.map(([key, label]) => <button type="button" key={key} className={activeTab === key ? 'active' : ''} onClick={() => setActiveTab(key)}>{label}</button>)}
      </div>

      {activeTab === 'basic' && (
        <SettingsSection title="基础设置" description="系统基础显示口径，默认按韩国店铺运营使用。">
          <div className="settings-grid">
            <FormField label="系统名称" required error={errors.systemName}>
              <input value={basic.systemName} onChange={(event) => setBasic({ ...basic, systemName: event.target.value })} />
            </FormField>
            <FormField label="默认语言">
              <select value={basic.defaultLanguage} onChange={(event) => setBasic({ ...basic, defaultLanguage: event.target.value })}>
                <option value="zh-CN">中文</option>
                <option value="ko-KR">韩文</option>
              </select>
            </FormField>
            <FormField label="默认时区">
              <select value={basic.defaultTimezone} onChange={(event) => setBasic({ ...basic, defaultTimezone: event.target.value })}>
                <option value="Asia/Seoul">韩国时间（KST / Asia/Seoul）</option>
                <option value="Asia/Shanghai">中国时间（CST / Asia/Shanghai）</option>
              </select>
            </FormField>
            <FormField label="默认币种">
              <select value={basic.defaultCurrency} onChange={(event) => setBasic({ ...basic, defaultCurrency: event.target.value })}>
                <option value="KRW">韩元（KRW）</option>
                <option value="CNY">人民币（CNY）</option>
              </select>
            </FormField>
            <FormField label="每页默认条数" required error={errors.defaultPageSize}>
              <input type="number" value={basic.defaultPageSize} onChange={(event) => setBasic({ ...basic, defaultPageSize: event.target.value })} />
            </FormField>
          </div>
        </SettingsSection>
      )}

      {activeTab === 'platforms' && (
        <SettingsSection title="平台设置" description="控制平台是否在普通运营页面展示。API 设置仍在管理员可见范围内。">
          <div className="settings-stack">
            {platforms.map((item, index) => (
              <div className="settings-row" key={item.key}>
                <div>
                  <strong>{item.displayName || item.key}</strong>
                  <p>{item.note}</p>
                </div>
                <div className="mini-grid">
                  <ToggleSwitch checked={item.enabled} onChange={(checked) => {
                    const next = [...platforms];
                    next[index] = { ...item, enabled: checked };
                    setPlatforms(next);
                  }} label="启用平台" />
                  <FormField label="显示名称">
                    <input value={item.displayName} onChange={(event) => {
                      const next = [...platforms];
                      next[index] = { ...item, displayName: event.target.value };
                      setPlatforms(next);
                    }} />
                  </FormField>
                  <FormField label="平台状态">
                    <select value={item.status} onChange={(event) => {
                      const next = [...platforms];
                      next[index] = { ...item, status: event.target.value };
                      setPlatforms(next);
                    }}>
                      {['정상', '확인 필요', '중지'].map((status) => (
                        <option key={status} value={status}>{platformStatusLabel(status)}</option>
                      ))}
                    </select>
                  </FormField>
                  <StatusBadge value={platformStatusLabel(item.status)} />
                </div>
              </div>
            ))}
          </div>
        </SettingsSection>
      )}

      {activeTab === 'notifications' && (
        <SettingsSection title="通知设置" description="控制订单、库存、消息、邮箱和申诉提醒。">
          <div className="settings-stack">
            {[
              ['emailNotice', '邮箱通知'],
              ['appealReminder', '申诉提醒'],
              ['customerTimeoutReminder', '平台消息超时提醒'],
              ['orderExceptionReminder', '订单异常提醒'],
              ['environmentRiskReminder', '店铺连接风险提醒'],
            ].map(([key, label]) => (
              <div className="settings-row" key={key}>
                <div><strong>{label}</strong></div>
                <ToggleSwitch checked={notifications[key]} onChange={(checked) => setNotifications({ ...notifications, [key]: checked })} />
              </div>
            ))}
          </div>
        </SettingsSection>
      )}

      {activeTab === 'risks' && (
        <SettingsSection title="风险规则" description="配置提醒规则和提醒天数。">
          <div className="settings-stack">
            {[
              ['sameIpMultiAccount', '同 IP 多账号提醒'],
              ['emailReceiveFailure', '邮箱收信失败提醒'],
              ['cookieExpired', '登录状态过期提醒'],
              ['loginRegionAbnormal', '登录地区异常提醒'],
              ['appealDeadline', '申诉截止提醒'],
              ['salesAbnormalFluctuation', '销售异常波动提醒'],
            ].map(([key, label]) => (
              <div className="settings-row" key={key}>
                <div>
                  <strong>{label}</strong>
                  {errors[key] && <p>{errors[key]}</p>}
                </div>
                <div className="mini-grid">
                  <ToggleSwitch checked={riskRules[key].enabled} onChange={(checked) => setRiskRules({ ...riskRules, [key]: { ...riskRules[key], enabled: checked } })} label="启用" />
                  <FormField label="提醒天数">
                    <input type="number" value={riskRules[key].days} onChange={(event) => setRiskRules({ ...riskRules, [key]: { ...riskRules[key], days: event.target.value } })} />
                  </FormField>
                </div>
              </div>
            ))}
          </div>
        </SettingsSection>
      )}

      {activeTab === 'templates' && (
        <SettingsSection title="模板设置" description="维护平台消息、申诉资料和邮件备注模板。">
          <div className="settings-stack">
            {[
              ['customerReplyTemplate', '平台消息常用回复模板'],
              ['authenticityTemplate', '正品保证说明模板'],
              ['refundTemplate', '退款说明模板'],
              ['appealDocumentTemplate', '申诉资料清单模板'],
              ['platformNoteTemplate', '平台通知备注模板'],
            ].map(([key, label]) => (
              <FormField key={key} label={label} required error={errors[key]}>
                <textarea value={templates[key]} onChange={(event) => setTemplates({ ...templates, [key]: event.target.value })} />
              </FormField>
            ))}
          </div>
        </SettingsSection>
      )}
    </>
  );
}
