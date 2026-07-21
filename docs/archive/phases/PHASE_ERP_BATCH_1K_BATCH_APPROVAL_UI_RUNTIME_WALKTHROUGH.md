# Phase ERP-Batch-1K: Batch Approval UI Runtime Walkthrough

## Purpose

Runtime-check the Naver batch approval readonly evidence UI in both mock and backend data-source modes.

## Walkthrough Result

- Orders page rendered without white screen in mock mode.
- Orders page rendered without white screen in backend mode after refreshing the local backend on port `8012`.
- The Naver batch approval evidence panel was visible.
- The main panel showed business wording for evidence readiness, product evidence, order evidence, and write protection.
- Technical fields stayed folded in TechnicalDetails.

## Fix Applied

Backend mode initially displayed the backend English business message in the main UI. The Orders page now maps the evidence status to Chinese seller-facing wording and leaves raw status fields in folded technical details.

## Safety Boundary

- No Naver API call.
- No product/order/SyncLog/tested-success/audit write.
- No schema change.
- No formal product or order batch sync opening.
