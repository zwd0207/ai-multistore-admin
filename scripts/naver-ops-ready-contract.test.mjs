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

includesAll('codex1/backend/app/schemas/shipping.py', [
  'ShippingShipmentWritebackExecuteRequest',
  'final_operator_confirmation: bool = False',
  'real_api_call_requested: bool = False',
]);

includesAll('codex1/backend/app/api/v1/endpoints/shipping.py', [
  '@router.post("/shipment-writeback/execute")',
  'execute_shipment_writeback',
]);

includesAll('codex1/backend/app/services/shipping_service.py', [
  'execute_naver_shipment_writeback',
  '/v1/pay-order/seller/product-orders/dispatch',
  'dispatchProductOrders',
  'deliveryCompanyCode',
  'trackingNumber',
  'manual_approval',
  'final_operator_confirmation',
  'platform_write',
  'raw_response_saved',
]);

includesAll('src/services/backendApi.js', [
  'syncNaverCustomerInquiries',
  "'/sync/customer-inquiries/naver'",
  'replyNaverCustomerInquiry',
  "'/sync/customer-inquiries/naver/reply'",
  'executeShippingShipmentWriteback',
  "'/shipping/shipment-writeback/execute'",
]);

includesAll('src/services/dataProvider.js', [
  'syncNaverCustomerInquiries',
  'replyNaverCustomerInquiry',
  'executeShippingShipmentWriteback',
]);

includesAll('src/pages/CustomerService.jsx', [
  '更新客户咨询',
  '提交到 Naver',
  '人工确认发送',
  'answerComment',
]);

includesAll('src/pages/ShippingAssistant.jsx', [
  '待确认平台回填',
  '确认发货信息',
  '我已确认店铺、订单、商品、快递公司和运单号无误。',
  '平台提交由受控流程另行执行。',
]);

console.log('naver ops ready contract checks passed');
