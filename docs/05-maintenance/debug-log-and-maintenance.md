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
- **Target defect:** Missing SHA-256 hash chain on AuditLog (present at v0.7-asbuilt).
- **Bisect log:**
```text
# defect-fixed: [1211a7397c326f7a96e37142784bfbfe375c1a2c] docs(maintenance): record actual git bisect log for audit-chain fix
# defect-present: [e2e27bdeff4b6675e3edb4a1bfdb358ccac65a67] Expand README with comprehensive project context
git bisect start '--term-old=defect-present' '--term-new=defect-fixed' 'HEAD' 'v0.7-asbuilt'
# defect-present: [a03cd979807879f651664868da18cc5ea87017cd] docs(design): add CI workflow, ADRs, FTR, reengineering report, and 500-user load test
git bisect defect-present a03cd979807879f651664868da18cc5ea87017cd
# defect-present: [d2ff5fc93fb1215f6d0394800a118840df46f390] fix(ci): clear complexity/flake8 gates, add WAL/indexes, and complete engineering docs
git bisect defect-present d2ff5fc93fb1215f6d0394800a118840df46f390
# defect-present: [7ac9d481affc4ff4f6708d8c7158cb581bf02742] docs(maintenance): record verified git bisect session for audit-chain fix
git bisect defect-present 7ac9d481affc4ff4f6708d8c7158cb581bf02742
# defect-present: [9fbb07d5e3d49783ee2017834f3b14b36784ba97] chore(git): stop tracking local sqlite db, coverage, and pycache files
git bisect defect-present 9fbb07d5e3d49783ee2017834f3b14b36784ba97
# first defect-fixed commit: [1211a7397c326f7a96e37142784bfbfe375c1a2c] docs(maintenance): record actual git bisect log for audit-chain fix
```
- **Bisect result:**
```text
Author: Ellen Kondani <kondaniellen@gmail.com>
Date:   Fri Nov 27 18:51:09 2026 +0200

    docs(maintenance): record actual git bisect log for audit-chain fix

 docs/05-maintenance/debug-log-and-maintenance.md | 9 ++++++---
 1 file changed, 6 insertions(+), 3 deletions(-)
bisect found first bad commit
```

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`
d2ff5fc (HEAD -> develop) fix(ci): clear complexity/flake8 gates, add WAL/indexes, and complete engineering docs
2d67569 (origin/develop) fix(ci): clear complexity/flake8 gates, add WAL/indexes, and complete engineering docs
0c2f661 docs(design): add CI workflow, ADRs, FTR, reengineering report, and 500-user load test
a03cd97 docs(design): add CI workflow, ADRs, FTR, reengineering report, and 500-user load test
926dddc (tag: v0.9) feat(channels): add Strategy/Observer/Template Method sync, backoff retries, and hotspot refactoring
28368cd feat(security): add DOB/OTP private lookup, IP throttling, and hash-chained audit log
fedbcc2 (tag: v0.8) docs: establish v0.8 requirements baseline (SRS, Gherkin, KAOS, RTM)
b350400 tests: add 18 pre-change characterisation tests and baseline report
698bf8e Add generated Python cache files and test coverage report
e2e27bd (tag: v0.7-asbuilt, main) Expand README with comprehensive project context
3e7f1fe Initial commit2
1ae0f35 Initial commit

Footer: Token EK01-HAZY-VM26 | Student 25313351001
