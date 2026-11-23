# Reengineering the Weakest Module — `core/views.py`

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. Before (`v0.7-asbuilt`)
- `core/views.py`: 699 NLOC, avg CCN 7.2, 36% initial coverage.
- `application_detail`: CCN 34, 106 lines.
- `ussd_endpoint`: CCN 30, 68 lines.
- `_ussd_collection_response`: CCN 16.

## 2. Phased reengineering
1. **Inventory & characterisation** (`v0.7`): 24 characterisation tests, 71% coverage.
2. **Extract helpers**: `_handle_*` action handlers, `_ussd_*` sub-handlers, `_api_*` validators.
3. **Introduce domain service**: `transition_application_stage` in `core/services.py`.
4. **Introduce event bus**: `StageEventBus` in `core/channels.py` for channel sync.
5. **Verify**: lizard, bandit, coverage, full test suite.

## 3. After (`v0.95`, measured)
- `core/views.py`: 881 NLOC (modular handlers), 0 lizard warnings (CCN > 15).
- `application_detail`: CCN 1 (dispatcher), ~25 lines.
- `ussd_endpoint`: CCN ~5 (dispatcher), ~30 lines.
- `_ussd_collection_response`: CCN 1 (delegated), ~5 lines.
- Test suite: 62 tests passing; overall coverage 73%.

## 4. Evidence
- `python3 manage.py test` → 62 OK.
- `lizard` warning count 0 for the refactored module set.
- `bandit`: 0 High, 0 Medium, 6 Low (B311 in `seed_demo.py`).

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`