# Operations Runbook — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. Clean-clone setup
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` (if present) and set `DJANGO_SECRET_KEY`.

## 2. Migrations
- `python manage.py migrate`

## 3. Seed demo data
- `python manage.py seed_demo` or `python manage.py seed_demo --reset`

## 4. Verification
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test`
- `python manage.py verify_slices`
- `python manage.py verify_audit`

## 5. Notifications
- Retry queued/failed: `python manage.py send_pending`
- Configure Africa's Talking via `PASTNS_SMS_GATEWAY=africastalking`, `AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID`, `SMS_CALLBACK_TOKEN`.

## 6. Backup/restore
- SQLite: copy `db.sqlite3`.
- PostgreSQL: use `pg_dump` / `pg_restore`.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`