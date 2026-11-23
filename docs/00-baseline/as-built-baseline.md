# As-Built Baseline Report — PassTrack (PASTNS)
- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Baseline Tag:** `v0.7-asbuilt`
- **Date:** 2026-11-21

## 1. Inventory of What Exists at `v0.7-asbuilt`
- **Codebase size:** 58 tracked files, 3,726 embedded lines (`CODEBOOK.md`).
- **Stack:** Python 3.10+ (Django 4.2 LTS), Django REST Framework + `TokenAuthentication`, `drf-spectacular` (OpenAPI/Swagger), SQLite (demo) / PostgreSQL (`dj-database-url`), Africa's Talking SMS/USSD callback seam (`PASTNS_SMS_GATEWAY=console`), self-hosted Inter font, Django i18n (`en`/`ny`).
- **Data schema (`core/models.py`, 13 models):** `Office`, `Profile`, `Applicant`, `Stage`, `Application`, `StageChange`, `Notification`, `SmsTemplate`, `UssdSession`, `AuditLog`, `LookupAttempt`, `LoginAttempt`, `OfficerNote`.
- **Implemented surfaces:**
  - Public portal (`/`, `/status/`, `/language/`, `/ussd-demo/`)
  - Officer workbench (`/officer/`, registration, application detail, bulk actions, outbox, audit log)
  - Supervisor reports (`/officer/reports/`, CSV exports, SVG bar chart)
  - Admin console (`/officer/admin/`, staff/roles, offices, stages, SMS templates)
  - Machine API (`/api/applications/`, `/api/applications/<code>/`, `/api/applications/<code>/stage/`, `/api/sms/delivery/`, `/api/ussd/`)

## 2. Baseline Metrics Snapshot (`v0.7-asbuilt`)
| Metric | Value at `v0.7-asbuilt` |
|---|---|
| Automated tests (initial) | 6 passing (`tests/test_workflows.py`) |
| Characterisation tests (pre-change gate) | 24 passing (`tests/test_workflows.py` + `tests/test_characterisation.py`) |
| Whole-system line coverage (initial 6 tests) | 52% (1,396 stmts, 668 missed) |
| Module coverage highlights | `models.py` 89%, `utils.py` 89%, `api.py` 72%, `forms.py` 70%, `services.py` 61%, `middleware.py` 60%, `views.py` 36% |
| Top complexity hotspots (`lizard`) | 1,535 NLOC, avg CCN 5.0, 7 warnings (CCN > 15); top 3 app hotspots: `core/views.py:application_detail` (CCN 34), `core/views.py:ussd_endpoint` (CCN 30), `core/api.py:ApplicationStageAPIView.put` (CCN 24); weakest module `core/views.py` (699 NLOC, avg CCN 7.2, 36% initial coverage) |
| Baseline SAST findings (`bandit`) | 0 High, 0 Medium, 6 Low (all B311 `random` calls in `core/management/commands/seed_demo.py`) |
| Baseline lint findings (`flake8`) | 111 lint issues |
| Known open defects / security gaps | See Section 3 below |

## 3. Gap List Against the Signature Challenge

### Property 1 — Consistency (Web, SMS, and USSD agree within 60 seconds)
- **Built:** All three channels query the same SQLite/PostgreSQL database (`Application.current_stage`); stage updates on web/API synchronously trigger `notify_stage()`.
- **Missing / Gaps:**
  1. `Stage.applicant_text_en/ny` (used by web & USSD) and `SmsTemplate.body_en/ny` (used by SMS) are edited independently with no consistency validation or unified message source.
  2. Resuming from `on_hold` (`views.py` `action == "resume"`) changes `current_stage` without calling `notify_stage()`, leaving SMS out of sync with web/USSD.
  3. USSD lookup (`views.py` line 674) reads `current_stage` directly, whereas `public_status` reads `current_stage` plus `status` (`on_hold`/`rejected` handling differs slightly in UI vs USSD text).

### Property 2 — Reliable Notifications (Exponential backoff retry, no duplicates, delivery reports stored)
- **Built:** Durable `Notification` outbox row (`queued`/`sent`/`delivered`/`failed`), `send_pending` management command, and `POST /api/sms/delivery/` callback endpoint updating `status`.
- **Missing / Gaps:**
  1. **No automatic exponential backoff:** `Notification` has no `retry_count`, `max_retries`, or `next_retry_at` fields; `send_pending` retries everything immediately with no backoff schedule.
  2. **No deduplication / idempotency guard:** Rapid double-clicks, duplicate API calls, or repeated `send_pending` runs can dispatch duplicate SMS for the same stage transition (no `idempotency_key` or unique constraint per stage change + channel).
  3. **Delivery callback auth optional:** When `SMS_CALLBACK_TOKEN` is empty (default), `/api/sms/delivery/` accepts unauthenticated updates (`core/api.py:195`).

### Property 3 — Private Lookup (Application number + DOB or OTP, rate-limited against enumeration)
- **Built:** Public lookup requires two factors (National ID + phone/tracking code), uses generic mismatch error, and enforces 5 attempts per 15 min per `(national_id_hash, ip)`.
- **Missing / Gaps:**
  1. **No Date of Birth (`date_of_birth`) field:** `Applicant` does not store DOB, so lookups cannot verify application number + DOB as required by the Signature Challenge.
  2. **No One-Time Code (OTP) alternative:** No OTP generation/expiry/verification flow exists for web or USSD lookups.
  3. **Enumeration & IP-bypass risks:** Rate limiting scopes strictly by `(national_id_hash, ip)` (`views.py:60-63`); rotating IPs or brute-forcing tracking codes across multiple IDs from one IP is not rate-limited (`ip`-only limiter missing). Furthermore, `public_status` checks `request.session["verified_status_code"]` without checking `verified_status_at` expiry.

### Property 4 — Auditability (Officer, time, reason in a tamper-evident log)
- **Built:** `AuditLog` records `user`, `action`, `object_type`, `object_id`, `details`, `ip`, `at`; `save()` and `delete()` raise `ValueError` in Django ORM.
- **Missing / Gaps:**
  1. **Not tamper-evident:** `AuditLog` has no cryptographic hash chain (`prev_hash`, `entry_hash`) or verification routine; `.update()`, `bulk_update()`, or direct SQL edits cannot be detected.
  2. **Inconsistent `reason` enforcement:** Standard `advance` and bulk updates hardcode generic reasons; `AuditLog` entries on some actions lack structured `reason` or `by_user` consistency (e.g., `send_notification` creates `AuditLog` directly while `views.py` uses `audit()`).
