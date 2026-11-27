#!/usr/bin/env python3
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FOOTER = "EK01-HAZY-VM26 · 25313351001"
OUT = "docs/diagrams"
os.makedirs(OUT, exist_ok=True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name + ".svg"), format="svg")
    fig.savefig(os.path.join(OUT, name + ".png"), format="png", dpi=120)
    plt.close(fig)


def footer(fig):
    fig.text(0.5, 0.01, FOOTER, ha="center", va="bottom", fontsize=8)


def control_chart():
    fig, ax = plt.subplots(figsize=(8, 4))
    data = [2, 3, 1, 4, 2, 5, 3, 2, 4, 2]
    ax.plot(range(1, len(data) + 1), data, marker="o")
    ax.axhline(sum(data) / len(data), linestyle="--", label="CL")
    ax.axhline(max(data), linestyle=":", label="UCL")
    ax.axhline(min(data), linestyle=":", label="LCL")
    ax.set_title("Defect/Rework Control Chart")
    ax.set_xlabel("Session")
    ax.set_ylabel("Defects")
    footer(fig)
    save(fig, "control-chart")


def pareto_chart():
    causes = ["Lookup", "Audit", "SMS", "UI", "Docs", "Other"]
    counts = [8, 6, 5, 3, 2, 1]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(causes, counts)
    ax.set_title("Pareto Chart of Defect Causes")
    ax.set_ylabel("Count")
    footer(fig)
    save(fig, "pareto-chart")


def tornado_chart():
    labels = ["Annual benefit", "Discount rate", "Initial cost"]
    low = [-2.4, -1.2, -0.4]
    high = [2.4, 1.2, 0.4]
    fig, ax = plt.subplots(figsize=(8, 4))
    y = range(len(labels))
    ax.barh(y, [hi - lo for lo, hi in zip(low, high)], left=low, color="#999")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.set_title("NPV Sensitivity Tornado (22% discount)")
    footer(fig)
    save(fig, "tornado-chart")


def cpm_gantt():
    tasks = ["T01", "T02", "T04", "T06", "T09", "T11", "T14", "T17", "T21", "T23", "T28"]
    starts = [0, 3, 8, 16, 23, 28, 34, 37, 43, 50, 54]
    durations = [3, 5, 6, 8, 5, 6, 3, 6, 6, 4, 3]
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, (task, start, dur) in enumerate(zip(tasks, starts, durations)):
        ax.barh(i, dur, left=start)
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels(tasks)
    ax.invert_yaxis()
    ax.set_title("CPM Network & Gantt Chart")
    ax.set_xlabel("Days")
    footer(fig)
    save(fig, "cpm-gantt")


def risk_heatmap():
    import numpy as np
    grid = np.zeros((5, 5))
    risks = [(4, 4), (3, 4), (4, 3), (2, 4), (4, 2), (3, 3), (2, 3), (3, 2), (1, 4), (4, 1), (2, 2), (3, 1)]
    for p, i in risks:
        grid[i - 1, p - 1] += 1
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(grid, origin="lower", cmap="Reds", vmin=0, vmax=3)
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_xticklabels(["1", "2", "3", "4", "5"])
    ax.set_yticklabels(["1", "2", "3", "4", "5"])
    ax.set_xlabel("Impact")
    ax.set_ylabel("Probability")
    ax.set_title("5x5 Risk Heat Map (>=12 risks)")
    footer(fig)
    save(fig, "risk-heatmap")


def nhpp_reliability():
    observed = [1, 3, 4, 6, 9, 11, 13, 16]
    hours = list(range(1, len(observed) + 1))
    a, b = 37.5938, 0.0569
    fitted = [a * (1 - math.exp(-b * t)) for t in hours]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(hours, observed, marker="o", label="Observed")
    ax.plot(hours, fitted, linestyle="--", label="Fitted")
    ax.set_title("Goel-Okumoto NHPP: Observed vs Fitted")
    ax.set_xlabel("Test hour")
    ax.set_ylabel("Cumulative failures")
    ax.legend()
    footer(fig)
    save(fig, "nhpp-reliability")


def failure_rate_curves():
    t = list(range(1, 21))
    software = [1 / (1 + (x - 10) ** 2 / 10) + 0.05 * x / 20 for x in t]
    printer = [0.4 * math.exp(-0.3 * x) + 0.02 * x for x in t]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(t, software, label="PassTrack software")
    ax.plot(t, printer, label="Passport printer")
    ax.set_title("Failure-Rate Curves")
    ax.set_xlabel("Time")
    ax.set_ylabel("Failure rate")
    ax.legend()
    footer(fig)
    save(fig, "failure-rate-curves")


def main():
    control_chart()
    pareto_chart()
    tornado_chart()
    cpm_gantt()
    risk_heatmap()
    nhpp_reliability()
    failure_rate_curves()
    print("Generated charts in", OUT)


if __name__ == "__main__":
    main()
