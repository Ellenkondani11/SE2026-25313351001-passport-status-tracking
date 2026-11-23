# Component and UI Design — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. Notification Dispatcher Specification

### 1.1 Classes
- `core/channels.py:BaseNotificationDispatcher`
- `core/channels.py:SmsDispatchFlow`
- `core/channels.py:EmailDispatchFlow`

### 1.2 Pseudocode
```
dispatch(notification, actor, ip):
    execution_order = []
    execution_order.append("prepare")
    prepare(notification)            # status=queued, error=""
    execution_order.append("deliver")
    result = deliver(notification)  # gateway.send
    execution_order.append("record_outcome")
    record_outcome(notification, result)
    execution_order.append("schedule_backoff")
    schedule_backoff(notification, result)  # retry_count++, next_retry_at = now + 2^(n-1) min
    execution_order.append("audit_dispatch")
    write_audit(notification, result, actor, ip)
    return notification
```

### 1.3 Decision table
| Gateway result | `status` | `retry_count` | `next_retry_at` | Audit action |
|---|---|---|---|---|
| sent/delivered | sent/delivered | unchanged | `null` | `notification_dispatched` |
| failed | failed | +1 | `now + 2^(retry_count-1)` min | `notification_failed` |

## 2. Screen Redesign Rationale
- **Public lookup (`public_home.html`)**: retains `#national-id` and `#phone-or-code`; adds optional tracking code, date of birth, and OTP inputs plus "Send one-time code" action. Generic errors only.
- **Status page (`public_status.html`)**: shows stage, masked phone, collection hours, and notification history; session expires after 15 minutes.
- **Officer detail (`application_detail.html`)**: split into single-purpose action handlers dispatched by a dictionary; resume now triggers SMS via the event bus.

## 3. SUS Questionnaire Protocol (blank)
Participant rows to be completed with 5 fellow students.

| Participant | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Q9 | Q10 | SUS score |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [TO BE COMPLETED WITH 5 FELLOW STUDENTS] |  |  |  |  |  |  |  |  |  |  |  |
| [TO BE COMPLETED WITH 5 FELLOW STUDENTS] |  |  |  |  |  |  |  |  |  |  |  |
| [TO BE COMPLETED WITH 5 FELLOW STUDENTS] |  |  |  |  |  |  |  |  |  |  |  |
| [TO BE COMPLETED WITH 5 FELLOW STUDENTS] |  |  |  |  |  |  |  |  |  |  |  |
| [TO BE COMPLETED WITH 5 FELLOW STUDENTS] |  |  |  |  |  |  |  |  |  |  |  |

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`