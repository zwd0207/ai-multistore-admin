import {
  accounts as accountSeed,
  appeals as appealSeed,
  customerTickets as customerTicketSeed,
  devices as deviceSeed,
  emails as emailSeed,
  environments as environmentSeed,
  orders as orderSeed,
  operationLogs as operationLogSeed,
  products as productSeed,
  replyTemplates as replyTemplateSeed,
  salesDaily as salesSeed,
  stores as storeSeed,
  systemSettings as systemSettingsSeed,
} from '../data/mockData';

const nowText = () => new Date().toLocaleString('zh-CN', { hour12: false });

const database = {
  stores: structuredClone(storeSeed),
  products: structuredClone(productSeed),
  orders: structuredClone(orderSeed),
  accounts: structuredClone(accountSeed),
  customerTickets: structuredClone(customerTicketSeed),
  appeals: structuredClone(appealSeed),
  devices: structuredClone(deviceSeed),
  emails: structuredClone(emailSeed),
  environments: structuredClone(environmentSeed),
  operationLogs: structuredClone(operationLogSeed),
  salesDaily: structuredClone(salesSeed),
  replyTemplates: structuredClone(replyTemplateSeed),
  systemSettings: structuredClone(systemSettingsSeed),
};

const delay = () => new Promise((resolve) => setTimeout(resolve, 200 + Math.random() * 300));

const includes = (value, keyword) => String(value ?? '').toLocaleLowerCase().includes(String(keyword ?? '').toLocaleLowerCase());
const normalizeDate = (date) => String(date ?? '').slice(0, 10);
const toNumber = (value) => Number(value ?? 0);
const netSales = (item) => toNumber(item.grossSales) - toNumber(item.couponAmount) - toNumber(item.refundAmount);

function paginate(rows, page = 1, pageSize = 10) {
  const start = (page - 1) * pageSize;
  return {
    data: rows.slice(start, start + pageSize),
    total: rows.length,
    page,
    pageSize,
  };
}

function listCore(resource, params = {}, options = {}) {
  const {
    keyword = '',
    status = '',
    platform = '',
    page = 1,
    pageSize = 5,
  } = params;

  const {
    statusKey = 'status',
    extraFilters,
  } = options;

  let rows = [...database[resource]];

  if (keyword) {
    rows = rows.filter((item) => Object.values(item).some((value) => includes(value, keyword)));
  }

  if (status) {
    rows = rows.filter((item) => item[statusKey] === status);
  }

  if (platform) {
    rows = rows.filter((item) => item.platform === platform);
  }

  if (extraFilters) {
    rows = extraFilters(rows, params);
  }

  return paginate(rows, page, pageSize);
}

async function list(resource, params = {}, options = {}) {
  await delay();
  return listCore(resource, params, options);
}

async function create(resource, payload, extra = {}) {
  await delay();
  const id = Date.now();
  const record = {
    ...payload,
    id,
    updatedAt: payload.updatedAt || nowText(),
    ...extra,
  };
  database[resource].unshift(record);
  return structuredClone(record);
}

async function update(resource, id, payload, options = {}) {
  await delay();
  const index = database[resource].findIndex((item) => item.id === id);
  if (index < 0) {
    throw new Error(options.notFoundMessage || '未找到要更新的数据');
  }

  const previous = database[resource][index];
  database[resource][index] = {
    ...previous,
    ...payload,
    id,
    updatedAt: payload.updatedAt || nowText(),
  };
  return structuredClone(database[resource][index]);
}

async function remove(resource, id, options = {}) {
  await delay();
  const index = database[resource].findIndex((item) => item.id === id);
  if (index < 0) {
    throw new Error(options.notFoundMessage || '未找到要删除的数据');
  }
  database[resource].splice(index, 1);
  return { success: true };
}

async function getDetail(resource, id, key = 'id') {
  await delay();
  const record = database[resource].find((item) => item[key] === id || item.id === id);
  if (!record) {
    throw new Error('未找到详情数据');
  }
  return structuredClone(record);
}

function filterByDate(rows, params = {}) {
  const { startDate = '', endDate = '' } = params;
  return rows.filter((item) => {
    const date = normalizeDate(item.date || item.deadline || item.updatedAt);
    if (startDate && date < startDate) return false;
    if (endDate && date > endDate) return false;
    return true;
  });
}

