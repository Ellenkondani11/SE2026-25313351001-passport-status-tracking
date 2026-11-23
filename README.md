# PASTNS — Mangochi passport status pilot

**Passport Application Status Tracking and Notification System**  
A status tracking and notification platform for Mangochi passport applicants — built so that an applicant does not have to travel to the immigration office just to hear whether their passport is ready. Scoped to the Mangochi Immigration Office pilot.

> An applicant should not have to travel to Mangochi just to hear “not ready”. PASTNS records stage changes and makes the latest status available by a low-bandwidth public portal, SMS and USSD.

## The intention

PASTNS is the passport status tracking and notification system for the Mangochi Immigration Office pilot, developed as Ellen Kondani's final-year project.

The problem it addresses: a passport applicant currently has no low-friction way to learn how their application is progressing. Status lives with the immigration office and is typically only communicated when the applicant physically visits — so people often hear “not ready” only when they arrive, or not at all.

The intention is to make application status transparent and reachable:

- Officers record stage changes (received, under review, approved, printed, ready, collected, …) against a real application.
- Applicants learn about stage changes through a low-bandwidth public portal, SMS or USSD — in English or Chichewa — without having to travel.
- The system keeps an auditable trail (stage changes, notifications, notes, contact corrections) so accountability and future policy review do not depend on informal conversations.

The Mangochi pilot is the first real deployment context for this intention; the design is expected to generalise to further offices over time.

## Who it's for

- **Applicants** — public users who need a private way to check status without travelling to Mangochi.
- **Immigration officers** — staff who register applications, advance stages, notify applicants and account for progress.
- **Supervisors and administrators** — staff who oversee officers, run batch operations and reports, and govern exceptions.

## What is built

This is the current working scope of the Mangochi pilot build: a runnable Django 4.2 application covering the full officer–applicant status loop.

- **Public portal** (`/`): dual-factor lookup with National ID + phone or tracking code, generic mismatch errors, DB-backed limit of five attempts per National ID/IP in 15 minutes, bilingual English/Chichewa selector (`?lang=ny`, remembered in a cookie), masked phone, stage tracker, collection details and message history.
- **USSD** (`POST /api/ussd/`): Africa's Talking-style `sessionId`, `serviceCode`, `phoneNumber`, `text` form protocol. The public phone simulator is `/ussd-demo/`; the staff simulator is `/officer/ussd-sim/`. Both call the real endpoint.
- **Officer workbench** (`/officer/`): office-scoped worklist, 50-row pagination, search and filters, new application registration, stage actions, notes, contact correction, timeline, batch stage actions, SMS outbox, CSV export, reports and audit log.
- **Administrator console** (`/officer/admin/`): staff roles, office details, stage copy/notification switches and SMS templates with live sample preview and GSM/Unicode character counts.
- **API**: token-authenticated application creation/detail/stage endpoints, delivery callback and Swagger UI at `/api/docs/` (OpenAPI JSON/YAML at `/api/schema/`).
- **Audit and lookup controls**: National IDs are hashed in lookup-attempt/audit records and masked in list views. Contact corrections require an officer and reason. Audit entries are append-only in the application model and have no delete/edit UI.

