import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  adaptCustomerInquiry,
  adaptCustomerInquiryClassification,
  adaptCustomerInquiryConversation,
  adaptCustomerInquiryDetail,
  manualBatchSyncResult,
  naverCustomerInquiryRefresh,
} from '../src/services/adapters.js';

const backendApi = fs.readFileSync(new URL('../src/services/backendApi.js', import.meta.url), 'utf8');
const dataProvider = fs.readFileSync(new URL('../src/services/dataProvider.js', import.meta.url), 'utf8');
const customerPage = fs.readFileSync(new URL('../src/pages/CustomerService.jsx', import.meta.url), 'utf8');

assert.match(backendApi, /sendData\('post', '\/customer-inquiries\/naver\/refresh'/);
assert.match(backendApi, /`\/customer-inquiries\/\$\{encodeURIComponent\(readonlyId\)\}`/);
assert.match(backendApi, /store_id: storeId/);
assert.match(dataProvider, /refreshNaverCustomerInquiries/);
assert.match(dataProvider, /queryCustomerInquiryRows/);
assert.match(dataProvider, /item\.replyClassification/);
assert.match(customerPage, /getCustomerInquiryDetail/);
assert.match(customerPage, /!activeMessage\.readonlyId/);
assert.match(customerPage, /正在加载客服消息详情/);
assert.match(customerPage, /客服消息详情暂不可用/);
assert.match(customerPage, /conversation-message-\$\{message\.actor\}/);
assert.match(customerPage, /message\.actor === 'store'/);
assert.match(customerPage, /当前对话中没有店铺回复/);
assert.match(customerPage, /<option value="">全部<\/option>/);
assert.match(customerPage, /value: 'unanswered', label: '未回复'/);
assert.match(customerPage, /value: 'answered', label: '已回复'/);
assert.match(customerPage, /const platformReplyEnabled = false/);
assert.match(customerPage, /disabled=\{!platformReplyEnabled \|\| !row\.replyEnabled\}/);
assert.doesNotMatch(customerPage, /function statusLabel/);
assert.doesNotMatch(customerPage, /syncNaverCustomerInquiries\(/);

assert.equal(adaptCustomerInquiryClassification({ classification: 'unanswered', status: 'answered' }), 'unanswered');
assert.equal(adaptCustomerInquiryClassification({ reply_classification: 'answered' }), 'answered');
assert.equal(adaptCustomerInquiryClassification({ replyClassification: 'unanswered' }), 'unanswered');
assert.equal(adaptCustomerInquiryClassification({ status: 'answered' }), 'unknown');
assert.equal(adaptCustomerInquiryClassification({ status: 'closed' }), 'unknown');
assert.equal(adaptCustomerInquiryClassification({ status: 'done' }), 'unknown');
assert.equal(adaptCustomerInquiryClassification({ classification: 'Answered' }), 'unknown');
assert.equal(adaptCustomerInquiryClassification({ classification: ' answered ' }), 'unknown');
assert.equal(adaptCustomerInquiryClassification({ classification: 'invalid', reply_classification: 'answered' }), 'unknown');
assert.equal(adaptCustomerInquiryClassification({ content: '店铺已经回复', error: 'answered' }), 'unknown');

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
  id: 17,
  store_id: 1,
  platform: 'naver',
  title: 'decrypted title',
  content: 'decrypted message',
});
assert.equal(detail.content, 'decrypted message');
assert.equal(detail.title, 'decrypted title');
assert.equal(detail.detailLoaded, true);
assert.equal(detail.id, undefined);
assert.deepEqual(detail.conversation, []);

const conversation = adaptCustomerInquiryConversation([
  { actor: 'customer', content: '什么时候发货？', sent_at: '2026-07-17T09:10:00+09:00' },
  { actor: 'store', content: '今天安排发货。', sent_at: '2026-07-17T09:18:00+09:00' },
  { actor: 'system', content: 'must not render', sent_at: '2026-07-17T09:19:00+09:00' },
]);
assert.deepEqual(conversation, [
  { actor: 'customer', content: '什么时候发货？', sentAt: '2026-07-17T09:10:00+09:00' },
  { actor: 'store', content: '今天安排发货。', sentAt: '2026-07-17T09:18:00+09:00' },
]);

const conversationDetail = adaptCustomerInquiryDetail({
  classification: 'answered',
  conversation: [
    { actor: 'customer', content: '请问有货吗？', sent_at: '2026-07-17T10:00:00+09:00' },
    { actor: 'store', content: '有货。', sent_at: '2026-07-17T10:02:00+09:00' },
  ],
});
assert.equal(conversationDetail.replyClassification, 'answered');
assert.equal(conversationDetail.replyClassificationLabel, '已回复');
assert.equal(conversationDetail.conversation.length, 2);

const activeListRow = adaptCustomerInquiry({
  inquiry_id: 'pxg_naver_readonly:17',
  source: 'pxg_naver_readonly_local_v1',
  store_id: 1,
  store_name: 'Original Naver Store',
  summary: 'safe summary',
  order_context: { order_no: 'ORDER-17', product_name: 'Product 17' },
});
const mergedDetail = { ...activeListRow, ...detail };
assert.equal(mergedDetail.ticketNo, 'pxg_naver_readonly:17');
assert.equal(mergedDetail.store, 'Original Naver Store');
assert.equal(mergedDetail.orderNo, 'ORDER-17');
assert.equal(mergedDetail.productName, 'Product 17');
assert.equal(mergedDetail.content, 'decrypted message');

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