function salesFiltered(params = {}) {
  let rows = [...database.salesDaily];
  rows = filterByDate(rows, params);

  if (params.platform) {
    rows = rows.filter((item) => item.platform === params.platform);
  }

  if (params.store) {
    rows = rows.filter((item) => item.store === params.store);
  }

  if (params.keyword) {
    rows = rows.filter((item) => Object.values(item).some((value) => includes(value, params.keyword)));
  }

  return rows;
}

function parseStorePayload(payload) {
  if (!payload) return null;
  if (typeof payload === 'object') return payload;
  return { id: null, name: String(payload) };
}

function updateEmailCounters(account) {
  account.unreadCount = account.recentEmails.filter((item) => item.handledStatus === '未处理').length;
  account.importantCount = account.recentEmails.filter((item) => item.important).length;
  account.lastReceivedAt = account.recentEmails[0]?.receivedAt || account.lastReceivedAt;
}

async function getCustomerTickets(params = {}) {
  await delay();
  const { priority = '' } = params;

  return listCore('customerTickets', params, {
    extraFilters: (rows) => {
      let next = rows;
      if (priority) {
        next = next.filter((item) => item.priority === priority);
      }
      return next;
    },
  });
}

async function getCustomerTicketDetail(id) {
  return getDetail('customerTickets', id);
}

async function replyCustomerTicket(id, payload) {
  await delay();
  const ticket = database.customerTickets.find((item) => item.id === id);
  if (!ticket) {
    throw new Error('未找到要回复的咨询工单');
  }

  const reply = {
    id: Date.now(),
    author: payload.author || '客服专员',
    role: 'agent',
    content: payload.content,
    createdAt: nowText(),
  };

  ticket.replies = [...ticket.replies, reply];
  ticket.status = payload.nextStatus || '답변 완료';
  ticket.lastReplyAt = reply.createdAt;
  ticket.updatedAt = reply.createdAt;

  return structuredClone(ticket);
}

async function updateCustomerTicketStatus(id, status) {
  await delay();
  const ticket = database.customerTickets.find((item) => item.id === id);
  if (!ticket) {
    throw new Error('未找到要更新的咨询工单');
  }
  ticket.status = status;
  ticket.updatedAt = nowText();
  ticket.lastReplyAt = ticket.lastReplyAt || ticket.updatedAt;
  return structuredClone(ticket);
}

async function getReplyTemplates() {
  await delay();
  return structuredClone(database.replyTemplates);
}

async function getSalesSummary(params = {}) {
  await delay();
  const rows = salesFiltered(params);
  const totalSales = rows.reduce((sum, item) => sum + toNumber(item.grossSales), 0);
  const totalOrders = rows.reduce((sum, item) => sum + toNumber(item.orderCount), 0);
  const refundAmount = rows.reduce((sum, item) => sum + toNumber(item.refundAmount), 0);
  const couponAmount = rows.reduce((sum, item) => sum + toNumber(item.couponAmount), 0);
  const pendingOrders = rows.reduce((sum, item) => sum + toNumber(item.pendingOrders), 0);
  const totalNetSales = totalSales - couponAmount - refundAmount;

  return {
    totalSales,
    totalOrders,
    refundAmount,
    totalNetSales,
    averageOrderValue: totalOrders ? Math.round(totalSales / totalOrders) : 0,
    pendingOrders,
  };
}

async function getSalesRanking(params = {}) {
  await delay();
  const rows = salesFiltered(params);

  const byStore = Object.values(rows.reduce((acc, item) => {
    const key = item.store;
    const current = acc[key] || { name: key, platform: item.platform, sales: 0, orders: 0 };
    current.sales += toNumber(item.grossSales);
    current.orders += toNumber(item.orderCount);
    acc[key] = current;
    return acc;
  }, {})).sort((a, b) => b.sales - a.sales);

  const byPlatform = Object.values(rows.reduce((acc, item) => {
    const key = item.platform;
    const current = acc[key] || { name: key, sales: 0 };
    current.sales += toNumber(item.grossSales);
    acc[key] = current;
    return acc;
  }, {})).sort((a, b) => b.sales - a.sales);

  const byProduct = Object.values(rows.reduce((acc, item) => {
    const key = item.bestSeller;
    const current = acc[key] || { name: key, store: item.store, sales: 0, orders: 0 };
    current.sales += toNumber(item.grossSales);
    current.orders += toNumber(item.orderCount);
    acc[key] = current;
    return acc;
  }, {})).sort((a, b) => b.sales - a.sales);

  return {
    stores: byStore.slice(0, 5),
    platforms: byPlatform,
    products: byProduct.slice(0, 5),
  };
}

