# Phase Shipping-3C: Real Excel Generation Approval Plan

## Purpose

Define the approval boundary for local real Excel generation.

## Approved Local Action

An operator may generate a local `.xlsx` file only when:

- `manual_approval=true`,
- rows are export-ready,
- receiver privacy is not included,
- export records and audit linkage are available,
- platform writes remain disabled.

## Still Closed

Naver shipment writeback, tracking-number import, cancel/return/exchange writes, logistics-provider API integration, and formal order batch sync remain closed.
