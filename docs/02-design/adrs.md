# Architecture Decision Records — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## ADR-001 [Retrospective] Technology stack
**Status:** Accepted (retrospective)  
**Context:** Need a stable, well-understood stack for a government pilot with limited budget.  
**Decision:** Django 4.2 LTS, Django REST Framework, SQLite (demo) / PostgreSQL (production), self-hosted Inter font, Django i18n (`en`/`ny`).  
**Consequences:** Mature ecosystem, built-in security, easy deployment; horizontal scaling deferred.

## ADR-002 [Retrospective] Synchronous `NotificationGateway` seam
**Status:** Accepted (retrospective)  
**Context:** SMS throughput target is 50,000 SMS in ≤ 15 min; MVP avoids Celery/Redis.  
**Decision:** Keep a synchronous `NotificationGateway` seam (`ConsoleGateway`, `AfricasTalkingGateway`, `SMTPGateway`) invoked from `send_notification` / `BaseNotificationDispatcher`.  
**Consequences:** Simple deployment; throughput ceiling is lower than async; seam allows future async replacement.

## ADR-003 Private lookup authentication
**Status:** Accepted  
**Context:** Public status lookup must be private and resist enumeration.  
**Decision:** Require `tracking_code` (or `national_id`) plus `date_of_birth` OR a 6-digit time-limited OTP; enforce per-identifier and per-IP throttling (5 failures / 15 min); expire the verified session after 15 minutes.  
**Consequences:** Stronger privacy; added `Applicant.date_of_birth` and `LookupOtp` model.

## ADR-004 Reliable notification retries & deduplication
**Status:** Accepted  
**Context:** Duplicate SMS and unbounded retries cause cost and inconsistency.  
**Decision:** Add `retry_count`, `max_retries`, `next_retry_at`, and `idempotency_key` to `Notification`; exponential backoff `2^(n-1)` minutes; `send_pending` skips future-due and exhausted rows; delivery callbacks require `SMS_CALLBACK_TOKEN` when configured.  
**Consequences:** Predictable retry cost; idempotent dispatch.

## ADR-005 Tamper-evident audit log & channel sync
**Status:** Accepted  
**Context:** Auditability and cross-channel consistency are Signature Challenge properties.  
**Decision:** Hash-chain `AuditLog` (`prev_hash`/`entry_hash`, SHA-256, starting from `GENESIS`) with `verify_audit_chain()` and `verify_audit` command; sync channels via `StageEventBus` + Observer/Strategy/Template Method in `core/channels.py`.  
**Consequences:** Tamper detection; consistent stage propagation within 60 seconds.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`