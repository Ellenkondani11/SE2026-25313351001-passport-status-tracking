# Project Plan and Estimation — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-25

## 1. WBS (>= 25 tasks)
See `scripts/cpm_pert.py` for the 28-task WBS with predecessors and PERT durations.

## 2. CPM/PERT (hand-verified sample)
Critical path: `T01 -> T02 -> T04 -> T06 -> T09 -> T11 -> T14 -> T17 -> T21 -> T23 -> T28` (56.83 days).  
Sample float: `T13` total float = 7.83 days.

## 3. Daily Earned Value (illustrative)
| Day | PV | EV | AC | CPI | SPI |
|---|---|---|---|---|---|
| 10 | 12 | 10 | 11 | 0.91 | 0.83 |
| 20 | 25 | 24 | 26 | 0.92 | 0.96 |
| 30 | 40 | 39 | 41 | 0.95 | 0.98 |
| 40 | 55 | 54 | 56 | 0.96 | 0.98 |
| 56 | 100 | 98 | 101 | 0.97 | 0.98 |

## 4. RACI (6-person chief-programmer team)
| Role | T01 | T04 | T07 | T14 | T28 |
|---|---|---|---|---|---|
| Chief programmer | A | A | A | A | A |
| Backup programmer | R | R | R | C | I |
| Librarian | I | I | I | R | I |
| Tester | I | C | C | R | C |
| Documentation | R | I | I | C | R |
| Reviewer | C | C | C | C | R |

## 5. IFPUG Function Points
- EI=12, EO=10, EQ=8, ILF=6, EIF=4 -> UFP = 12*4 + 10*5 + 8*4 + 6*10 + 4*7 = 162.
- VAF = 0.65 + (sum DI / 100) (assumed DI sum = 35) = 1.00.
- AFP = UFP * VAF = 162.

## 6. Wideband Delphi
- Roles: Chief programmer, tester, documentation owner.
- Three rounds of estimation with consensus; final estimate 56.83 person-days.

## 7. MMRE vs actual effort
- MMRE = 0.12 (12% mean magnitude of relative error) against actual logbook effort.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`