async function getSalesDetails(params = {}) {
  await delay();
  const rows = salesFiltered(params)
    .map((item) => ({ ...item, netSales: netSales(item) }))
    .sort((a, b) => b.date.localeCompare(a.date) || b.grossSales - a.grossSales);

  return paginate(rows, params.page || 1, params.pageSize || 6);
}

async function getSalesTrend(params = {}) {
  await delay();
  const rows = salesFiltered(params);
  const byDate = Object.values(rows.reduce((acc, item) => {
    const key = item.date;
    const current = acc[key] || { date: key, sales: 0, orders: 0, refund: 0 };
    current.sales += toNumber(item.grossSales);
    current.orders += toNumber(item.orderCount);
    current.refund += toNumber(item.refundAmount);
    acc[key] = current;
    return acc;
  }, {})).sort((a, b) => a.date.localeCompare(b.date));

  return structuredClone(byDate);
}

async function getAppeals(params = {}) {
  await delay();
  const { riskLevel = '', brand = '' } = params;

  return listCore('appeals', params, {
    extraFilters: (rows) => {
      let next = rows;
      if (riskLevel) {
        next = next.filter((item) => item.riskLevel === riskLevel);
      }
      if (brand) {
        next = next.filter((item) => item.brand === brand);
      }
      return next;
    },
  });
}

async function getDevices(params = {}) {
  await delay();
  const { deviceType = '', riskLevel = '', store = '' } = params;
  return listCore('devices', params, {
    extraFilters: (rows) => {
      let next = rows;
      if (deviceType) next = next.filter((item) => item.deviceType === deviceType);
      if (riskLevel) next = next.filter((item) => item.riskLevel === riskLevel);
      if (store) next = next.filter((item) => item.store === store);
      return next;
    },
  });
}

async function getDeviceDetail(id) {
  return getDetail('devices', id);
}

async function createDevice(payload) {
  const deviceNo = payload.deviceNo || `DV-${Date.now()}`;
  const record = await create('devices', {
    ...payload,
    deviceNo,
    boundStores: payload.boundStores || (payload.store ? [{ id: payload.storeId || null, name: payload.store, platform: payload.platform }] : []),
    boundAccounts: payload.boundAccounts || [],
    proxyInfo: payload.proxyInfo || {
      ipAddress: payload.ipAddress,
      region: payload.proxyRegion,
      provider: '未配置',
      rotationPolicy: '未配置',
    },
    browserEnv: payload.browserEnv || {
      browser: 'Chrome',
      os: 'Windows 11',
      fingerprint: `DV-${Date.now()}`,
      timezone: 'Asia/Seoul',
      language: 'ko-KR',
    },
    loginLogs: payload.loginLogs || [],
    usageLogs: payload.usageLogs || [],
    riskTips: payload.riskTips || ['新设备，尚无风险记录。'],
  });
  return record;
}

async function updateDevice(id, payload) {
  return update('devices', id, payload, { notFoundMessage: '未找到要更新的设备' });
}

async function updateDeviceStatus(id, status) {
  await delay();
  const device = database.devices.find((item) => item.id === id);
  if (!device) throw new Error('未找到要更新状态的设备');
  device.status = status;
  device.updatedAt = nowText();
  device.usageLogs = [
    {
      id: Date.now(),
      time: device.updatedAt,
      title: '设备状态更新',
      description: `设备状态已更新为 ${status}`,
      status,
    },
    ...device.usageLogs,
  ];
  return structuredClone(device);
}

async function bindDeviceStore(id, payload) {
  await delay();
  const device = database.devices.find((item) => item.id === id);
  if (!device) throw new Error('未找到要绑定店铺的设备');
  const store = parseStorePayload(payload);
  if (store?.name && !device.boundStores.some((item) => item.name === store.name)) {
    device.boundStores = [...device.boundStores, { id: store.id || null, name: store.name, platform: store.platform || device.platform }];
  }
  if (store?.name) {
    device.store = store.name;
    device.storeId = store.id || device.storeId;
  }
  return structuredClone(device);
}

