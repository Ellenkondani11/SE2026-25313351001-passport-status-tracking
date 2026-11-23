# KAOS Goal Model — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Baseline:** `v0.8` (Requirements Baseline)
- **Date:** 2026-11-23
- **Source (editable Mermaid):** `docs/diagrams/kaos-goal-model.mmd`

## 1. Purpose
This document captures the KAOS (Keep All Objectives Satisfied) goal-oriented requirements model for PassTrack. It decomposes the top-level objective into sub-goals, identifies obstacles (threats/gaps) from the Signature Challenge analysis, and maps mitigating requirements (FRs) and responsible agents.

## 2. Top-Level Goal
**G0 — Provide consistent, private, auditable passport status tracking across Web, SMS, and USSD.**

## 3. Sub-Goals
| ID | Goal | Related FRs |
|---|---|---|
| G1 | Consistency: all channels show identical stage text within 60 seconds | FR-17, FR-08, FR-25 |
| G2 | Reliable notifications: exponential backoff retry, deduplication, delivery reports | FR-18, FR-19, FR-26 |
| G3 | Private lookup: two-factor (code/DOB or OTP), rate-limited, session TTL | FR-20, FR-21 |
| G4 | Auditability: tamper-evident hash-chained log with actor/time/reason | FR-22, FR-28 |
| G5 | Performance & availability NFRs (p95 <= 500 ms, 99.5% uptime) | NFR-01..NFR-08 |

## 4. Obstacles (from Signature Challenge gap analysis)
| ID | Obstacle | Threatens | Mitigation |
|---|---|---|---|
| O1 | `Stage.applicant_text_*` vs `SmsTemplate.body_*` divergence | G1 | FR-17 / FR-25 |
| O2 | `resume` omits SMS notification | G1 | FR-08 / FR-17 |
| O3 | No exponential backoff, idempotency key, or callback token | G2 | FR-18 / FR-19 |
| O4 | Missing `date_of_birth`, OTP flow, IP-wide limit, session TTL | G3 | FR-20 / FR-21 |
| O5 | ORM guard only; no cryptographic hash chain | G4 | FR-22 |

## 5. Agents
- Applicant — consumes G3 (private lookup).
- Officer (Counter Clerk) — drives G1 (stage updates).
- Supervisor (Approving Officer) — authorises skips/rejects, supports G4.
- Admin (ICT Manager) — manages configuration, supports G5.
- SMS Gateway (Africa's Talking) — participates in G2.
- System — orchestrates all goals.

## 6. Diagram
See `docs/diagrams/kaos-goal-model.mmd` (render with any Mermaid-compatible tool).

---

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`