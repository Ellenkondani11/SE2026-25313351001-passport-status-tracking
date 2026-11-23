# Token: EK01-HAZY-VM26 | Student: 25313351001
Feature: PassTrack Consistent, Private, Auditable Status Tracking

  Scenario: 1. Dual-factor lookup with tracking code and date of birth succeeds
    Given an application "MW-MGC-2026-00001" for applicant with DOB "1995-04-12"
    When the applicant submits tracking code "MW-MGC-2026-00001" and DOB "1995-04-12" on "/"
    Then the system redirects to "/status/?code=MW-MGC-2026-00001"
    And the phone number is displayed masked as "+265 99* *** 567"

  Scenario: 2. Private lookup with one-time code (OTP) succeeds within expiry
    Given an applicant requests an OTP for "MW-MGC-2026-00001"
    When the applicant submits the valid 6-digit OTP within 10 minutes
    Then the status page displays the current stage and notification history

  Scenario: 3. Wrong DOB or expired OTP returns generic mismatch error
    Given an application "MW-MGC-2026-00001" with DOB "1995-04-12"
    When the applicant submits DOB "1990-01-01" or an expired OTP
    Then the system displays "We could not match those details" without revealing which factor failed

  Scenario: 4. Rate limiting stops enumeration across tracking codes from one IP
    Given 5 failed lookup attempts have occurred from the same IP within 15 minutes
    When a 6th lookup attempt is made with valid credentials
    Then the lookup is blocked with the generic mismatch error and logged in LookupAttempt

  Scenario: 5. Stage update synchronises Web, SMS, and USSD consistently
    Given application "MW-MGC-2026-00001" is at stage "received"
    When an officer advances the application to "under_review"
    Then the web status page, the queued SMS body, and USSD menu option 1 all report "Under review" within 60 seconds

  Scenario: 6. Resuming an on-hold application triggers a notification and syncs channels
    Given application "MW-MGC-2026-00001" is "on_hold" with previous stage "under_review"
    When an officer resumes the application
    Then its stage returns to "under_review" and a resumption SMS notification is dispatched

  Scenario: 7. Notification retries use exponential backoff and stop at max retries
    Given a failed SMS notification with retry_count 0
    When retry scheduling runs after failure 1, 2, and 3
    Then next_retry_at increases exponentially by 2^retry_count minutes
    And retries cease once max_retries is reached

  Scenario: 8. Duplicate notifications are prevented via idempotency key
    Given an SMS notification was already created for stage change 42
    When the stage-change notification handler is invoked again for stage change 42
    Then no second Notification row is created

  Scenario: 9. Delivery callback stores status and rejects invalid tokens
    Given SMS_CALLBACK_TOKEN is configured
    When a provider posts a delivery callback with a wrong X-Callback-Token
    Then the API returns HTTP 403 and leaves the notification unchanged

  Scenario: 10. Tamper-evident audit log detects direct modification
    Given 3 sequential AuditLog entries with hash chaining
    When an entry's details or action are altered directly in the database
    Then the audit integrity verification reports a broken hash chain

  Scenario: 11. Role-based access control blocks officers from supervisor/admin actions
    Given a user signed in with role "officer"
    When the officer requests "/officer/reports/" or attempts to reject an application
    Then the system denies the action with HTTP 403 or a supervisor-required error

  Scenario: 12. USSD Chichewa responses stay at or under 160 characters
    Given an applicant selects Chichewa via USSD option "3*2"
    When the applicant checks status or collection hours
    Then the USSD reply starts with "END" and has length <= 160 characters
