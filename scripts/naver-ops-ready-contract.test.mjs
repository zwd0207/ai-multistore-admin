import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function includesAll(file, phrases) {
  const text = read(file);
  for (const phrase of phrases) {
    assert.ok(text.includes(phrase), `${file} should include "${phrase}"`);
  }
}

includesAll('codex1/backend/app/schemas/sync.py', [
  'NaverCustomerInquirySyncRequest',
  'NaverCustomerInquiryReplyRequest',
  'answer_comment: str',
  'manual_approval: bool = False',
  'final_operator_confirmation: bool = False',
]);

includesAll('codex1/backend/app/api/v1/endpoints/sync.py', [
  '@router.post("/customer-inquiries/naver")',
  'sync_naver_customer_inquiries',
  '@router.post("/customer-inquiries/naver/reply")',
  'reply_naver_customer_inquiry',
]);

includesAll('codex1/backend/app/services/sync_service.py', [
  'NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE',
  '/v1/pay-user/inquiries',
  '/v1/pay-merchant/inquiries/',
  'answerComment',
  'manual_approval',
  'final_operator_confirmation',
  'platform_write',
  'raw_response_saved',
  'sync_naver_customer_inquiries',
  'reply_naver_customer_inquiry',
  'raw_response_saved": False',
]);

includesAll('src/services/backendApi.js', [
  'syncNaverCustomerInquiries',
  "'/sync/customer-inquiries/naver'",
  'replyNaverCustomerInquiry',
  "'/sync/customer-inquiries/naver/reply'",
  'confirmWarehouseShippingWriteback',
  "`/shipping/warehouse-batches/${batchId}/writeback`",
]);

includesAll('src/services/dataProvider.js', [
  'syncNaverCustomerInquiries',
  'replyNaverCustomerInquiry',
  "action: 'reconcile'",
  'real_api_call_requested: false',
]);

includesAll('src/pages/CustomerService.jsx', [
  '更新客户咨询',
  '提交到 Naver',
  '人工确认发送',
  'answerComment',
]);

includesAll('src/pages/ShippingAssistant.jsx', [
  '待确认平台回填',
  '申请平台回填审批',
  '确认执行平台回填',
  'writebackCapability',
  '平台结果待核对',
  '发货信息已成功回填平台。',
]);

const backendApi = read('src/services/backendApi.js');
const dataProvider = read('src/services/dataProvider.js');
const shippingPage = read('src/pages/ShippingAssistant.jsx');
assert.doesNotMatch(backendApi, /shipment-writeback\/execute|writeback-capability|executeShippingShipmentWriteback/);
assert.doesNotMatch(dataProvider, /executeShippingShipmentWriteback|toBackendShippingShipmentWriteback/);
assert.doesNotMatch(shippingPage, /healthCheck\(|getWarehouseShippingWritebackCapability|platformWriteEnabled/);
assert.match(shippingPage, /data-action="reconcile"/);
assert.match(shippingPage, /unknown \? <button[^>]+data-action="reconcile"/);
assert.match(shippingPage, /failed && capability\?\.allowedAction === 'approve'/);

console.log('naver ops ready contract checks passed');
