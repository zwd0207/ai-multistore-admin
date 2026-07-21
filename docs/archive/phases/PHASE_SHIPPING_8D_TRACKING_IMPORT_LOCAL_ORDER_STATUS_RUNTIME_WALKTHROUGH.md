# Phase Shipping-8D: Tracking Import Local Order Status Runtime Walkthrough

Runtime walkthrough target:

- backend data source `/shipping`
- mock data source `/shipping`
- tracking import history visible
- tracking-to-order match evidence visible
- local order status update gate visible
- shipment writeback remains closed

Expected behavior:

- operator can review parsed/imported tracking rows before any local order status update,
- local status update requires manual approval, backup evidence, audit evidence, and operator checklist acknowledgement,
- ready evidence can update local ERP order status only in the separately approved local update route,
- repeated or terminal-status orders are blocked or treated as no-op,
- Naver shipment writeback is not called,
- logistics-provider API is not called,
- formal order batch sync remains closed.

Runtime boundary:

- no Naver API call is required for this walkthrough,
- no platform shipment write operation is allowed,
- no order insert is allowed,
- no product write is allowed,
- no SyncLog write is allowed,
- no ApiCapabilityTestResult `tested_success` write is allowed,
- no raw response, token, Authorization, headers, signature, client secret, buyer privacy, receiver privacy, full address, or zip code may be saved.

Verification commands:

```text
python scripts/verify_all.py
python scripts/scan_encoding.py
npm.cmd run build
VITE_DATA_SOURCE=mock npm.cmd run build
npm.cmd run encoding:scan
git diff --check
```

Walkthrough checklist:

- `/shipping` renders without a blank screen.
- The page shows the Shipping Assistant workflow, tracking import upload/history, match evidence, and local order status update panels.
- The local update panel explains that it updates local status evidence only.
- The Naver shipment writeback panel still shows writeback as closed or not called.
- Ordinary operator copy avoids raw technical fields; advanced evidence stays in TechnicalDetails.