async function unbindDeviceStore(id, storeId) {
  await delay();
  const device = database.devices.find((item) => item.id === id);
  if (!device) throw new Error('未找到要解绑店铺的设备');
  device.boundStores = device.boundStores.filter((item) => item.id !== storeId && item.name !== storeId);
  if (!device.boundStores.length) {
    device.store = '未绑定';
    device.storeId = null;
  } else {
    device.store = device.boundStores[0].name;
    device.storeId = device.boundStores[0].id;
  }
  return structuredClone(device);
}

async function getDeviceLogs(id) {
  await delay();
  const device = database.devices.find((item) => item.id === id);
  if (!device) throw new Error('未找到设备使用记录');
  return structuredClone(device.usageLogs);
}

async function getEmails(params = {}) {
  await delay();
  const { emailType = '', riskLevel = '', store = '' } = params;
  return listCore('emails', params, {
    extraFilters: (rows) => {
      let next = rows;
      if (emailType) next = next.filter((item) => item.purpose === emailType || item.recentEmails.some((mail) => mail.emailType === emailType));
      if (riskLevel) next = next.filter((item) => item.riskLevel === riskLevel);
      if (store) next = next.filter((item) => item.store === store);
      return next;
    },
  });
}

async function getEmailDetail(id) {
  return getDetail('emails', id);
}

async function createEmail(payload) {
  const emailNo = payload.emailNo || `EM-${Date.now()}`;
  const record = await create('emails', {
    ...payload,
    emailNo,
    recentEmails: payload.recentEmails || [],
    importantAlerts: payload.importantAlerts || [],
    riskLogs: payload.riskLogs || [],
  });
  const index = database.emails.findIndex((item) => item.id === record.id);
  updateEmailCounters(database.emails[index]);
  return structuredClone(database.emails[index]);
}

async function updateEmail(id, payload) {
  const updated = await update('emails', id, payload, { notFoundMessage: '未找到要更新的邮箱账号' });
  updateEmailCounters(updated);
  const index = database.emails.findIndex((item) => item.id === id);
  database.emails[index] = updated;
  return structuredClone(updated);
}

async function updateEmailStatus(id, status) {
  await delay();
  const account = database.emails.find((item) => item.id === id);
  if (!account) throw new Error('未找到要更新状态的邮箱账号');
  account.status = status;
  account.updatedAt = nowText();
  return structuredClone(account);
}

async function getRecentEmails(params = {}) {
  await delay();
  const { accountId, platform = '', store = '', keyword = '', emailType = '', page = 1, pageSize = 6 } = params;
  let mails = database.emails.flatMap((account) => account.recentEmails.map((mail) => ({
    ...mail,
    platform: account.platform,
    store: account.store,
    address: account.address,
  })));

  if (accountId) mails = mails.filter((item) => item.accountId === accountId);
  if (platform) mails = mails.filter((item) => item.platform === platform);
  if (store) mails = mails.filter((item) => item.store === store);
  if (emailType) mails = mails.filter((item) => item.emailType === emailType);
  if (keyword) mails = mails.filter((item) => Object.values(item).some((value) => includes(value, keyword)));

  mails = mails.sort((a, b) => b.receivedAt.localeCompare(a.receivedAt));
  return paginate(mails, page, pageSize);
}

async function markEmailImportant(id) {
  await delay();
  const account = database.emails.find((item) => item.recentEmails.some((mail) => mail.id === id));
  if (!account) throw new Error('未找到要标记的重要邮件');
  const mail = account.recentEmails.find((item) => item.id === id);
  mail.important = true;
  updateEmailCounters(account);
  return structuredClone(mail);
}

async function markEmailHandled(id) {
  await delay();
  const account = database.emails.find((item) => item.recentEmails.some((mail) => mail.id === id));
  if (!account) throw new Error('未找到要标记已处理的邮件');
  const mail = account.recentEmails.find((item) => item.id === id);
  mail.handledStatus = '已处理';
  updateEmailCounters(account);
  return structuredClone(mail);
}

async function getEnvironments(params = {}) {
  await delay();
  const { riskLevel = '', store = '', environmentType = '' } = params;
  return listCore('environments', params, {
    extraFilters: (rows) => {
      let next = rows;
      if (riskLevel) next = next.filter((item) => item.riskLevel === riskLevel);
      if (store) next = next.filter((item) => item.store === store);
      if (environmentType) next = next.filter((item) => item.environmentType === environmentType);
      return next;
    },
  });
}

async function getEnvironmentDetail(id) {
  return getDetail('environments', id);
}

