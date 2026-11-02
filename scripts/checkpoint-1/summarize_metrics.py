"""Validate a completed run and summarize measured repetitions without warmups."""

import argparse
import csv
import json
from pathlib import Path
from statistics import median


METRICS = ("elapsed_ms", "read_rows", "read_bytes", "cpu_time_us", "memory_usage_bytes")


def summarize(run_dir):
    run = json.loads((run_dir / "run.json").read_text())
    if run["status"] != "complete":
        raise ValueError("Cannot summarize an incomplete run")
    repeats = run["measured_runs"]
    queries = run["queries"]
    if type(repeats) is not int or repeats < 3 or type(queries) is not int or queries < 1:
        raise ValueError("Expected at least three measured repetitions per query")
    rows = [json.loads(line) for line in (run_dir / "measurements.jsonl").read_text().splitlines()]
    expected = {(q, r) for q in range(1, queries + 1) for r in range(1, repeats + 1)}
    seen = set()
    ids = set()
    for row in rows:
        if type(row["query_number"]) is not int or type(row["repeat"]) is not int:
            raise ValueError("Query numbers and repetitions must be integers")
        pair = (row["query_number"], row["repeat"])
        if pair not in expected or pair in seen or row["query_id"] in ids:
            raise ValueError("Unexpected or duplicate query/repetition or query_id")
        expected_id = f"{run['run_id']}-q{pair[0]}-measure{pair[1]}"
        if row["query_id"] != expected_id:
            raise ValueError("A measurement belongs to another run or to a warmup")
        if any(type(row.get(key)) is not int or row[key] < 0 for key in METRICS):
            raise ValueError("Each of the five metrics must be a nonnegative integer")
        if "has_cpu_events" in row and not row["has_cpu_events"]:
            raise ValueError("CPU counters are unavailable")
        if "user_cpu_time_us" in row and row["cpu_time_us"] != (
            row["user_cpu_time_us"] + row["system_cpu_time_us"]
        ):
            raise ValueError("CPU total differs from its components")
        seen.add(pair)
        ids.add(row["query_id"])
    if seen != expected:
        raise ValueError("Some measured repetitions are missing")

    summaries = []
    for query in range(1, queries + 1):
        group = [row for row in rows if row["query_number"] == query]
        result = {"query_number": query, "repeats": repeats}
        for metric in METRICS:
            values = [row[metric] for row in group]
            result.update({
                f"{metric}_median": median(values),
                f"{metric}_min": min(values),
                f"{metric}_max": max(values),
            })
        summaries.append(result)
    return summaries


def write_summary(run_dir):
    rows = summarize(run_dir)
    destination = run_dir / "summary.tsv"
    with destination.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    print(write_summary(args.run_dir))


if __name__ == "__main__":
    main()
