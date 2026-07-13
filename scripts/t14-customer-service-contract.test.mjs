import assert from 'node:assert/strict';
import fs from 'node:fs';
import { adaptCustomerInquiry, adaptCustomerInquiryDetail, manualBatchSyncResult, naverCustomerInquiryRefresh } from '../src/services/adapters.js';

const backendApi = fs.readFileSync(new URL('../src/services/backendApi.js', import.meta.url), 'utf8');
const dataProvider = fs.readFileSync(new URL('../src/services/dataProvider.js', import.meta.url), 'utf8');
const customerPage = fs.readFileSync(new URL('../src/pages/CustomerService.jsx', import.meta.url), 'utf8');

assert.match(backendApi, /sendData\('post', '\/customer-inquiries\/naver\/refresh'/);
assert.match(backendApi, /`\/customer-inquiries\/\$\{encodeURIComponent\(readonlyId\)\}`/);
assert.match(backendApi, /store_id: storeId/);
assert.match(dataProvider, /refreshNaverCustomerInquiries/);
assert.match(customerPage, /getCustomerInquiryDetail/);
assert.match(customerPage, /!activeMessage\.readonlyId/);
assert.match(customerPage, /正在加载客服消息详情/);
assert.match(customerPage, /客服消息详情暂不可用/);
assert.doesNotMatch(customerPage, /syncNaverCustomerInquiries\(/);

const summary = adaptCustomerInquiry({
  inquiry_id: 'readonly-1',
  summary: 'delivery inquiry',
  content: 'must not appear in list summary',
  reply_enabled: false,
});
assert.equal(summary.content, 'delivery inquiry');
assert.equal(summary.replyEnabled, false);
const readonly = adaptCustomerInquiry({ inquiry_id: 'pxg_naver_readonly:17', source: 'pxg_naver_readonly_local_v1', summary: 'safe summary' });
assert.equal(readonly.readonlyId, '17');
assert.equal(readonly.detailLoaded, false);
const generic = adaptCustomerInquiry({ inquiry_id: 'generic:1', source: 'generic', summary: 'safe generic summary', content: 'raw content must not appear' });
assert.equal(generic.readonlyId, null);
assert.equal(generic.content, 'safe generic summary');
assert.equal(generic.detailLoaded, true);

const detail = adaptCustomerInquiryDetail({
  readonly_id: 'readonly-1',
  decrypted_content: 'decrypted message',
});
assert.equal(detail.content, 'decrypted message');
assert.equal(detail.detailLoaded, true);

const unavailable = manualBatchSyncResult({
  status: 'partial_success',
  items: [{ resource: 'customer_inquiries', platform: 'naver', status: 'failed', error_code: 'not_open', message: 'legacy technical error' }],
});
assert.equal(unavailable.items[0].status, 'skipped');
assert.equal(unavailable.items[0].message, '客服消息暂不可用');
assert.doesNotMatch(unavailable.items[0].message, /legacy technical error/);

const refreshed = naverCustomerInquiryRefresh({ status: 'success', message: '客服消息同步完成' });
assert.equal(refreshed.status, 'success');
assert.equal(naverCustomerInquiryRefresh({ status: 'not_open' }).status, 'unavailable');
console.log('T14 customer service contract checks passed');
