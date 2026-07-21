# Database Models

The development database is SQLite. The schema is created with SQLAlchemy `Base.metadata.create_all`. PostgreSQL migration is planned for a later stage.

All business records must be tied to `store_id` unless they are top-level stores or platform credentials that themselves point to a store.

## Timezone Rules

Business timezone is fixed by `APP_TIMEZONE`, defaulting to `Asia/Seoul`.

Rules:

- Stored datetimes are UTC aware values.
- Windows display timezone is not used as a business-time source.
- SQLite may return older local development rows as naive datetimes; service code treats those as UTC for compatibility.
- Daily sales, daily order grouping, and AI daily context use Korean natural days.
- SyncLog writes UTC timestamps. Frontend display should convert UTC timestamps to KST.

## Store

Table: `stores`

Main fields:

```text
id
name
platform
country
language
status
owner_name
remark
created_at
updated_at
```

Rules:

- `name` is a real store-name-style value.
- Chinese, Korean, and mixed text are supported.
- `status` currently uses strings such as `active`, `inactive`, `suspended`.

Future integration notes:

- Add tenant or user ownership if the system becomes multi-user.
- Consider soft delete before production.

## ApiCredential

Table: `api_credentials`

Main fields:

```text
id
store_id
platform
credential_name
vendor_id
client_id
encrypted_access_key
encrypted_secret_key
encrypted_access_token
encrypted_refresh_token
token_expires_at
market
auth_status
last_tested_at
api_remark
extra_config
status
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Access keys, secret keys, access tokens, and refresh tokens are encrypted with Fernet.
- Public APIs return only metadata such as `has_access_key`, `has_secret_key`, `has_access_token`, and `has_refresh_token`.
- Decryption is limited to service/client internals.
- `vendor_id`, `client_id`, `market`, `auth_status`, `last_tested_at`, and `api_remark` are structured local configuration fields.
- `auth_status` is local configuration or future test status only; it does not mean real platform API validation succeeded in the current stage.
- `extra_config` stores short-term platform-specific metadata such as HMAC notes, allowed IP notes, and experimental fields.

Future integration notes:

- Add API capability test records before real API integration.
- Add token refresh workflow only after real Naver/Coupang API validation is explicitly approved.

## ApiCapabilityCheck

Table: `api_capability_checks`

Main fields:

```text
id
platform
capability_key
capability_name
api_category
endpoint_path
method
required_credential_type
required_permission
ordinary_store_supported
test_status
test_mode
request_params_summary
response_fields_summary
error_codes_summary
data_usefulness
first_phase_candidate
sales_source_type
official_doc_url
doc_checked_at
notes
last_checked_at
created_at
updated_at
```

Rules:

- Records platform-level API capability definitions and docs/manual confirmation notes.
- Does not bind to `store_id`; store-specific results live in `api_capability_test_results`.
- `docs_only` means documentation or manual research only.
- `tested_success` is a record status only and must not be described as full sync support.
- `real_readonly` is reserved for the Phase 6C readonly smoke-test endpoint; it is not a manual docs-only record.
- This table does not store API keys, secrets, tokens, or decrypted credential data.

Future integration notes:

- Link official Naver/Coupang documentation references before any real API implementation.
- Keep explicit real read-only tests limited to the approved readonly smoke-test endpoint.
- API capability summaries aggregate this table by `platform`; `last_checked_at` is derived from `last_checked_at`, `doc_checked_at`, or `updated_at`.
- Summary counts are local records only. `tested_success` does not mean full platform connection, and `real_readonly_count` means readonly smoke-test records exist.

## ApiCapabilityTestResult

Table: `api_capability_test_results`

Main fields:

```text
id
store_id
credential_id
capability_id
test_mode
test_status
http_status
error_code
permission_result
rate_limit_summary
response_fields_observed
tested_at
notes
created_at
```

Rules:

- Must bind to an existing `store_id`.
- Must bind to an existing `capability_id`.
- Can bind to `credential_id`; when provided, the credential must belong to the same store.
- Credential platform must match capability platform.
- Stores manual/docs/mock/sandbox notes and approved readonly smoke-test metadata.
- Does not decrypt credentials and does not store secret/token values.
- `real_readonly` result creation is reserved for the approved readonly smoke-test endpoint and is rejected by the generic manual result create API.

Future integration notes:

- Readonly smoke tests write result records with step statuses, error code, HTTP status, and timestamps only.
- Failure records should preserve error code, permission reason, observed fields, and rate limit summary.
- Store-level summaries aggregate this table by `store_id` and capability platform.
- `missing_first_phase_candidates` is derived by comparing first-phase platform capabilities against the store's result records.
- Summary responses do not include API secrets, tokens, passwords, encrypted values, or decrypted credential material.

## PlatformLoginCredential

Table: `platform_login_credentials`

Main fields:

```text
id
store_id
platform
login_label
login_account
encrypted_login_password
email_account_id
device_environment_id
login_status
last_login_check_at
remark
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Stores manual Naver SmartStore / Coupang Wing backend login metadata only.
- Login password is encrypted with Fernet.
- Public APIs return `hasLoginPassword`, never plaintext or encrypted password.
- `email_account_id` and `device_environment_id` must belong to the same store when provided.
- `login_status` is local configuration status only; this stage does not perform real platform login checks.

