# Reliability and SCM — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-25

## 1. Goel-Okumoto NHPP (8-hour)
- Fit from `scripts/nhpp_fit.py`: a=37.5938, b=0.0569.
- m(8)=13.7425, m(12)=18.5957, lambda(8)=1.3565.

## 2. SCM plan (1 page)
- Trunk-based development on `develop`, tags for baselines, PR review, CI gates, immutable audit log.

## 3. SBOM summary
- Generated from `requirements.txt` / `pip freeze` into `docs/07-management/sbom.json`.
- Checksums for key scripts/docs in `docs/07-management/checksums-sha256.txt`.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`