# UAT Sign-off — PassTrack (PASTNS)
- **Token:** `EK01-HAZY-VM26` | **Student:** `25313351001`

## UAT test cases (Immigration Counter Clerk role)
| TC ID | Scenario | Steps | Expected Result | Pass/Fail | Evidence |
|-------|----------|-------|-----------------|-----------|----------|
| UAT-01 | Register new application | Enter national ID, name, phone, type; submit | Application registered, tracking code shown, SMS queued |  |  |
| UAT-02 | Advance stage | Open application, click "Advance to Under review" | Stage changes, SMS notification dispatched |  |  |
| UAT-03 | Hold / resume | Click "Hold", then "Resume" | Previous stage restored, audit log entry created |  |  |
| UAT-04 | Reject application | Supervisor rejects with reason | Status = rejected, terminal, no further advance |  |  |
| UAT-05 | Correct contact details | Update phone, verify ID check | Audit log records masked numbers |  |  |
| UAT-06 | Public lookup (dual factor) | Enter national ID + tracking code | Status shown, phone masked |  |  |
| UAT-07 | USSD *384*123# | Dial code, enter tracking code | Status returned within 160 chars |  |  |
| UAT-08 | Bulk update CSV export | Select rows, export CSV | Formula-safe CSV downloaded |  |  |

## Sign-off block
- Counter Clerk (student playing role): Name ____________________ Reg No. ____________________ Signature ____________________ Date __________
- Supervisor (witness): Name ____________________ Reg No. ____________________ Signature ____________________ Date __________

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`
