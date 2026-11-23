# Load Test Report — PassTrack (PASTNS)

- **Token:** `EK01-HAZY-VM26`
- **Student:** Ellen Kondani (`25313351001`)
- **Version:** `v0.95`
- **Date:** 2026-11-23
- **Script:** `scripts/load_test.py`
- **Environment:** local Django `runserver` on `127.0.0.1:8000`, SQLite, 500 concurrent client threads.

## 1. Phase 1 — POST `/` (lookup)
- Total requests: 500
- Concurrency: 500
- Total time: 31.646 s
- Throughput: 15.80 rps
- Rate-limited/failed lookups: 427
- Other (connection/timeout): 73
- p50: 6250.08 ms
- p95: 18091.81 ms
- p99: 19894.64 ms
- Gate (p95 <= 500 ms): **FAIL**

## 2. Phase 2 — GET `/status/`
- Total requests: 500
- Concurrency: 500
- Total time: 29.330 s
- Throughput: 17.05 rps
- Successful (HTTP 200 with expected stage): 500
- p50: 14438.48 ms
- p95: 19271.42 ms
- p99: 27819.85 ms
- Gate (p95 <= 500 ms): **FAIL**

## 3. Conclusion
The single-threaded development server with SQLite does not meet the 500 ms p95 gate under 500 concurrent users. Production deployment requires a multi-worker WSGI server and PostgreSQL.

Footer: Token `EK01-HAZY-VM26` | Student `25313351001`