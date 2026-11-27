# Risk and Quality — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-25

## 1. Risk register (>= 12)
1. SMS delivery failure (Technical, High)
2. Lookup enumeration (Security/Privacy, High)
3. Audit tampering (Security/Privacy, High)
4. SQLite contention (Technical, High)
5. Scope creep (Political, Medium)
6. Staff training gaps (Operational, Medium)
7. USSD 160-char truncation (Technical, Medium)
8. Gateway credential leakage (Security/Privacy, High)
9. Data retention compliance (Security/Privacy, Medium)
10. Third-party gateway downtime (Operational, Medium)
11. Regression risk (Technical, Medium)
12. Budget overrun (Political, Medium)

## 2. RMMM (top 3)
- **SMS delivery failure:** mitigate via `send_pending`, exponential backoff, outbox.
- **Lookup enumeration:** mitigate via per-IP/identifier throttling and generic errors.
- **SQLite contention:** mitigate via WAL, indexes, and PostgreSQL production plan.

## 3. Drop 2 readiness
- CI gates green; 62 tests; verify_slices/verify_audit pass.

## 4. Technical debt comparison
- `v0.7-asbuilt`: god module, no hash chain, no idempotency, no backoff.
- Current: modular handlers, hash chain, idempotency, backoff, CI gates.

## 5. ISO 25010 quality gates
- Functional Correctness: 62 tests passing.
- Availability: load-test gate currently failing; production recommendation documented.
- Confidentiality: masked PII, hashed identifiers, RBAC.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`
## Sealed Drops status (honest disclosure)
- Sealed Drop 1 (Requirements baseline), Drop 2 (Design baseline) and Drop 3 (Implementation baseline) were **not issued by the lecturer** for this course run.
- RMMM traceability hooks (`verify_slices`, `verify_audit`, reengineering report) are implemented and ready to consume a drop when issued.
- Footer: Token `EK01-HAZY-VM26` | Student `25313351001`
