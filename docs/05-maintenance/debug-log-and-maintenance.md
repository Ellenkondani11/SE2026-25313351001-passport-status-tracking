# Debug Log and Maintenance — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. Defects found and fixed (v0.7-asbuilt -> v0.95)
1. **Resume from `on_hold` omitted SMS** (Corrective). Cause: `application_detail` resume branch updated stage but did not call `notify_stage`. Fix: route through `transition_application_stage`, which publishes `StageChangedEvent` and `SmsChannelObserver` dispatches SMS.
2. **IP-wide lookup enumeration unthrottled** (Corrective). Cause: rate limit scoped only to `(national_id_hash, ip)`. Fix: added per-IP failure count across all identifiers in `core/lookup.py:_rate_limited`.
3. **`public_status` ignored `verified_status_at` TTL** (Corrective). Cause: only compared `verified_status_code`. Fix: parse and enforce 15-minute TTL, clearing expired session keys.
4. **Duplicate SMS on repeated triggers** (Corrective). Cause: no deduplication guard. Fix: added `Notification.idempotency_key` (unique, nullable) and early return in `notify()`.
5. **`AuditLog` lacked tamper evidence** (Preventive). Cause: ORM immutability only. Fix: SHA-256 hash chain (`prev_hash`/`entry_hash`) via `core/audit_chain.py`, `verify_audit_chain()`, and `verify_audit` command.
6. **`send_pending` retried immediately without backoff** (Corrective). Cause: no `retry_count`/`next_retry_at`. Fix: exponential backoff `2^(n-1)` minutes and filtering in `send_pending`.
7. **SQLite/session contention under load** (Adaptive/Preventive). Cause: single-threaded dev server + session writes on every request. Fix: WAL mode, indexes, `SESSION_SAVE_EVERY_REQUEST=False`, session touch only for authenticated users.

### Program slicing (examples)
- **Defect 1 (resume SMS)**: slice included `application_detail` resume branch, `notify_stage`, `notify`, `Stage.notify`. Eliminated the missing call by unifying through `transition_application_stage`.
- **Defect 5 (audit tamper)**: slice included `AuditLog.save`, `AuditLog.delete`, `audit()`, and all `AuditLog.objects.create` call sites. Added hash computation at creation only.

## 2. Boehm maintenance model / IEEE 1219 types
- **Corrective:** defects 1, 2, 3, 4, 6.
- **Adaptive:** defect 7 (load/performance environment).
- **Perfective:** channel consistency, dispatcher refactor, UI handler split.
- **Preventive:** hash-chained audit log, idempotency keys, rate limits, WAL/indexes.

## 3. Live git bisect check
[TO RUN: git bisect session]

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`