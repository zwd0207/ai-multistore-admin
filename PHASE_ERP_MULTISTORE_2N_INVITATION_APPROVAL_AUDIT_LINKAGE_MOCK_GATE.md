# Phase ERP-Multistore-2N - Invitation Approval Audit Linkage Mock Gate

## Goal

Add a Codex1 mock gate proving that a future real user invitation approval can link to sanitized audit evidence before any user or membership write.

## Completed

Codex1 now validates planned references for invitation decision id, target user hash, masked login identifier, store scope, target role, approval actor hash, permission evidence, backup evidence, invite expiry policy, readback plan, rollback plan, audit correlation id, and append-only audit rows.

## Safety Result

- No user is created.
- No invitation is sent.
- No auth session is created.
- No role or store membership is written.
- No audit row is written.
- No formal sync or platform write is opened.

Passing this mock gate only means future invitation approval evidence can be reviewed.
