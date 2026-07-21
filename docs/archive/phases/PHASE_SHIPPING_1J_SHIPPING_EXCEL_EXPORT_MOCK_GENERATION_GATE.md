# Phase Shipping-1J: Shipping Excel Export Mock Generation Gate

## Purpose

Add the first Excel export contract mock gate for logistics-provider shipping requests.

## Implemented

- Added `buildShippingExcelExportMock(...)`.
- Added a `生成 Excel 导出预览` action on `/shipping`.
- The preview includes:
  - file name,
  - file type,
  - file format,
  - row count,
  - mock file hash,
  - export row preview.

## Export Contract

The first export type remains:

```text
file_type=shipping_request
file_format=xlsx
```

The contract stays extensible for future:

- tracking upload files,
- inventory tables,
- product tables,
- CSV or other formats.

## Boundary

- No actual Excel file is generated.
- No export record is written.
- No operation-audit row is written.
- Receiver privacy is not included by default.
- No Naver API call.
- No formal order sync.
- No platform shipment write.

