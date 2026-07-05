# Phase Shipping-7E: Tracking Import Parser Runtime Walkthrough

Runtime walkthrough target:

- backend data source `/shipping`
- mock data source `/shipping`
- parser upload shell visible
- page renders without white screen
- parser boundary visible in advanced details

Expected behavior:

- selecting an `.xlsx` file enables preview,
- preview calls the parser mock route in backend mode,
- mock mode returns a safe sample preview,
- no local import record is created,
- no order is updated,
- no Naver API or logistics-provider API is called.

Verification commands:

```text
npm.cmd run build
VITE_DATA_SOURCE=mock npm.cmd run build
npm.cmd run encoding:scan
```