The project is deliberately **not** an applicant self-registration or passport-production system. See [Scope boundaries and roadmap](#scope-boundaries-and-roadmap).

## Run the current build locally

Requires Python 3.10+ (tested here with Python 3.13), SQLite for the pilot build, and pip.

```bash
cd pastns
python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
cp .env.example .env                # edit DJANGO_SECRET_KEY before deployment
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/`. SQLite is the default. `DATABASE_URL` can be changed to a PostgreSQL URL for a deployment; `dj-database-url` parses it and `psycopg` is included. Use a real random secret, `DJANGO_DEBUG=False`, a restricted `DJANGO_ALLOWED_HOSTS`, HTTPS, and a production static-file server before exposing a deployment.

The development preview for this workspace is already running on port `8000`. If CSS or JavaScript has just changed, hard-refresh the preview; static links carry a `?v=8` cache-buster.

### Demo users

| Username | Password | Role |
|---|---|---|
| `officer` | `officer123` | Officer |
| `supervisor` | `super123` | Supervisor |
| `admin` | `admin123` | Administrator |

These are **demo-only** credentials. Change them before any non-demo use. `seed_demo` prints the supervisor API token after seeding; to retrieve it later:

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; from rest_framework.authtoken.models import Token; print(Token.objects.get(user__username='supervisor').key)"
```

Sample records use synthetic 13-digit National IDs. For example:

- `MW-MGC-2026-00001` → `0000000000001`
- `MW-MGC-2026-00002` → `0000000000002`

Use the matching applicant phone or tracking code as the second lookup factor. `python manage.py seed_demo --reset` recreates the sample application set; do this only in a demo database.

## Tests and verification

```bash
python manage.py test
python manage.py verify_slices
```

`verify_slices` runs the three end-to-end vertical slices (web status, SMS outbox + delivery callback, USSD status) and exits non-zero if any fail.

The browser test is optional for normal runtime, and is in `requirements-dev.txt`:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
# Start `python manage.py runserver 0.0.0.0:8000` in another terminal.
python scripts/e2e_playwright.py
```

Override the target with `PASTNS_BASE_URL`, for example `PASTNS_BASE_URL=https://<preview-host> python scripts/e2e_playwright.py`. The Playwright flow signs in, registers an application, advances it to Approved, looks it up in the public portal, enters the same application in the USSD simulator, marks it Printed in a bulk action, and opens supervisor reports. It also fails on browser JavaScript exceptions.

## Six-minute demo walkthrough

1. **Public service (45 sec):** use a 320 px-wide browser viewport, switch to Chichewa, and look up a sample with National ID + code. Point out the generic error behaviour and masked phone.
2. **Officer registration (60 sec):** sign in as `officer`, register a synthetic applicant, and show the generated `MW-MGC-2026-xxxxx` code and exact Received SMS in the confirmation view.
3. **Stage change + outbox (75 sec):** open the application, advance it to Under review, then Approved. Show the stage timeline and the notification row/body. The default console gateway is explicitly simulated.
4. **Applicant update (45 sec):** return to the public portal, look up with the new code and ID, show the updated tracker and notification history.
5. **USSD (60 sec):** use `/officer/ussd-sim/` or `/ussd-demo/`; select Check status, enter the National ID, then enter the tracking code. The simulator posts each turn to `/api/ussd/`.
6. **Batch + accountability (75 sec):** return to the worklist, filter Approved, select applications and Mark as Printed. Open the outbox, then sign in as `supervisor` and show Reports and Audit log.

## Architecture notes

### Data model

The `core` app contains `Office`, Django `User` + `Profile` roles, `Applicant`, `Application`, configurable `Stage`, `StageChange`, `Notification` (outbox), `SmsTemplate`, `UssdSession`, `AuditLog`, `LookupAttempt`, `LoginAttempt`, and `OfficerNote`. Tracking codes follow `MW-{OFFICE}-{YEAR}-{SEQ:05d}`. Seed IDs and contact details are synthetic.

### Notification gateway and dispatch

`notify(application, event)` creates a durable `Notification` outbox row and calls a small gateway interface synchronously:

- `ConsoleGateway` is the safe default. It writes the message to the outbox/log and marks it **sent (simulated)**; it does not send a real SMS.
- `AfricasTalkingGateway` is enabled with `PASTNS_SMS_GATEWAY=africastalking` plus `AT_USERNAME`, `AT_API_KEY` and optional `AT_SENDER_ID`.
- `SMTPGateway` is available for email channel calls. The pilot currently sends SMS by default; email fan-out is not turned on automatically.

Failed or queued records can be retried by the officer in the outbox or by `python manage.py send_pending`. A delivery callback can post a notification ID/provider reference plus status to `/api/sms/delivery/`; set `SMS_CALLBACK_TOKEN` and pass the same value in `X-Callback-Token` for a shared-secret check. **Celery/Redis are out of scope**: when volume requires asynchronous dispatch, the intended seam is the `NotificationGateway`/dispatcher class, not a rewrite of application workflow.

### Authentication and deployment notes

The web console uses Django sessions and CSRF-protected forms. Session expiry is 30 minutes of inactivity. Five recent failed sign-ins for a username/IP pair trigger a 15-minute lockout. Public lookup attempts are stored with a keyed hash of the National ID and IP. API calls use DRF token auth. The USSD and provider callback endpoints are machine callbacks; configure provider secrets and network restrictions for production. When the reverse proxy sends `X-Forwarded-Proto: https` (or the request host is a trusted `*.e2b.app` preview), middleware adds `Secure; SameSite=None; Partitioned` to session/CSRF/language cookies for embedded HTTPS previews; plain-HTTP localhost cookies remain usable. `SECURE_PROXY_SSL_HEADER`, CSP `frame-ancestors`, security headers and HSTS settings are configured in `config/settings.py`.

Inter is self-hosted as a compact WOFF2 subset in `core/static/fonts/` under the SIL Open Font License. English and Chichewa messages use Django's gettext catalog (`core/locale/ny/LC_MESSAGES/django.po` plus compiled `.mo`); after editing the PO file, rebuild it with `python scripts/compile_catalog.py` (or Django `compilemessages` if GNU gettext is installed). The Chichewa SMS/copy is a project draft and **must be checked by a native Chichewa speaker before a pilot**.

## API quick reference

All application APIs require `Authorization: Token <token>` and are office-scoped.

```http
POST /api/applications/
Content-Type: application/json
Authorization: Token <token>
```

```json
{
  "national_id": "1234567890123",
  "first_name": "Chisomo",
  "surname": "Banda",
  "phone": "+265991234567",
  "language": "ny",
  "application_type": "new"
}
```

Other endpoints: `GET /api/applications/{tracking_code}/`, `PUT /api/applications/{tracking_code}/stage/` with `{"stage":"approved","reason":"..."}`, `POST /api/ussd/`, and `POST /api/sms/delivery/`. Backward/skip stage changes through the API require supervisor/admin plus a reason. Use `/api/docs/` for the interactive schema.

## Scope boundaries and roadmap

These are deliberate scope boundaries for the Mangochi pilot, not unfinished MVP work; each item records what the project intentionally does not attempt yet and where the intention goes next.

- `ConsoleGateway` simulates message acceptance; no live delivery is claimed unless Africa's Talking/SMTP is configured. A provider callback, short-code approval, sender ID, airtime/billing and service credentials are deployment work.
- Africa's Talking USSD is represented by its callback protocol and simulator; this workspace does not provision the real `*384*123#` shortcode or test with a Malawi carrier.
- Chichewa strings and SMS templates are drafts awaiting native-speaker review. SMS concatenation/Unicode segment billing should be checked against the selected carrier/provider.
- Data is synthetic and SQLite is for a single-node demonstration. No data-protection impact assessment, penetration test, independent security review, backup/restore procedure, operational monitoring, or production SLA has been completed.
- One office is seeded. Multi-office routing, mobile app, payments, biometrics, applicant self-registration, passport production integration and analytics beyond the four simple reports are intentionally cut.
- The administrator UI is a project console, not a full identity governance workflow. Supervisor approval for exceptional changes is implemented in the demo but should be validated against Department policy.
- The synchronous dispatcher is intentionally simple: retries are manual/command-driven, not guaranteed background delivery. Celery/Redis are not installed.
