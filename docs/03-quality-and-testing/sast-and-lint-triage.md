# SAST and Lint Triage — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. Bandit triage
- 6 Low (B311) findings in `core/management/commands/seed_demo.py` (demo data generator uses `random`).
- 0 Medium, 0 High.
- Disposition: accepted for demo generator only; production seeding must use `secrets`.

## 2. Flake8 cleanup summary
- Trivial issues fixed: unused imports (F401), unused variables (F841), blank-line/spacing (E302/E303/E304/E305/W292/E202/E701/E128).
- Remaining: 320 E501 line-length issues (mostly long model field definitions and templates); deferred to a formatting pass.
- Post-cleanup flake8 (excluding migrations and `seed_demo.py`): 344 total issues (320 E501 + 24 spacing/import residuals).

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`