import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
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

includesAll('backend/app/schemas/order.py', [
  'delivery_company: str | None = None',
  'tracking_number: str | None = None',
  'logistics_trace_status: str | None = None',
]);

includesAll('backend/app/services/sync_service.py', [
  '"shippingAddress"',
  '"receiverTelNo2"',
  '"tel1"',
  '"deliveryCompany"',
  '"deliveryCompanyCode"',
  '"trackingNumber"',
  '"delivery_company"',
  '"tracking_number"',
]);

includesAll('backend/app/schemas/sync.py', [
  'class NaverOrderSingleRefreshRequest',
]);

includesAll('backend/app/api/v1/endpoints/sync.py', [
  '@router.post("/orders/naver/refresh-one")',
  'refresh_single_naver_order_detail',
]);

includesAll('backend/app/services/order_service.py', [
  'def get_order_logistics_timeline(',
  'shipping_tracking_import_rows',
  'local_tracking_trace',
  '实时快递轨迹暂未接入',
]);

includesAll('backend/app/api/v1/endpoints/orders.py', [
  '@router.get("/{order_id}/logistics-trace")',
  'get_order_logistics_trace',
]);

includesAll('src/services/backendApi.js', [
  'getOrderLogisticsTrace',
  '/orders/${orderId}/logistics-trace',
  'refreshSingleNaverOrderDetail',
]);

includesAll('src/services/dataProvider.js', [
  'getOrderLogisticsTrace',
  'mockOrderLogisticsTrace',
  'refreshSingleNaverOrderDetail',
]);

includesAll('src/services/adapters.js', [
  'deliveryCompany',
  'trackingNumber',
  'logisticsTraceStatus',
  'adaptOrderLogisticsTrace',
]);

includesAll('src/pages/Orders.jsx', [
  '查询物流轨迹',
  '物流轨迹',
  '刷新订单详情',
  'dataProvider.getOrderLogisticsTrace',
  'traceModal',
  '暂未提供实时轨迹',
]);

const backendDir = path.join(root, 'backend');
const backendPython = path.join(backendDir, '.venv', 'Scripts', 'python.exe');
const pythonBin = fs.existsSync(backendPython) ? backendPython : 'python';

execFileSync(pythonBin, ['-c', `
from datetime import datetime, timezone
from app.services.sync_service import _to_coupang_order_payload

payload = _to_coupang_order_payload({
    "orderId": 880011,
    "orderItems": [{"sellerProductName": "PXG test bag", "vendorItemName": "Black / OS", "shippingCount": 1}],
    "receiver": {
        "name": "Kim Ops",
        "safeNumber": "010-1234-5678",
        "addr1": "Seoul Gangnam",
        "addr2": "Test road 12",
        "postCode": "06123",
    },
    "deliveryCompanyName": "CJ대한통운",
    "invoiceNumber": "123456789012",
    "shipmentStatus": "DELIVERING",
    "orderedAt": "2026-07-09T10:00:00+09:00",
}, datetime(2026, 7, 9, 1, 0, tzinfo=timezone.utc))

assert payload["receiver_name"] == "Kim Ops", payload
assert payload["receiver_phone"] == "010-1234-5678", payload
assert payload["receiver_address"] == "Seoul Gangnam Test road 12", payload
assert payload["zip_code"] == "06123", payload
assert payload["raw_data"]["delivery_company"] == "CJ대한통운", payload
assert payload["raw_data"]["tracking_number"] == "123456789012", payload
assert payload["raw_data"]["platform_write"] is False, payload
`], { cwd: backendDir, stdio: 'pipe' });

execFileSync(pythonBin, ['-c', `
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base
from app.models.order import Order
from app.models.store import Store
from app.services import order_service, sync_service

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, future=True)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine, future=True)

with Session() as db:
    db.add(Store(id=901, name="Naver detail refresh contract store", platform="naver"))
    db.add(Order(
        id=9901,
        store_id=901,
        platform="naver",
        external_order_id="PO-9901",
        external_product_order_id="PO-9901",
        product_name="Old product",
        quantity=1,
        order_amount=0,
        currency="KRW",
        order_status="DELIVERING",
        ordered_at=datetime(2026, 7, 9, 1, 0, tzinfo=timezone.utc),
        source_type="naver_real_order_sync",
        raw_data={"mapping_version": "old"},
    ))
    db.commit()

    detail_payload = {
        "data": {
            "productOrders": [{
                "productOrder": {
                    "productOrderId": "PO-9901",
                    "orderId": "ORDER-9901",
                    "productName": "PXG detail product",
                    "quantity": 1,
                    "productOrderStatus": "DELIVERING",
                    "totalPaymentAmount": 499000,
                },
                "shippingAddress": {
                    "receiverName": "Kim Ops",
                    "tel1": "010-1234-5678",
                    "baseAddress": "Seoul Gangnam",
                    "detailedAddress": "Test road 12",
                    "zipCode": "06123",
                },
                "delivery": {
                    "deliveryCompany": "CJGLS",
                    "deliveryCompanyCode": "CJGLS",
                    "trackingNumber": "123456789012",
                },
            }]
        }
    }

    with patch.object(sync_service, "_ensure_naver_product_preview_credential", return_value=object()), \
        patch.object(sync_service, "_build_naver_token_context_from_credential", return_value={"api_base": "https://unit.test"}), \
        patch.object(sync_service.api_credential_readiness_service, "_request_naver_token_from_context", return_value=("unit-token", {})), \
        patch.object(sync_service, "_request_naver_order_detail_query", return_value={"success": True, "http_status": 200, "payload": detail_payload}):
        result = sync_service.refresh_single_naver_order_detail(db, store_id=901, order_id=9901)

    updated = db.scalar(select(Order).where(Order.id == 9901))
    assert result["status"] == "success", result
    assert result["updated_count"] == 1, result
    assert result["platform_write"] is False, result
    assert updated.receiver_phone == "010-1234-5678", updated.raw_data
    assert updated.receiver_address == "Seoul Gangnam Test road 12", updated.raw_data
    assert updated.raw_data["delivery_company"] == "CJ대한통운", updated.raw_data
    assert updated.raw_data["tracking_number"] == "123456789012", updated.raw_data
    serialized = order_service.serialize_order(updated)
    assert serialized["delivery_company"] == "CJ대한통운", serialized
    updated.raw_data["delivery_company"] = "CJGLS"
    serialized_from_legacy_code = order_service.serialize_order(updated)
    assert serialized_from_legacy_code["delivery_company"] == "CJ대한통운", serialized_from_legacy_code
`], { cwd: backendDir, stdio: 'pipe' });

console.log('order logistics contract checks passed');
