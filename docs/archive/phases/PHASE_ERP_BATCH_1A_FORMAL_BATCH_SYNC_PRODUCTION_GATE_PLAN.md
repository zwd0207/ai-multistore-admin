# Phase ERP-Batch-1A: Formal batch sync production gate plan

## Purpose

Prioritize the path toward formal product and order batch sync without opening it yet.

This phase defines the production gate that must pass before any future formal batch sync execution:

- explicit human approval
- store-scoped role permission
- sensitive-action approval role
- fresh readonly preview evidence
- verified database backup evidence
- duplicate protection
- field whitelist verification
- rollback and recovery plan
- failure isolation by store
- append-only audit evidence
- post-write readback and sensitive scan

## Current Decision

Formal Naver product batch sync and formal Naver order batch sync remain closed. A successful small-batch or no-change refresh is not enough to infer production readiness.

The next implementation may only prove the gate in mock/private helpers. It must not call Naver, write products, write orders, write SyncLog, add tested-success rows, or enable platform write operations.

## Safety Boundary

Do not save or return tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw external responses, full channel ids, full product/order ids, full buyer or receiver privacy, phones, addresses, or zip codes.

