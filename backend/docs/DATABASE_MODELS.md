# Database Models

The development database is SQLite. The schema is created with SQLAlchemy `Base.metadata.create_all`. PostgreSQL migration is planned for a later stage.

All business records must be tied to `store_id` unless they are top-level stores or platform credentials that themselves point to a store.

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
encrypted_access_key
encrypted_secret_key
extra_config
status
created_at
updated_at
```

Rules:

- Must bind to `store_id`.
- Access and secret keys are encrypted with Fernet.
- Public APIs return only metadata such as `has_access_key` and `has_secret_key`.
- Decryption is limited to service/client internals.

Future integration notes:

- Add per-platform credential field mapping.
- Add token expiry, refresh status, and audit trail for real APIs.

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

