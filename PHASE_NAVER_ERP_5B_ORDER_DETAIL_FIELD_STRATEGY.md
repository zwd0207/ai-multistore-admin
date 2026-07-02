# Phase Naver-ERP-5B - Order Detail Complete Field Display Strategy

## Scope

This phase documents the Naver order detail field policy after the product and order ERP summaries have reached the Dashboard.

No code path is changed in this phase. It does not call Naver, does not write Codex1 data, does not open formal order sync, and does not change database schema.

## Goal

Codex2 may support complete order detail display for internal daily operations, including:

- complete Naver order number
- complete Naver product order number
- complete platform product number when available
- buyer name
- buyer phone
- receiver name
- receiver phone
- receiver address

This is a controlled business-detail view, not a Dashboard summary view.

## Display Layers

Dashboard:

- Shows only ERP summary signals.
- Shows counts, statuses, local order amount, inventory alerts, fulfillment alerts, and sync protection state.
- Does not expand complete buyer information, address, full order numbers, or full product numbers.

Orders list:

- May show readable order number and product number.
- Should stay compact and avoid placing full address or phone numbers in every row.
- Should provide an order detail entry for the complete business fields.

Order detail drawer or detail page:

- May show complete order number, product order number, platform product number, buyer name, buyer phone, receiver name, receiver phone, and address.
- Should group fields into order information, product information, buyer information, receiver and delivery information, and claim or after-sales status.
- Should keep platform write actions disabled unless a later phase explicitly opens them.

TechnicalDetails:

- Keeps technical metadata, mapping flags, and diagnostic fields.
- Must not become the main location for complete buyer business data.

## Backend Data Policy

Current Codex1 order phases were built with a redaction-first policy. Complete fields are not guaranteed to exist in the local database today.

Future backend phases must explicitly decide how to store complete fields before Codex2 can display them from real backend data.

Allowed future business fields, after explicit approval:

- `external_order_id`
- `external_product_order_id`
- `platform_product_id`
- `buyer_name`
- `buyer_phone`
- `receiver_name`
- `receiver_phone`
- `receiver_address`
- `order_status`
- `order_status_label_zh`
- `product_name`
- `option_name`
- `quantity`
- `order_amount`
- `currency`
- `ordered_at`
- `paid_at`
- `last_changed_at`
- `delivery_status`
- `claim_status`
- `source_type`
- `last_synced_at`
- `mapping_version`

Still forbidden:

- token
- Authorization
- request headers
- signature or bcrypt sign payload
- client secret
- raw response
- debug dumps containing raw order payloads
- complete buyer data in logs, error messages, sync logs, capability test results, or console output

## Permission And Safety Boundary

Complete buyer and order fields are allowed only for internal operations pages.

The UI should keep them out of:

- Dashboard summary cards
- broad technical detail grids
- error banners
- build logs
- browser console logs
- mock sync result messages
- API capability records

Copy buttons, export features, printing, and bulk download of complete buyer information require separate approval.

## Future Write Gate

A future real-data phase may store complete order fields only after all of the following are true:

- User explicitly approves the phase.
- `codex1.db` is backed up before writing.
- The phase is limited to `store_id=8`.
- The phase starts from readonly dry-run.
- The dry-run previews exactly which complete fields will be stored.
- Only one Naver order is written in the first complete-field write test.
- No Naver platform write action is executed.
- No SyncLog is written unless a later audit phase explicitly changes this rule.
- No `ApiCapabilityTestResult tested_success` is added by the write.
- Post-write readback confirms complete fields exist only in approved order business fields.
- Sensitive fields are absent from logs, errors, raw payload storage, and TechnicalDetails.

Formal order sync remains closed until a separate phase approves it.

## Codex2 Mock Plan

The next frontend implementation phase should be:

`Phase Naver-ERP-5C: Naver order detail complete field mock display`

Recommended implementation:

- Add an order detail drawer or detail panel on the Orders page.
- Use mock data to represent complete order number, product number, buyer information, receiver information, delivery status, and claim status.
- Keep Dashboard unchanged as summary-only.
- Keep backend mode tolerant when complete fields are missing.
- Do not add real API calls.
- Do not require Codex1 schema changes.

## Acceptance Criteria For The Future UI Phase

- Orders page opens in mock and backend modes.
- Detail view shows complete mock business fields when mock data provides them.
- Backend mode does not crash if complete fields are absent.
- Dashboard does not display complete buyer phone or address.
- No text claims formal Naver order sync is open.
- No text claims platform settlement, profit, or account extractable funds are confirmed.
- Encoding scan passes.
- Build passes.

## Current Status

Documented only.

No real API executed. No database write performed. No Codex1 schema changed. No Codex2 order detail UI implemented yet.
