#!/usr/bin/env python3
import math

# Cumulative defect/failure observations over 8 test hours
# (illustrative values derived from local testing sessions).
OBSERVED = [1, 3, 4, 6, 9, 11, 13, 16]
HOURS = list(range(1, len(OBSERVED) + 1))


def model_m(t, a, b):
    return a * (1.0 - math.exp(-b * t))


def model_lambda(t, a, b):
    return a * b * math.exp(-b * t)


def residuals(a, b):
    return [model_m(t, a, b) - y for t, y in zip(HOURS, OBSERVED)]


def optimize():
    # Grid search + local refinement (pure Python, no dependencies).
    best = None
    for ai in range(1, 400):
        for bi in range(1, 200):
            a = ai / 10.0
            b = bi / 100.0
            sse = sum(r * r for r in residuals(a, b))
            if best is None or sse < best[0]:
                best = (sse, a, b)
    sse, a, b = best
    # Local refinement
    step_a = 0.05
    step_b = 0.005
    for _ in range(200):
        improved = False
        for da in (-step_a, 0.0, step_a):
            for db in (-step_b, 0.0, step_b):
                na, nb = a + da, b + db
                if na <= 0 or nb <= 0:
                    continue
                nsse = sum(r * r for r in residuals(na, nb))
                if nsse < sse:
                    a, b, sse = na, nb, nsse
                    improved = True
        if not improved:
            step_a *= 0.5
            step_b *= 0.5
    return a, b


def main():
    a, b = optimize()
    print("Goel-Okumoto NHPP fit")
    print(f"observed_hours={HOURS}")
    print(f"observed_cumulative={OBSERVED}")
    print(f"a={a:.4f}")
    print(f"b={b:.4f}")
    print(f"m(8)={model_m(8, a, b):.4f}")
    print(f"m(12)={model_m(12, a, b):.4f}")
    print(f"lambda(8)={model_lambda(8, a, b):.4f}")


if __name__ == "__main__":
    main()
