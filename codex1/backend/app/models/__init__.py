"""SQLAlchemy models are registered from this package."""

from app.models.api_credential import ApiCredential
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.appeal_case import AppealCase
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpSession, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.customer_inquiry import CustomerInquiry
from app.models.device_environment import DeviceEnvironment
from app.models.email_account import EmailAccount
from app.models.financial import PlatformSalesDetail, PlatformSettlementDetail
from app.models.important_email import ImportantEmail
from app.models.order import Order
from app.models.order_status_event import OrderStatusEvent
from app.models.operation_audit_log import OperationAuditLog
from app.models.platform_login_credential import PlatformLoginCredential
from app.models.product import Product
from app.models.pxg_naver_readonly import (
    PxgNaverOrderRecipientSecureRecord,
    PxgNaverReadonlyCustomerInquiry,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlyRecordState,
)
from app.models.shipping import (
    LogisticsInventoryItem,
    LogisticsInventoryMapping,
    ShippingExportBatch,
    ShippingExportBatchRow,
    ShippingTrackingImportBatch,
    ShippingTrackingImportRow,
    WarehouseShippingBatch,
    WarehouseShippingBatchOrder,
    WarehouseShippingApprovalGrant,
)
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.store import Store
from app.models.sync_log import SyncLog

__all__ = [
    "ApiCredential",
    "ApiCapabilityCheck",
    "ApiCapabilityTestResult",
    "AppealCase",
    "ErpPermission",
    "ErpRole",
    "ErpRolePermission",
    "ErpSession",
    "ErpStoreMembership",
    "ErpUser",
    "ErpUserSecurity",
    "CustomerInquiry",
    "DeviceEnvironment",
    "EmailAccount",
    "PlatformSalesDetail",
    "PlatformSettlementDetail",
    "ImportantEmail",
    "Order",
    "OrderStatusEvent",
    "OperationAuditLog",
    "PlatformLoginCredential",
    "Product",
    "PxgNaverOrderRecipientSecureRecord",
    "PxgNaverReadonlyCustomerInquiry",
    "PxgNaverReadonlyLogisticsRecord",
    "PxgNaverReadonlyRecordState",
    "LogisticsInventoryItem",
    "LogisticsInventoryMapping",
    "ShippingExportBatch",
    "ShippingExportBatchRow",
    "ShippingTrackingImportBatch",
    "ShippingTrackingImportRow",
    "WarehouseShippingBatch",
    "WarehouseShippingBatchOrder",
    "WarehouseShippingApprovalGrant",
    "SyncCheckpoint",
    "Store",
    "SyncLog",
]
