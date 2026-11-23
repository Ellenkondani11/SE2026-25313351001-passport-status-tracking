# Software Requirements Specification (SRS) — PassTrack (PASTNS)
- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.8` (Requirements Baseline)
- **Date:** 2026-11-21
- **CMMI Areas:** Requirements Management (REQM); Configuration Management (CM)

## 1. Scope & Stakeholders
PassTrack (PASTNS) enables Malawi's Department of Immigration and Citizenship Services (Mangochi pilot) to record passport stage transitions and expose consistent, private status updates over **Web**, **SMS**, and **USSD (`*384*123#`)**.
- **Stakeholders:** Applicant, Immigration Counter Clerk (Officer), Approving Officer (Supervisor), ICT Manager (Admin).

## 2. Functional Requirements (28 Requirements — Tagged Built / Partial / New)

| ID | Requirement | Status | Signature Challenge / Scope |
|---|---|---|---|
| FR-01 | Dual-factor public status lookup (National ID + phone/code) | Built | Core lookup |
| FR-02 | Masked phone & National ID display on public/worklist views | Built | Privacy |
| FR-03 | Bilingual UI & messages (English `en` / Chichewa `ny`) | Built | Public & USSD |
| FR-04 | USSD 3-level menu (`1 Check status`, `2 Hours`, `3 Language`) <= 160 chars | Built | USSD channel |
| FR-05 | Officer application registration generating `MW-{OFFICE}-{YEAR}-{SEQ:05d}` | Built | Officer workbench |
| FR-06 | Sequential stage advance (`Received -> Under review -> Approved -> Printed -> Ready`) | Built | Officer workbench |
| FR-07 | Supervisor-gated stage skip/rollback/reject with mandatory reason | Built | RBAC / Workflow |
| FR-08 | Put application on hold with reason and resume to previous stage | Partial | Resume omits SMS notify |
| FR-09 | Batch stage update (`Mark as Printed`, `Mark as Ready`) and CSV export | Built | Officer workbench |
| FR-10 | Formula-injection safe CSV export (`_csv_safe`) with masked PII | Built | Security |
| FR-11 | Officer contact correction requiring ID verification tick-box + reason | Built | Accountability |
| FR-12 | Staff login lockout (5 failed attempts -> 15 min) & 30-min session idle timeout | Built | Security |
| FR-13 | Role-based access control (`officer < supervisor < admin`) and office scoping | Built | Security |
| FR-14 | Admin management of staff roles, offices, stages, and SMS templates | Built | Administration |
| FR-15 | Supervisor workload, monthly intake, and SMS delivery rate reports | Built | Reporting |
| FR-16 | Token-authenticated REST API (`/api/applications/`) with OpenAPI/Swagger | Built | Integration |
| FR-17 | **Cross-channel consistency:** web, SMS, and USSD show identical status/stage text within 60s, including on hold/resume | Partial | **Signature Challenge #1** |
| FR-18 | **Exponential backoff SMS retry:** automatic retry schedule (`2^n` min, capped) with `retry_count`, `max_retries`, `next_retry_at` | New | **Signature Challenge #2** (Issue #1) |
| FR-19 | **Notification deduplication & callback security:** idempotency key per transition+channel preventing duplicate SMS; delivery report storage with enforced callback auth | Partial | **Signature Challenge #2** (Issue #2) |
| FR-20 | **Private lookup via App Code + DOB or OTP:** store applicant `date_of_birth`, support tracking code + DOB or 6-digit time-limited OTP | New | **Signature Challenge #3** (Issue #3) |
| FR-21 | **Anti-enumeration rate limiting & session TTL:** IP + identifier sliding rate limits and 15-min verified-status session expiry | Partial | **Signature Challenge #3** (Issue #3) |
| FR-22 | **Tamper-evident hash-chained audit log:** SHA-256 `prev_hash` + `entry_hash` across `AuditLog` with integrity verification command/endpoint and mandatory actor/time/reason | Partial | **Signature Challenge #4** (Issue #4) |
| FR-23 | **Event-driven stage-change dispatcher:** publish `StageChangedEvent` to registered channel handlers (Observer + Strategy + Template Method) | New | Architecture / Remaining Scope (Issue #5) |
| FR-24 | **Public lookup rate-limit & audit verification UI/health endpoint:** surface tamper-check status to admin and handle Drop 1–3 extensions cleanly | New | Remaining Scope (Issue #6) |
| FR-25 | **Bilingual message-source parity:** unify `Stage.applicant_text_*` and `SmsTemplate.body_*` with automated consistency check | Partial | Remaining Scope (Issue #7) |
| FR-26 | **Notification outbox & dispatch seam:** `send_pending` management command, async batch dispatch, and outbox status dashboard | Built | Remaining Scope (Issue #8) |
| FR-27 | **USSD session & phone shortcut:** 3-level menu, language switch, and cached last-status shortcut within 160 chars | Built | Remaining Scope (Issue #9) |
| FR-28 | **Admin console CRUD & audit:** staff roles, offices, stages, and SMS templates management with hash-chained audit logging | Built | Remaining Scope (Issue #10) |

## 3. Non-Functional Requirements (Constraint Card)
- **NFR-01 Performance:** Status lookup p95 <= 500 ms at 500 concurrent users (load tested).
- **NFR-02 Throughput:** Notification pipeline capable of dispatching 50,000 SMS in <= 15 min (async seam / batch dispatch).
- **NFR-03 Availability:** >= 99.5% monthly uptime target.
- **NFR-04 Capacity & Retention:** 150,000 applications/year; 10-year retention policy.
- **NFR-05 Device Limits:** Applicant access works on basic feature phones (USSD/SMS) and 320 px mobile browsers; officer console runs smoothly on 4 GB RAM PCs.
- **NFR-06 Code Quality & Coverage:** New code >= 80% line / 70% branch coverage; whole system >= 50% by `v1.0.0`; new functions CC <= 10 and <= 40 lines; top 3 as-built complexity hotspots reduced.
- **NFR-07 Budget:** Cost to date and rollout within MWK 15,000,000 cap, evaluated at 22% annual discount rate.
- **NFR-08 ISO 25010 Focus:** Functional correctness, availability, confidentiality.

## 4. Full Use-Case Specifications (3)

### UC-01: Officer Registers Application and Triggers Notification
- **Actor:** Immigration Counter Clerk (`officer`)
- **Preconditions:** Officer authenticated; assigned to Mangochi office (`MGC`).
- **Main Flow:**
  1. Officer opens `/officer/applications/new/` and enters National ID, name, DOB, phone, language, and application type.
  2. System validates E.164 Malawi phone (`+265...`) and National ID, creates/updates `Applicant`, generates `MW-MGC-{YEAR}-{SEQ:05d}`.
  3. System records `StageChange(None -> received)`, appends hash-chained `AuditLog`, and publishes `StageChangedEvent`.
  4. Notification dispatcher formats `received` template in applicant's language, creates idempotent `Notification` row, dispatches via gateway, and displays tracking code confirmation.
- **Alternate / Exception Flow:** Invalid phone/ID returns field errors without saving; gateway failure leaves row `failed` with `next_retry_at` scheduled for exponential backoff retry.

### UC-02: Officer Updates Status and Synchronises All Channels
- **Actor:** Counter Clerk (`officer`) or Approving Officer (`supervisor`)
- **Preconditions:** Application exists in officer's office; user authenticated.
- **Main Flow:**
  1. Staff opens `/officer/applications/<code>/` (or uses API `PUT /api/applications/<code>/stage/`) and triggers `advance`, `hold`, `resume`, `collect`, or supervisor `move`/`reject`.
  2. System enforces role gates and mandatory reason for hold/skip/rollback/reject.
  3. System atomically updates `Application.current_stage` & `status`, inserts `StageChange`, appends tamper-evident `AuditLog` (`officer`, `timestamp`, `reason`, `entry_hash`).
  4. Event dispatcher notifies Web/USSD state (immediately reflected on next query) and SMS channel handler (respecting idempotency key) within 60 seconds.
- **Exception Flow:** Non-supervisor attempting skip/reject receives HTTP 403 / error banner; duplicate trigger within same transition is ignored by idempotency check.

### UC-03: Applicant Checks Status Privately via Web or USSD
- **Actor:** Passport Applicant
- **Preconditions:** Application exists in database.
- **Main Flow (Web):**
  1. Applicant opens `/` (EN or NY), enters `tracking_code` (or National ID) plus `date_of_birth` (or requests/enters 6-digit OTP sent to registered phone).
  2. System checks sliding IP + identifier rate limits (`<= 5` failures / 15 min).
  3. On match, system logs hashed `LookupAttempt(success=True)`, sets session token with 15-min TTL, and redirects to `/status/?code=...` showing stage, masked phone, collection hours, and message history.
- **Main Flow (USSD):** Applicant dials `*384*123#`, selects `1 Check status`, enters identifier + DOB/OTP or registered phone (`0`), receives `<= 160`-char `END` message matching Web/SMS status.
- **Exception Flow:** Any mismatch or rate-limit breach returns identical generic error (`We could not match those details`) to block enumeration.