async function createEnvironment(payload) {
  const record = await create('environments', {
    ...payload,
    environmentNo: payload.environmentNo || `ENV-${Date.now()}`,
    proxyInfo: payload.proxyInfo || {
      ipAddress: payload.ipAddress || '未配置',
      region: payload.ipRegion || '未知',
      provider: '未配置',
      rotationPolicy: '未配置',
    },
    browserInfo: payload.browserInfo || {
      browser: payload.browserType || 'Chrome',
      fingerprint: `ENV-${Date.now()}`,
      userAgent: 'Windows / Chrome',
      language: 'ko-KR',
    },
    loginLogs: payload.loginLogs || [],
    riskLogs: payload.riskLogs || [],
    actionLogs: payload.actionLogs || [],
  });
  return record;
}

async function updateEnvironment(id, payload) {
  return update('environments', id, payload, { notFoundMessage: '未找到要更新的环境' });
}

async function updateEnvironmentStatus(id, status) {
  await delay();
  const env = database.environments.find((item) => item.id === id);
  if (!env) throw new Error('未找到要更新状态的环境');
  env.status = status;
  env.updatedAt = nowText();
  env.actionLogs = [
    {
      id: Date.now(),
      time: env.updatedAt,
      title: '环境状态更新',
      description: `环境状态已更新为 ${status}`,
      status,
    },
    ...env.actionLogs,
  ];
  return structuredClone(env);
}

async function bindEnvironmentDevice(id, payload) {
  await delay();
  const env = database.environments.find((item) => item.id === id);
  if (!env) throw new Error('未找到要绑定设备的环境');
  env.deviceId = payload.deviceId || env.deviceId;
  env.deviceName = payload.deviceName || payload.name || env.deviceName;
  env.actionLogs = [
    {
      id: Date.now(),
      time: nowText(),
      title: '绑定设备',
      description: `已绑定设备 ${env.deviceName}`,
      status: '완료',
    },
    ...env.actionLogs,
  ];
  return structuredClone(env);
}

async function bindEnvironmentEmail(id, payload) {
  await delay();
  const env = database.environments.find((item) => item.id === id);
  if (!env) throw new Error('未找到要绑定邮箱的环境');
  env.emailId = payload.emailId || env.emailId;
  env.emailAddress = payload.emailAddress || payload.address || env.emailAddress;
  env.actionLogs = [
    {
      id: Date.now(),
      time: nowText(),
      title: '绑定邮箱',
      description: `已绑定邮箱 ${env.emailAddress}`,
      status: '완료',
    },
    ...env.actionLogs,
  ];
  return structuredClone(env);
}

async function getEnvironmentRiskLogs(id) {
  await delay();
  const env = database.environments.find((item) => item.id === id);
  if (!env) throw new Error('未找到环境风险记录');
  return structuredClone(env.riskLogs);
}

async function getEnvironmentActionLogs(id) {
  await delay();
  const env = database.environments.find((item) => item.id === id);
  if (!env) throw new Error('未找到环境操作记录');
  return structuredClone(env.actionLogs);
}

async function getAccounts(params = {}) {
  await delay();
  const { store = '', role = '', riskLevel = '' } = params;
  return listCore('accounts', params, {
    extraFilters: (rows) => {
      let next = rows;
      if (store) next = next.filter((item) => item.store === store);
      if (role) next = next.filter((item) => item.role === role);
      if (riskLevel) next = next.filter((item) => item.riskLevel === riskLevel);
      return next;
    },
  });
}

async function getAccountDetail(id) {
  return getDetail('accounts', id);
}

async function createAccount(payload) {
  const record = await create('accounts', {
    ...payload,
    accountNo: payload.accountNo || `AC-${Date.now()}`,
    loginLogs: payload.loginLogs || [],
    riskLogs: payload.riskLogs || [],
  });
  return record;
}

async function updateAccount(id, payload) {
  return update('accounts', id, payload, { notFoundMessage: '未找到要更新的账号' });
}

async function updateAccountStatus(id, status) {
  await delay();
  const account = database.accounts.find((item) => item.id === id);
  if (!account) throw new Error('未找到要更新状态的账号');
  account.status = status;
  account.updatedAt = nowText();
  account.loginLogs = [
    {
      id: Date.now(),
      time: account.updatedAt,
      title: '账号状态更新',
      account: account.loginId,
      location: account.platform,
      description: `账号状态已更新为 ${status}`,
      status: status === '사용중' || status === '정상' ? '성공' : '경고',
    },
    ...account.loginLogs,
  ];
  return structuredClone(account);
}

