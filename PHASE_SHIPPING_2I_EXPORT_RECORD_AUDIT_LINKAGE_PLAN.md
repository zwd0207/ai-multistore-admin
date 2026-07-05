# Phase Shipping-2I: Export Record and Audit Linkage Plan

## Purpose

Define how a future real logistics export should connect file evidence, export records, and operation audit logs.

## Plan

Future real export must create a single correlation chain:

1. operator approval evidence,
2. pre-export row-count and mapping readiness evidence,
3. generated file metadata with SHA-256,
4. export batch record,
5. operation audit row linked by `audit_correlation_id`,
6. post-export verification that no platform shipment writeback was executed.

## Boundary

This phase adds no runtime writer. Real export records and audit rows remain closed until a later explicit implementation phase.
