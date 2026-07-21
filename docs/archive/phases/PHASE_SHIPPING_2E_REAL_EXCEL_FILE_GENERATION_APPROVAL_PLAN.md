# Phase Shipping-2E: Real Excel File Generation Approval Plan

## Purpose

Plan the approval boundary for future real Excel generation.

## Decision

Current `/shipping` can still generate only an export contract preview. Real `.xlsx` creation must be a later phase with:

- operator approval,
- export row count,
- file hash,
- file path boundary,
- export record,
- operation audit evidence,
- privacy review for any receiver fields.

## Still Closed

Real Excel file creation, export record persistence, download record persistence, tracking-number upload, Naver shipment writeback, logistics-provider API integration, and formal order/product batch sync remain closed.