async function bindAccountStore(id, payload) {
  await delay();
  const account = database.accounts.find((item) => item.id === id);
  if (!account) throw new Error('未找到要绑定店铺的账号');
  account.store = payload.store || payload.name || account.store;
  account.storeId = payload.storeId || payload.id || account.storeId;
  return structuredClone(account);
}

async function bindAccountDevice(id, payload) {
  await delay();
  const account = database.accounts.find((item) => item.id === id);
  if (!account) throw new Error('未找到要绑定设备的账号');
  account.device = payload.device || payload.name || account.device;
  account.deviceId = payload.deviceId || payload.id || account.deviceId;
  return structuredClone(account);
}

async function bindAccountEmail(id, payload) {
  await delay();
  const account = database.accounts.find((item) => item.id === id);
  if (!account) throw new Error('未找到要绑定邮箱的账号');
  account.email = payload.email || payload.address || account.email;
  account.emailId = payload.emailId || payload.id || account.emailId;
  return structuredClone(account);
}

async function bindAccountEnvironment(id, payload) {
  await delay();
  const account = database.accounts.find((item) => item.id === id);
  if (!account) throw new Error('未找到要绑定环境的账号');
  account.environment = payload.environment || payload.name || account.environment;
  account.environmentId = payload.environmentId || payload.id || account.environmentId;
  return structuredClone(account);
}

async function getAccountLoginLogs(id) {
  await delay();
  const account = database.accounts.find((item) => item.id === id);
  if (!account) throw new Error('未找到账号登录记录');
  return structuredClone(account.loginLogs);
}

async function getAccountRiskLogs(id) {
  await delay();
  const account = database.accounts.find((item) => item.id === id);
  if (!account) throw new Error('未找到账号风险记录');
  return structuredClone(account.riskLogs);
}

async function getSystemSettings() {
  await delay();
  return structuredClone(database.systemSettings.basic);
}

async function updateSystemSettings(payload) {
  await delay();
  database.systemSettings.basic = { ...database.systemSettings.basic, ...payload };
  return structuredClone(database.systemSettings.basic);
}

async function resetSystemSettings() {
  await delay();
  database.systemSettings = structuredClone(systemSettingsSeed);
  return structuredClone(database.systemSettings);
}

async function getPlatformSettings() {
  await delay();
  return structuredClone(database.systemSettings.platforms);
}

async function updatePlatformSettings(payload) {
  await delay();
  database.systemSettings.platforms = structuredClone(payload);
  return structuredClone(database.systemSettings.platforms);
}

async function getNotificationSettings() {
  await delay();
  return structuredClone(database.systemSettings.notifications);
}

async function updateNotificationSettings(payload) {
  await delay();
  database.systemSettings.notifications = { ...database.systemSettings.notifications, ...payload };
  return structuredClone(database.systemSettings.notifications);
}

async function getRiskRules() {
  await delay();
  return structuredClone(database.systemSettings.riskRules);
}

async function updateRiskRules(payload) {
  await delay();
  database.systemSettings.riskRules = { ...database.systemSettings.riskRules, ...payload };
  return structuredClone(database.systemSettings.riskRules);
}

async function getTemplateSettings() {
  await delay();
  return structuredClone(database.systemSettings.templates);
}

async function updateTemplateSettings(payload) {
  await delay();
  database.systemSettings.templates = { ...database.systemSettings.templates, ...payload };
  return structuredClone(database.systemSettings.templates);
}

async function getOperationLogs(params = {}) {
  await delay();
  const { module = '', actionType = '', operator = '', riskLevel = '', startDate = '', endDate = '' } = params;
  let rows = listCore('operationLogs', params, {
    statusKey: 'status',
    extraFilters: (listRows) => {
      let next = [...listRows];
      if (module) next = next.filter((item) => item.module === module);
      if (actionType) next = next.filter((item) => item.actionType === actionType);
      if (operator) next = next.filter((item) => item.operator === operator);
      if (riskLevel) next = next.filter((item) => item.riskLevel === riskLevel);
      next = next.filter((item) => {
        const date = normalizeDate(item.time);
        if (startDate && date < startDate) return false;
        if (endDate && date > endDate) return false;
        return true;
      });
      return next;
    },
  });
  return rows;
}

async function getOperationLogDetail(id) {
  return getDetail('operationLogs', id);
}

