# Characterisation, Crisis and Ethics — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23

## 1. System classification and failure-rate curve
PassTrack is a multi-channel e-government system (Web, SMS, USSD) with a software failure curve dominated by configuration, integration, and data issues rather than hardware wear. Unlike a physical passport printer's bathtub curve (infant mortality -> useful life -> wear-out), the software curve shows spikes after releases and configuration changes, with gradual improvement through characterisation tests and monitoring.

## 2. 1999 UK Passport Agency crisis fishbone
Causes and PASTNS controls:
- **People:** staff overload -> RBAC, officer workbench, audit trail.
- **Process:** unmanaged change -> `transition_application_stage`, hash-chained `AuditLog`.
- **Technology:** single-channel bottleneck -> Web/SMS/USSD with `StageEventBus`.
- **Policy:** unclear eligibility -> stage definitions and reports.
- **Volume:** seasonal surge -> load-test gate (currently failing; production recommendation documented).
- **Communication:** applicants uninformed -> SMS notifications with exponential backoff.

Remaining gaps: production-grade throughput (PostgreSQL + multi-worker WSGI), full observability, and capacity planning.

## 3. Ethics dilemma (one page)
An officer requests a hidden "VIP" queue-jumping flag. Evaluation:
- **ACM/IEEE-CS Software Engineering Code of Ethics**: software engineers must act in the public interest and not discriminate; a hidden VIP flag undermines fairness and transparency.
- **Malawi Data Protection Act**: processing must be lawful, fair, and transparent; a covert priority flag risks unlawful preferential treatment and data misuse.

**Resolution:** Refuse to implement a hidden VIP flag. If priority handling is required, implement an auditable, policy-governed expedited process with documented criteria, supervisor approval, and an audit trail.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`