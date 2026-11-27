# Process and Metrics — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. Pre-baseline process (from commit history, 2026-11-18)
The project began with an initial commit, followed by a second commit and a README expansion, then test/cache additions. The as-built baseline (`v0.7-asbuilt`) was tagged after characterisation tests reached 24 tests (71% coverage).

## 2. Spiral model (2 risk-driven loops)
- **Loop 1:** Baseline verification, characterisation tests, requirements baseline (SRS, traceability, KAOS). Risk: unknown defects in `core/views.py`.
- **Loop 2:** Signature Challenge implementation (private lookup, tamper-evident audit, channel consistency, reliable notifications), hotspot refactoring, quality gates.

## 3. Contrast
- **Waterfall:** would fix all requirements up front; poor fit for discovered defects.
- **Scrum:** iterative but less explicit risk analysis than Spiral.
- **V-model:** strong verification pairing, but less adaptive to emerging Signature Challenge gaps.

## 4. Challenge register (>= 8)
1. `core/views.py` god module (CCN 34).
2. Missing DOB/OTP/private lookup.
3. Audit log not tamper-evident.
4. SMS duplicates on repeated triggers.
5. `resume` omitted SMS.
6. USSD 160-char limit.
7. Load-test gate failure under 500 users.
8. Flake8 line-length debt.

## 5. Effort/defects/rework
- Tests grew from 6 to 62.
- Coverage: 52% (6 tests) -> 73% (62 tests).
- Defects fixed: 7 documented in `docs/05-maintenance/debug-log-and-maintenance.md`.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`