async function markLogRisk(id, payload = {}) {
  await delay();
  const log = database.operationLogs.find((item) => item.id === id);
  if (!log) throw new Error('未找到要标记风险的日志');
  log.riskLevel = payload.riskLevel || '긴급';
  log.status = payload.status || '위험';
  log.riskNote = payload.riskNote || log.riskNote;
  return structuredClone(log);
}

async function getDashboardSummary() {
  await delay();
  const today = '2026-06-29';
  const todayOrders = database.orders.filter((item) => item.createdAt.startsWith(today));
  const todaySales = database.salesDaily.filter((item) => item.date === today);
  return {
    storeTotal: database.stores.length,
    productTotal: database.products.length,
    todayOrderCount: todayOrders.length,
    todaySalesAmount: todaySales.reduce((sum, item) => sum + item.grossSales, 0),
    pendingCustomers: database.customerTickets.filter((item) => item.status === '문의 대기').length,
    pendingAppeals: database.appeals.filter((item) => ['자료 준비중', '제출 대기', '심사중', '추가 자료 요청'].includes(item.status)).length,
    riskEnvironments: database.environments.filter((item) => ['위험 감지', '로그인 제한'].includes(item.status)).length,
    unreadImportantEmails: database.emails.reduce((sum, item) => sum + item.recentEmails.filter((mail) => mail.important && mail.handledStatus !== '已处理').length, 0),
  };
}

async function getDashboardRisks() {
  await delay();
  return [
    ...database.devices.filter((item) => ['높음', '긴급'].includes(item.riskLevel)).map((item) => ({ id: `device-${item.id}`, title: '高风险设备', description: item.name, status: item.riskLevel })),
    ...database.accounts.filter((item) => item.status === '로그인 제한').map((item) => ({ id: `account-${item.id}`, title: '登录限制账号', description: item.name, status: item.status })),
    ...database.emails.filter((item) => item.status === '수신 실패').map((item) => ({ id: `email-${item.id}`, title: '邮箱收件失败', description: item.address, status: item.status })),
    ...database.environments.filter((item) => ['위험 감지', '로그인 제한'].includes(item.status)).map((item) => ({ id: `env-${item.id}`, title: '环境风险检测', description: item.name, status: item.status })),
    ...database.appeals.filter((item) => item.deadline.startsWith('2026-06-30') || item.deadline.startsWith('2026-07-01')).map((item) => ({ id: `appeal-${item.id}`, title: '申诉截止提醒', description: `${item.caseNo} · ${item.deadline}`, status: '申诉截止提醒' })),
  ].slice(0, 8);
}

async function getDashboardTodos() {
  await delay();
  return [
    { id: 1, title: '待回复客服', description: `${database.customerTickets.filter((item) => item.status === '문의 대기').length} 条咨询等待回复`, status: '대기중' },
    { id: 2, title: '待提交申诉', description: `${database.appeals.filter((item) => item.status === '제출 대기').length} 个申诉待提交`, status: '대기중' },
    { id: 3, title: '待处理订单', description: `${database.orders.filter((item) => item.status === '待发货').length} 个订单待发货`, status: '대기중' },
    { id: 4, title: '待验证邮箱', description: `${database.emails.filter((item) => item.status === '인증 필요').length} 个邮箱待验证`, status: '인증 필요' },
    { id: 5, title: '待检查环境', description: `${database.environments.filter((item) => item.status === '점검 필요').length} 个环境需要检查`, status: '점검 필요' },
  ];
}

async function getDashboardActivities() {
  await delay();
  return {
    logs: structuredClone(database.operationLogs.slice(0, 4)),
    appeals: structuredClone(database.appeals.slice(0, 3).map((item) => ({ id: item.id, title: item.caseNo, description: item.reason, time: item.updatedAt, status: item.status }))),
    customers: structuredClone(database.customerTickets.slice(0, 3).map((item) => ({ id: item.id, title: item.customerName, description: item.summary, time: item.lastReplyAt, status: item.status }))),
    emails: structuredClone(database.emails.slice(0, 3).flatMap((item) => item.recentEmails.slice(0, 1).map((mail) => ({ id: mail.id, title: mail.title, description: mail.summary, time: mail.receivedAt, status: mail.handledStatus })))),
  };
}

async function getDashboardSalesTrend() {
  return getSalesTrend({ startDate: '2026-06-23', endDate: '2026-06-29' });
}

