# User Manual — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. Applicant guide
### Web
1. Open the public portal.
2. Enter National ID and phone number or tracking code.
3. Optionally use tracking code + date of birth, or request a one-time code.
4. View status, masked phone, collection hours, and notification history.

### SMS
- Receive stage-update SMS in English or Chichewa.
- Delivery status is tracked automatically.

### USSD (`*384*123#`)
1. Dial `*384*123#`.
2. Choose `1 Check status`, `2 Collection information`, or `3 Change language`.
3. Follow prompts; replies are at most 160 characters.

## 2. Officer guide
- Log in at `/officer/login/`.
- Register applications, advance stages, hold/resume, correct contact details with ID check.
- Bulk update and CSV export available.

## 3. Supervisor guide
- Approve skips/rollbacks/rejections with reasons.
- View reports and CSV exports.

## 4. Admin guide
- Manage staff roles, offices, stages, and SMS templates in `/officer/admin/`.
- Verify audit chain via `/officer/audit/` or `python manage.py verify_audit`.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`