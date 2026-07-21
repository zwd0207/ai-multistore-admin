# Phase Shipping-4C: Export History Readonly API Plan

## Purpose

Plan a business-readable export-history API over the existing Shipping-3 export tables.

## Read Model

The read-only API should show:

- export time
- file name
- file type and format
- row count
- export status
- audit correlation id
- safe file hash in technical details

## Boundary

The route must not generate files, write audit rows, write export rows, import tracking numbers, or call platform/logistics APIs.
