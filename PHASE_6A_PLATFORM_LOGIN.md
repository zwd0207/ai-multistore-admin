# Phase 6A Platform Login Boundary

## Scope

Phase 6A separates manual platform backend login records from API development credentials.

Phase 6A-1 was completed in Codex1 backend with:

- `GET /api/v1/platform-logins?store_id={store_id}`
- `POST /api/v1/platform-logins`
- `GET /api/v1/platform-logins/{login_id}`
- `PUT /api/v1/platform-logins/{login_id}`

Phase 6A-2 connects the Codex2 Accounts backend page to those endpoints. It does not modify Codex1 backend, does not perform real Naver or Coupang login, does not read verification codes, and does not connect real mailboxes.

## Accounts Page Boundary

Backend mode Accounts now shows two separate sections:

- Platform Login Information: manual Naver SmartStore / Coupang Wing backend login configuration.
- API Development Credentials: local API credential configuration for future platform API calls.

The two sections use separate tables, forms, labels, and save flows. Platform login records are never displayed as API keys, and API credentials are never displayed as backend login accounts.

## Platform Login Fields

Frontend fields are mapped in `src/services/adapters.js`:

- `platform`
- `label`
- `account`
- `passwordInput`
- `emailAccountId`
- `deviceEnvironmentId`
- `loginStatus`
- `remark`

Codex1 backend response only returns `hasLoginPassword`. It does not return plaintext or encrypted login password values.

## Binding Rules

The Platform Login form loads binding options from the current selected store:

- Email Accounts for verification email selection.
- Device Environments for login device selection.

Empty option states tell the user to add an email account or device environment first. Cross-store binding is rejected by Codex1 backend.

## Sensitive Field Rules

- Edit forms never prefill platform login password.
- Blank password on edit means the password is not updated.
- Save success, modal close, and save failure clear `passwordInput`.
- UI, notices, errors, and console output must not show plaintext password, encrypted password, API secret, or token values.
- Backend field names may exist in service and adapter payload mapping where required by Codex1 contracts.

## Local Status Semantics

`loginStatus` is displayed as local configuration status only. It does not mean real Naver or Coupang login succeeded, and the UI must not use wording such as real platform verified or login success.

## Verification Notes

Phase 6A-2 verification:

- backend mode `/accounts` returns 200 on the local Vite server.
- Codex1 `/platform-logins` create/list/edit/inactive was verified against port 8012.
- Current-store Email Account and Device Environment bindings were verified through the Platform Login payload.
- API Credential 5D-2 logic was preserved; `BackendCredentialPage` was only made embeddable.
- mock mode continues to use `MockAccounts`.
- build passed with the Vite JavaScript entrypoint and official Node.js.
- UTF-8 replacement scan returned 0.
- mojibake scan had no abnormal findings.
- Forbidden real-login and real-success UI wording scan returned 0.

## Phase 6A-3 API Credential Structured Fields

Phase 6A-3 extends API Credential structure for future API capability validation. It does not call real Naver or Coupang APIs and does not refresh tokens.

Backend 6A-3-1 adds structured fields to Codex1 `api_credentials`:

- `vendor_id`
- `client_id`
- encrypted access / refresh token storage
- `token_expires_at`
- `market`
- `auth_status`
- `last_tested_at`
- `api_remark`

Frontend 6A-3-2 updates the API Development Credentials section:

- Coupang shows Vendor ID, Access Key, Secret Key, Market, API local status, and API remark.
- Naver shows Client ID, Client Secret, Access Token, Refresh Token, Token expiry, API local status, and API remark.
- Sensitive inputs are blank on edit; blank values are not sent as updates.
- Lists show only configuration states such as `已配置 / 未配置`.
- `authStatus` is displayed as API local status only and does not mean real API validation succeeded.

The existing 5D-2 credential create/edit/inactive flow remains compatible, and 5D-3 mock sync continues to use existing `platform`, `status`, `hasAccessKey`, and `hasSecretKey` metadata.
