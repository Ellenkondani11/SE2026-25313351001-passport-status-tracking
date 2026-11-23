# AI Disclosure — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Date:** 2026-11-23
- **Tooling:** OpenCode coding agent harness with an AI assistant (model: Beam Free) operating in the repository at `/home/hanieyo/Documents/PASTNS`.

## 1. Workflow
1. The assistant inspected the repository (tests, docs, source) read-only.
2. The assistant ran the existing Django test suite (`python3 manage.py test`) to establish a green baseline (24/24 passing) before any edits.
3. Documentation repairs and new artifacts were produced with targeted edits; no Python files under `core/` were modified.
4. The test suite was re-run after edits to confirm no regression.

## 2. Prompts / Instructions Used
- Inspect `tests/test_characterisation.py`, `docs/00-baseline/as-built-baseline.md`, `docs/01-requirements/srs.md`, `docs/01-requirements/acceptance.feature`, `docs/01-requirements/traceability-matrix.md`, and `docs/logbook/2026-11-21.md` for truncated/incomplete text.
- Run `python3 manage.py test` and confirm all 24 tests pass.
- Repair incomplete sections, ensure every doc includes token `EK01-HAZY-VM26` and registration number `25313351001`, preserving verified v0.7-asbuilt metrics.
- Ensure SRS contains >= 20 functional requirements tagged Built/Partial/New (FR-17..FR-24 for the 4 Signature Challenge properties and >= 4 remaining-scope features), all Constraint Card NFRs, and 3 full use-case specs.
- Create `docs/01-requirements/kaos-goal-model.md`, `docs/diagrams/kaos-goal-model.mmd`, `docs/logbook/2026-11-23.md`, and `docs/ai-disclosure.md`.
- Re-run `python3 manage.py test` and summarize.

## 3. Verification
- Baseline run: 24 tests OK.
- Post-edit run: 24 tests OK.
- No changes to `core/*.py`; documentation-only edits plus new doc/diagram files.
- Metrics preserved: 6 initial tests (52% coverage) -> 24 characterisation tests (71% coverage); lizard 1,535 NLOC, avg CCN 5.0, 7 warnings; bandit 0 High / 0 Medium / 6 Low (B311); flake8 111 lint issues.

## 4. Implementation Update (2026-11-23)
- Implemented Signature Challenge #3 (private lookup via tracking code + DOB or 6-digit OTP, IP/identifier rate limits, 15-minute session TTL) in `core/lookup.py`, `core/models.py`, `core/forms.py`, `core/api.py`, templates, and `core/urls.py`.
- Implemented Signature Challenge #4 (tamper-evident hash-chained `AuditLog` with `reason`, `prev_hash`, `entry_hash`, `verify_audit_chain()`, `verify_audit` command, and audit-log integrity badge) in `core/audit_chain.py`, `core/models.py`, `core/utils.py`, `core/views.py`, and `core/templates/core/audit_log.html`.
- Added `tests/test_signature_challenge.py` (13 tests); full suite now 37 passing.
- Quality checks: `makemigrations --check --dry-run` reports no changes; lizard reports no new function with CCN > 10 or length > 40; bandit reports 0 High / 0 Medium / 6 Low.

## 5. Human Oversight
All generated documentation was reviewed for consistency with the as-built baseline and the Signature Challenge gap analysis before being committed to the working tree. Final approval rests with the student (Ellen Kondani, 25313351001).