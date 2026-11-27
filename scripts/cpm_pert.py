#!/usr/bin/env python3
from collections import defaultdict, deque

TASKS = [
    ("T01", "Requirements baseline", [], 2, 3, 5),
    ("T02", "Characterisation tests", ["T01"], 3, 5, 8),
    ("T03", "As-built baseline docs", ["T01"], 2, 3, 4),
    ("T04", "Signature Challenge #3 private lookup", ["T02"], 4, 6, 10),
    ("T05", "Signature Challenge #4 audit chain", ["T02"], 4, 6, 9),
    ("T06", "Signature Challenge #1 consistency", ["T04", "T05"], 5, 8, 12),
    ("T07", "Signature Challenge #2 notifications", ["T04", "T05"], 5, 7, 11),
    ("T08", "Channel strategies", ["T06"], 3, 4, 6),
    ("T09", "Observer event bus", ["T06"], 3, 5, 7),
    ("T10", "Template dispatcher", ["T07"], 3, 4, 6),
    ("T11", "Refactor application_detail", ["T08", "T09"], 4, 6, 9),
    ("T12", "Refactor ussd_endpoint", ["T08"], 3, 5, 8),
    ("T13", "Refactor API stage update", ["T07"], 3, 4, 6),
    ("T14", "verify_slices command", ["T11", "T12", "T13"], 2, 3, 5),
    ("T15", "verify_audit command", ["T05"], 2, 3, 4),
    ("T16", "Docs design package", ["T03"], 4, 6, 9),
    ("T17", "Docs quality package", ["T14", "T15"], 4, 6, 9),
    ("T18", "Load test script", ["T14"], 3, 4, 6),
    ("T19", "Load test run", ["T18"], 2, 3, 5),
    ("T20", "Maintenance docs", ["T17"], 3, 4, 6),
    ("T21", "Engineering analysis docs", ["T17"], 4, 6, 9),
    ("T22", "User docs", ["T16"], 3, 4, 6),
    ("T23", "Charts generation", ["T19", "T21"], 3, 4, 6),
    ("T24", "SBOM and checksums", ["T17"], 2, 3, 4),
    ("T25", "CPM/Pert scripts", ["T19"], 3, 4, 6),
    ("T26", "NHPP reliability script", ["T19"], 3, 5, 7),
    ("T27", "Africa's Talking readiness", ["T14"], 3, 4, 6),
    ("T28", "Final CI verification", ["T20", "T21", "T22", "T23", "T24", "T25", "T26", "T27"], 2, 3, 5),
]


def main():
    task_map = {t[0]: t for t in TASKS}
    expected = {t[0]: (t[3] + 4 * t[4] + t[5]) / 6.0 for t in TASKS}

    # Topological order
    indegree = {t[0]: len(t[2]) for t in TASKS}
    successors = defaultdict(list)
    for t in TASKS:
        for pred in t[2]:
            successors[pred].append(t[0])
    queue = deque([tid for tid in indegree if indegree[tid] == 0])
    order = []
    while queue:
        tid = queue.popleft()
        order.append(tid)
        for succ in successors[tid]:
            indegree[succ] -= 1
            if indegree[succ] == 0:
                queue.append(succ)

    es = {}
    ef = {}
    for tid in order:
        preds = task_map[tid][2]
        es[tid] = max((ef[p] for p in preds), default=0.0)
        ef[tid] = es[tid] + expected[tid]

    project_duration = max(ef.values())
    # backward pass
    lf = {}
    ls = {}
    for tid in reversed(order):
        succs = successors[tid]
        lf[tid] = min((ls[s] for s in succs), default=project_duration)
        ls[tid] = lf[tid] - expected[tid]

    total_float = {tid: ls[tid] - es[tid] for tid in task_map}
    critical = [tid for tid in task_map if abs(total_float[tid]) < 1e-9]

    print("CPM/PERT Analysis - PassTrack (PASTNS)")
    print(f"Project expected duration: {project_duration:.2f} days")
    print()
    header = f"{'Task':<6}{'Name':<34}{'Pred':<24}{'Exp':>6}{'ES':>7}{'EF':>7}{'LS':>7}{'LF':>7}{'Float':>7}"
    print(header)
    print("-" * len(header))
    for tid in order:
        name = task_map[tid][1][:32]
        preds = ",".join(task_map[tid][2]) or "-"
        print(f"{tid:<6}{name:<34}{preds:<24}{expected[tid]:>6.2f}{es[tid]:>7.2f}{ef[tid]:>7.2f}{ls[tid]:>7.2f}{lf[tid]:>7.2f}{total_float[tid]:>7.2f}")  # noqa: E501
    print()
    print("Critical path:", " -> ".join(critical))
    print("Critical path length:", sum(expected[t] for t in critical))


if __name__ == "__main__":
    main()
