# Architecture and Data Design — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. As-Built vs Refactored Architecture

### 1.1 C4 Context (narrative)
PassTrack (PASTNS) is a passport status tracking system for Malawi's Department of Immigration and Citizenship Services (Mangochi pilot). Actors: Applicant, Immigration Counter Clerk (Officer), Approving Officer (Supervisor), ICT Manager (Admin), and the Africa's Talking SMS/USSD gateway. The system exposes Web, SMS, and USSD channels over a single Django 4.2 LTS application backed by SQLite (demo) / PostgreSQL (production).

### 1.2 C4 Container (narrative)
- **Web container**: Django templates + static assets (`core/templates`, `core/static`).
- **API container**: Django REST Framework (`core/api.py`) with `TokenAuthentication`.
- **Domain container**: `core/models.py`, `core/services.py`, `core/channels.py`, `core/lookup.py`, `core/audit_chain.py`.
- **Data container**: relational database accessed via Django ORM.
- **Integration container**: Africa's Talking SMS/USSD callback seam (`core/services.py`, `core/views.py:ussd_endpoint`).

### 1.3 As-Built (`v0.7-asbuilt`) weaknesses
- `core/views.py` was a 699-NLOC god module (avg CCN 7.2), with `application_detail` at CCN 34 and `ussd_endpoint` at CCN 30.
- Channel text was duplicated between `Stage.applicant_text_*` and `SmsTemplate.body_*`.
- `resume` from `on_hold` did not notify SMS.
- No exponential backoff, idempotency key, or callback-token enforcement beyond an optional token.
- `AuditLog` was append-only in the ORM only (no hash chain).

### 1.4 Refactored (`v0.95`) architecture
The refactored system uses an **Event-Driven architecture** centred on `core/channels.py:StageEventBus` and `StageChangedEvent`. Domain transitions are funnelled through `core/services.py:transition_application_stage`, which publishes events to registered observers:
- `WebSyncObserver` (web state is read from the shared database).
- `SmsChannelObserver` (dispatches SMS via `notify_stage` with `idempotency_key=f"stagechange:{change.pk}:sms"`).
- `UssdSyncObserver` (USSD reads the same database on the next request).

This guarantees that Web, SMS, and USSD converge on the same stage within the 60-second SLA.

## 2. Design Patterns (exact classes/files)
1. **Strategy** — `core/channels.py`: `ChannelStrategy` (ABC), `WebChannelStrategy`, `SmsChannelStrategy`, `UssdChannelStrategy`. All build a consistent view from a shared `StatusSnapshot`.
2. **Observer** — `core/channels.py`: `StageChangedEvent`, `StageObserver`, `StageEventBus`, `WebSyncObserver`, `SmsChannelObserver`, `UssdSyncObserver`.
3. **Template Method** — `core/channels.py`: `BaseNotificationDispatcher` with `dispatch()` skeleton (`prepare -> deliver -> record_outcome -> schedule_backoff -> audit_dispatch`), implemented by `SmsDispatchFlow` and `EmailDispatchFlow`.

## 3. Data Design (Django schema, 3NF)

### 3.1 Models (`core/models.py`)
- `Office` (PK `id`): `code` (unique), `name`, `district`, `phone`, `address`, `collection_hours`, `collection_hours_ny`.
- `Profile` (PK `id`, FK `user`): `role`, `office`.
- `Applicant` (PK `id`): `national_id` (unique), `first_name`, `surname`, `phone`, `email`, `language`, `date_of_birth` (nullable), `created_at`. PII is hashed for lookup/audit via `hash_sensitive`.
- `Stage` (PK `id`): `key` (unique), `order`, `name`, `applicant_text_en`, `applicant_text_ny`, `colour`, `notify`, `is_terminal`.
- `Application` (PK `id`): `tracking_code` (unique), FK `applicant`, FK `office`, `application_type`, FK `current_stage`, `status`, `received_at`, `updated_at`, FK `previous_stage`. Indexes: `(office, status, current_stage)`, `(received_at)`.
- `StageChange` (PK `id`): FK `application`, FK `from_stage`, FK `to_stage`, FK `by_user`, `reason`, `at`.
- `Notification` (PK `id`): FK `application`, `channel`, `to`, `template_key`, `body`, `status`, `provider_ref`, `error`, `retry_count`, `max_retries`, `next_retry_at` (indexed), `idempotency_key` (unique, nullable), `created_at`, `sent_at`, `updated_at`. Index: `(status, created_at)`.
- `SmsTemplate` (PK `id`): `key` (unique), `name`, `body_en`, `body_ny`, `is_active`.
- `UssdSession` (PK `session_id`): `phone`, `state` (JSON), `started_at`, `updated_at`.
- `AuditLog` (PK `id`): FK `user`, `action`, `object_type`, `object_id`, `details` (JSON), `ip`, `at` (indexed), `reason`, `prev_hash`, `entry_hash` (indexed). Immutable in the ORM (`save`/`delete` raise `ValueError`); hash-chained via `core/audit_chain.py`.
- `LookupAttempt` (PK `id`): `national_id_hash` (indexed), `ip` (indexed), `success`, `at` (indexed).
- `LoginAttempt` (PK `id`): `username_hash` (indexed), `ip` (indexed), `success`, `at` (indexed).
- `OfficerNote` (PK `id`): FK `application`, FK `user`, `body`, `created_at`.
- `LookupOtp` (PK `id`): FK `application`, `code_hash`, `expires_at`, `used_at`, `created_at`.

### 3.2 Normalisation
All entities are in Third Normal Form (3NF): non-key attributes depend only on the primary key; foreign keys represent relationships. PII is never stored in audit details in raw form; identifiers are hashed with `hash_sensitive`.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`