Future integration notes:

- Add login check events if a future manual or automated verification workflow is approved.
- Add multi-factor verification metadata without storing verification codes.
- Add binding history if device reuse risk analysis is needed.

## SyncLog

Table: `sync_logs`

Main fields:

```text
id
store_id
platform
sync_type
status
started_at
finished_at
message
error_detail
raw_summary
```

Rules:

- Must bind to `store_id`.
- `raw_summary` stores structured JSON summaries.
- Supports Chinese and Korean messages.

Future integration notes:

- Add duration, request id, retry count, and raw response storage pointer.

## Product

Table: `products`

Main fields:

```text
id
store_id
platform
external_product_id
name
sku
brand
category
status
price
currency
stock_quantity
raw_data
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Upsert key: `store_id + platform + external_product_id`.
- `raw_data` stores platform source summaries.

Future integration notes:

- Add real Naver/Coupang product field mapping, option data, image URLs, and listing status normalization.

## Order

Table: `orders`

Main fields:

```text
id
store_id
platform
external_order_id
buyer_name
buyer_masked_phone
product_name
quantity
order_amount
currency
order_status
paid_at
ordered_at
raw_data
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Upsert key: `store_id + platform + external_order_id`.
- Only masked phone numbers are stored.
- Full phone, full address, ID number, and payment sensitive data are not modeled.
- `ordered_at` and `paid_at` are stored in UTC; daily grouping converts `ordered_at` to KST before taking the date.

Future integration notes:

- Add item-level order mapping if platform order contains multiple product lines.
- Add cancellation/refund amount fields for real sales statistics.

## CustomerInquiry

Table: `customer_inquiries`

Main fields:

```text
id
store_id
platform
external_inquiry_id
inquiry_type
customer_name
title
content
status
received_at
answered_at
raw_data
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Upsert key: `store_id + platform + external_inquiry_id`.
- `title`, `content`, and `raw_data` support Chinese/Korean text.

Future integration notes:

- Add response tracking and customer-name masking for real data.

## DeviceEnvironment

Table: `device_environments`

Main fields:

```text
id
store_id
environment_name
device_type
os_name
browser_name
ip_label
proxy_label
status
last_used_at
remark
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Store labels only, not real full IPs, proxy passwords, or remote desktop passwords.

Future integration notes:

- Add secure secret vault integration if remote credentials are needed.

## EmailAccount

Table: `email_accounts`

Main fields:

```text
id
store_id
email_address
provider
account_label
encrypted_password_or_token
status
last_checked_at
remark
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Password/token is encrypted with Fernet.
- Public APIs do not return plaintext or encrypted token.
- Current stage does not connect to real mail providers.

Future integration notes:

- Add OAuth account ids, token expiry, refresh metadata, and provider-specific scopes.

## ImportantEmail

Table: `important_emails`

Main fields:

```text
id
store_id
email_account_id
platform
mail_type
sender
subject
snippet
body_text
received_at
status
priority
related_case_id
raw_data
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Can link to `email_account_id`.
- `related_case_id` is reserved for linking to appeal cases.
- No real attachments are stored.

Future integration notes:

- Add attachment metadata, file storage pointers, and mail provider message ids when real mail ingestion is added.

## AppealCase

Table: `appeal_cases`

Main fields:

```text
id
store_id
platform
case_type
case_title
case_status
external_case_id
related_order_id
related_product_id
deadline_at
submitted_at
resolved_at
summary
action_required
raw_data
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Mock `external_case_id` values use test ids such as `MOCK-CASE-001`.
- No real ID cards, bank cards, full addresses, or legal documents are stored.

Future integration notes:

- Add evidence file metadata, workflow events, and platform-specific case status mapping.
