#!/usr/bin/env python3
import argparse
import concurrent.futures
import http.cookiejar
import time
import urllib.error
import urllib.parse
import urllib.request


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct / 100.0
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=500)
    parser.add_argument("--national-id", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--tracking-code", required=True)
    args = parser.parse_args()

    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    with op.open(args.base_url + "/", timeout=30) as resp:
        resp.read()
    token = ""
    for cookie in cj:
        if cookie.name == "csrftoken":
            token = cookie.value
    data = urllib.parse.urlencode({
        "national_id": args.national_id,
        "phone_or_code": args.phone,
        "csrfmiddlewaretoken": token,
    }).encode()
    req = urllib.request.Request(
        args.base_url + "/", data=data,
        headers={"X-CSRFToken": token, "Referer": args.base_url + "/"},
    )
    for cookie in cj:
        req.add_unredirected_header("Cookie", f"{cookie.name}={cookie.value}")
    with op.open(req, timeout=30) as resp:
        resp.read()
    session_cookies = "; ".join(f"{c.name}={c.value}" for c in cj)

    def one_lookup(i):
        jar = http.cookiejar.CookieJar()
        op2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        try:
            with op2.open(args.base_url + "/", timeout=30) as resp:
                resp.read()
        except Exception:  # noqa: BLE001
            return 0, 0.0, "other"
        token2 = ""
        for cookie in jar:
            if cookie.name == "csrftoken":
                token2 = cookie.value
        data2 = urllib.parse.urlencode({
            "national_id": args.national_id,
            "phone_or_code": "0000000000",
            "csrfmiddlewaretoken": token2,
        }).encode()
        req2 = urllib.request.Request(
            args.base_url + "/", data=data2,
            headers={"X-CSRFToken": token2, "Referer": args.base_url + "/"},
        )
        for cookie in jar:
            req2.add_unredirected_header("Cookie", f"{cookie.name}={cookie.value}")
        t = time.perf_counter()
        try:
            with op2.open(req2, timeout=30) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            status = 0
            body = ""
        elapsed = (time.perf_counter() - t) * 1000.0
        outcome = "success" if args.tracking_code in body else (
            "rate_limited" if "could not match" in body.lower() else "other"
        )
        return status, elapsed, outcome

    def one_status(i):
        req = urllib.request.Request(
            args.base_url + f"/status/?code={args.tracking_code}",
            headers={"Cookie": session_cookies},
        )
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            status = 0
            body = ""
        elapsed = (time.perf_counter() - t) * 1000.0
        outcome = "success" if status == 200 and "Under review" in body else "other"
        return status, elapsed, outcome

    for phase_name, worker in (("lookup", one_lookup), ("status", one_status)):
        latencies = []
        outcomes = {}
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = [executor.submit(worker, i) for i in range(args.concurrency)]
            for future in concurrent.futures.as_completed(futures):
                status, elapsed, outcome = future.result()
                latencies.append(elapsed)
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
        total_time = time.perf_counter() - started
        p50 = percentile(latencies, 50)
        p95 = percentile(latencies, 95)
        p99 = percentile(latencies, 99)
        print(f"phase={phase_name}")
        print(f"total_requests={len(latencies)}")
        print(f"concurrency={args.concurrency}")
        print(f"total_time_s={total_time:.3f}")
        print(f"throughput_rps={len(latencies)/total_time:.2f}")
        for key, value in outcomes.items():
            print(f"{key}={value}")
        print(f"p50_ms={p50:.2f}")
        print(f"p95_ms={p95:.2f}")
        print(f"p99_ms={p99:.2f}")
        print(f"gate_p95_le_500ms={'PASS' if p95 <= 500 else 'FAIL'}")
        print("---")


if __name__ == "__main__":
    main()
