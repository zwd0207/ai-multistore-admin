# Phase ERP-Batch-1F: Readonly Evidence API Local Implementation Plan

## Purpose

Plan the future local readonly evidence API that will feed batch approval screens with safe summaries.

## Planned Response Shape

- Sync kind
- Store id
- Window label
- Candidate count
- Would create/update/refresh/skip counts
- Changed field names
- Duplicate-check status
- Field-whitelist status
- Backup/permission/audit requirements
- Business message and next action

## Hidden From Main UI

Raw responses, tokens, headers, signatures, full channel identifiers, full product/order identifiers, and buyer privacy must never be included.

## Current Status

Only the private mock evidence normalizer exists. No public readonly evidence route is open yet.
