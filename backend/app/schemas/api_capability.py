from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


TEST_STATUSES = {
    "not_tested",
    "planned",
    "tested_success",
    "tested_failed",
    "unavailable",
    "permission_required",
}
TEST_MODES = {"docs_only", "manual", "mock", "sandbox", "real_readonly"}
ORDINARY_STORE_SUPPORTED = {"unknown", "yes", "no"}
DATA_USEFULNESS = {"high", "medium", "low", "not_useful", "unknown"}
SALES_SOURCE_TYPES = {"order-derived", "platform-stat-api", "settlement-api", "manual", "not_applicable"}
API_CATEGORIES = {"products", "orders", "inquiries", "sales", "settlements", "seller", "logistics", "auth"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def _strip(value: str | None) -> str | None:
    if isinstance(value, str):
        return value.strip()
    return value


class ApiCapabilityCheckCreate(BaseModel):
    platform: str = Field(..., min_length=1, max_length=50)
    capability_key: str = Field(..., min_length=1, max_length=120)
    capability_name: str = Field(..., min_length=1, max_length=200)
    api_category: str = Field(..., min_length=1, max_length=50)
    endpoint_path: str | None = Field(default=None, max_length=500)
    method: str | None = Field(default=None, max_length=20)
    required_credential_type: str | None = Field(default=None, max_length=200)
    required_permission: str | None = None
    ordinary_store_supported: str = Field(default="unknown", min_length=1, max_length=30)
    test_status: str = Field(default="not_tested", min_length=1, max_length=30)
    test_mode: str = Field(default="docs_only", min_length=1, max_length=30)
    request_params_summary: str | None = None
    response_fields_summary: str | None = None
    error_codes_summary: str | None = None
    data_usefulness: str = Field(default="unknown", min_length=1, max_length=30)
    first_phase_candidate: bool = False
    sales_source_type: str = Field(default="not_applicable", min_length=1, max_length=50)
    official_doc_url: str | None = Field(default=None, max_length=1000)
    doc_checked_at: datetime | None = None
    notes: str | None = None
    last_checked_at: datetime | None = None

    @field_validator(
        "platform",
        "capability_key",
        "capability_name",
        "api_category",
        "endpoint_path",
        "method",
        "required_credential_type",
        "required_permission",
        "ordinary_store_supported",
        "test_status",
        "test_mode",
        "request_params_summary",
        "response_fields_summary",
        "error_codes_summary",
        "data_usefulness",
        "sales_source_type",
        "official_doc_url",
        "notes",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _strip(value)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"naver", "coupang"}:
            raise ValueError("platform must be naver or coupang")
        return normalized

    @field_validator("api_category")
    @classmethod
    def validate_api_category(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in API_CATEGORIES:
            raise ValueError("api_category is not supported")
        return normalized

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.upper()
        if normalized not in HTTP_METHODS:
            raise ValueError("method is not supported")
        return normalized

    @field_validator("ordinary_store_supported")
    @classmethod
    def validate_ordinary_store_supported(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in ORDINARY_STORE_SUPPORTED:
            raise ValueError("ordinary_store_supported must be unknown, yes, or no")
        return normalized

    @field_validator("test_status")
    @classmethod
    def validate_test_status(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in TEST_STATUSES:
            raise ValueError("test_status is not supported")
        return normalized

    @field_validator("test_mode")
    @classmethod
    def validate_test_mode(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in TEST_MODES:
            raise ValueError("test_mode is not supported")
        return normalized

    @field_validator("data_usefulness")
    @classmethod
    def validate_data_usefulness(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in DATA_USEFULNESS:
            raise ValueError("data_usefulness is not supported")
        return normalized

    @field_validator("sales_source_type")
    @classmethod
    def validate_sales_source_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in SALES_SOURCE_TYPES:
            raise ValueError("sales_source_type is not supported")
        return normalized


class ApiCapabilityCheckUpdate(BaseModel):
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    capability_key: str | None = Field(default=None, min_length=1, max_length=120)
    capability_name: str | None = Field(default=None, min_length=1, max_length=200)
    api_category: str | None = Field(default=None, min_length=1, max_length=50)
    endpoint_path: str | None = Field(default=None, max_length=500)
    method: str | None = Field(default=None, max_length=20)
    required_credential_type: str | None = Field(default=None, max_length=200)
    required_permission: str | None = None
    ordinary_store_supported: str | None = Field(default=None, min_length=1, max_length=30)
    test_status: str | None = Field(default=None, min_length=1, max_length=30)
    test_mode: str | None = Field(default=None, min_length=1, max_length=30)
    request_params_summary: str | None = None
    response_fields_summary: str | None = None
    error_codes_summary: str | None = None
    data_usefulness: str | None = Field(default=None, min_length=1, max_length=30)
    first_phase_candidate: bool | None = None
    sales_source_type: str | None = Field(default=None, min_length=1, max_length=50)
    official_doc_url: str | None = Field(default=None, max_length=1000)
    doc_checked_at: datetime | None = None
    notes: str | None = None
    last_checked_at: datetime | None = None

    _strip_text = field_validator(
        "platform",
        "capability_key",
        "capability_name",
        "api_category",
        "endpoint_path",
        "method",
        "required_credential_type",
        "required_permission",
        "ordinary_store_supported",
        "test_status",
        "test_mode",
        "request_params_summary",
        "response_fields_summary",
        "error_codes_summary",
        "data_usefulness",
        "sales_source_type",
        "official_doc_url",
        "notes",
        mode="before",
    )(_strip)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in {"naver", "coupang"}:
            raise ValueError("platform must be naver or coupang")
        return normalized

    @field_validator("api_category")
    @classmethod
    def validate_api_category(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in API_CATEGORIES:
            raise ValueError("api_category is not supported")
        return normalized

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.upper()
        if normalized not in HTTP_METHODS:
            raise ValueError("method is not supported")
        return normalized

    @field_validator("ordinary_store_supported")
    @classmethod
    def validate_ordinary_store_supported(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in ORDINARY_STORE_SUPPORTED:
            raise ValueError("ordinary_store_supported must be unknown, yes, or no")
        return normalized

    @field_validator("test_status")
    @classmethod
    def validate_test_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in TEST_STATUSES:
            raise ValueError("test_status is not supported")
        return normalized

    @field_validator("test_mode")
    @classmethod
    def validate_test_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in TEST_MODES:
            raise ValueError("test_mode is not supported")
        if normalized == "real_readonly":
            raise ValueError("real_readonly is reserved for future explicit read-only API tests")
        return normalized

    @field_validator("data_usefulness")
    @classmethod
    def validate_data_usefulness(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in DATA_USEFULNESS:
            raise ValueError("data_usefulness is not supported")
        return normalized

    @field_validator("sales_source_type")
    @classmethod
    def validate_sales_source_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in SALES_SOURCE_TYPES:
            raise ValueError("sales_source_type is not supported")
        return normalized


class ApiCapabilityCheckRead(ApiCapabilityCheckCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiCapabilityTestResultCreate(BaseModel):
    store_id: int
    capability_id: int
    credential_id: int | None = None
    test_mode: str = Field(default="manual", min_length=1, max_length=30)
    test_status: str = Field(default="planned", min_length=1, max_length=30)
    http_status: int | None = Field(default=None, ge=100, le=599)
    error_code: str | None = Field(default=None, max_length=120)
    permission_result: str | None = None
    rate_limit_summary: str | None = None
    response_fields_observed: str | None = None
    tested_at: datetime | None = None
    notes: str | None = None

    @field_validator(
        "test_mode",
        "test_status",
        "error_code",
        "permission_result",
        "rate_limit_summary",
        "response_fields_observed",
        "notes",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _strip(value)

    @field_validator("test_mode")
    @classmethod
    def validate_test_mode(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in TEST_MODES:
            raise ValueError("test_mode is not supported")
        return normalized

    @field_validator("test_status")
    @classmethod
    def validate_test_status(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in TEST_STATUSES:
            raise ValueError("test_status is not supported")
        return normalized


class ApiCapabilityTestResultRead(ApiCapabilityTestResultCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