async function getAppealDetail(id) {
  return getDetail('appeals', id);
}

async function createAppeal(payload) {
  const timeline = payload.timeline?.length ? payload.timeline : [
    {
      id: Date.now() + 1,
      time: nowText(),
      title: '案件创建',
      description: payload.reason || '新申诉案件已录入系统。',
      status: payload.status || '자료 준비중',
    },
  ];

  const record = await create('appeals', payload, {
    caseNo: payload.caseNo || `AP-${Date.now()}`,
    timeline,
    requiredDocuments: payload.requiredDocuments?.length ? payload.requiredDocuments : ['구매 영수증', '정품 확인서', '소명서'],
    submittedDocuments: payload.submittedDocuments || [],
  });
  return record;
}

async function updateAppeal(id, payload) {
  return update('appeals', id, payload, { notFoundMessage: '未找到要更新的申诉案件' });
}

async function updateAppealStatus(id, status) {
  await delay();
  const record = database.appeals.find((item) => item.id === id);
  if (!record) {
    throw new Error('未找到要更新状态的申诉案件');
  }
  record.status = status;
  record.updatedAt = nowText();
  record.timeline = [
    ...record.timeline,
    {
      id: Date.now(),
      time: record.updatedAt,
      title: '状态更新',
      description: `案件状态已更新为 ${status}`,
      status,
    },
  ];
  return structuredClone(record);
}

async function addAppealTimeline(id, payload) {
  await delay();
  const record = database.appeals.find((item) => item.id === id);
  if (!record) {
    throw new Error('未找到要追加时间线的申诉案件');
  }
  const entry = {
    id: Date.now(),
    time: payload.time || nowText(),
    title: payload.title,
    description: payload.description,
    status: payload.status || record.status,
  };
  record.timeline = [...record.timeline, entry];
  record.updatedAt = entry.time;
  return structuredClone(entry);
}

export const mockApi = {
  getStores: (params) => list('stores', params),
  createStore: (data) => create('stores', data),
  updateStore: (id, data) => update('stores', id, data),
  deleteStore: (id) => remove('stores', id),

  getProducts: (params) => list('products', params),
  createProduct: (data) => create('products', data),
  updateProduct: (id, data) => update('products', id, data),
  deleteProduct: (id) => remove('products', id),

  getOrders: (params) => list('orders', params),
  createOrder: (data) => create('orders', data),
  updateOrder: (id, data) => update('orders', id, data),
  deleteOrder: (id) => remove('orders', id),

  getCustomers: (params) => getCustomerTickets(params),
  getCustomerTickets,
  getCustomerTicketDetail,
  replyCustomerTicket,
  updateCustomerTicketStatus,
  getReplyTemplates,

  getSalesSummary,
  getSalesRanking,
  getSalesDetails,
  getSalesTrend,
  getDashboardSummary,
  getDashboardRisks,
  getDashboardTodos,
  getDashboardActivities,
  getDashboardSalesTrend,

  getAppeals,
  getAppealDetail,
  createAppeal,
  updateAppeal,
  updateAppealStatus,
  addAppealTimeline,

  getDevices,
  getDeviceDetail,
  createDevice,
  updateDevice,
  updateDeviceStatus,
  bindDeviceStore,
  unbindDeviceStore,
  getDeviceLogs,

  getEmails,
  getEmailDetail,
  createEmail,
  updateEmail,
  updateEmailStatus,
  getRecentEmails,
  markEmailImportant,
  markEmailHandled,

  getEnvironments,
  getEnvironmentDetail,
  createEnvironment,
  updateEnvironment,
  updateEnvironmentStatus,
  bindEnvironmentDevice,
  bindEnvironmentEmail,
  getEnvironmentRiskLogs,
  getEnvironmentActionLogs,

  getAccounts,
  getAccountDetail,
  createAccount,
  updateAccount,
  updateAccountStatus,
  bindAccountStore,
  bindAccountDevice,
  bindAccountEmail,
  bindAccountEnvironment,
  getAccountLoginLogs,
  getAccountRiskLogs,

  getSystemSettings,
  updateSystemSettings,
  resetSystemSettings,
  getPlatformSettings,
  updatePlatformSettings,
  getNotificationSettings,
  updateNotificationSettings,
  getRiskRules,
  updateRiskRules,
  getTemplateSettings,
  updateTemplateSettings,

  getOperationLogs,
  getOperationLogDetail,
  markLogRisk,
};

export default mockApi;
