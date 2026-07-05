# Phase Shipping-8F: Shipment Writeback Dry-Run Mock Gate

Implemented route:

```text
POST /api/v1/shipping/shipment-writeback/dry-run-gate
```

The route checks whether a matched local tracking import can become safe dry-run evidence for a future Naver shipment writeback. It only produces candidate evidence; it does not call Naver and does not write local data.

Ready candidate requirements:

- platform is `naver`,
- all approval and evidence flags are true,
- tracking rows match local orders,
- unmatched tracking rows are zero,
- local order status is already `DISPATCHED`,
- target delivery status is `DISPATCHED`.

Ready output:

- local order id,
- hashed order reference,
- hashed product order reference,
- hashed tracking number,
- carrier,
- shipped time,
- current local order status,
- target delivery status.

Closed boundaries:

- `shipment_writeback_called=false`,
- `shipment_writeback_open=false`,
- `real_api_called=false`,
- `real_database_written=false`,
- `platform_writes_enabled=false`,
- `future_platform_write_requires_separate_approval=true`.
