"""Verify the complete ClickBench hash sample and run the Docker workload."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid


def digest(path):
    if not path.exists():
        return None
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context")
    parser.add_argument("--artifacts-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    data_dir = root / ".local/data/checkpoint-1-all"
    results = root / ".local/results/checkpoint-1-all"
    artifacts = args.artifacts_dir or root / "artifacts/checkpoint-1"
    names = ("clickbench-sample.json", "clickbench-reference.json", "clickbench-check.json")
    previous = {name: digest(artifacts / name) for name in names}
    previous_report = digest(artifacts / "benchmark/run.tsv")
    docker = ["docker"]
    context_args = []
    if args.context:
        docker.extend(["--context", args.context])
        context_args = ["--context", args.context]
    compose = docker + ["compose", "-f", str(root / "compose.yaml")]

    def run(arguments, capture=False):
        return subprocess.run(arguments, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None).stdout

    print("Starting ClickHouse and preparing the sample from all 100 files", flush=True)
    run(compose + ["up", "--wait", "clickhouse"])
    run(compose + ["run", "--rm", "--build", "download"])
    run(compose + ["run", "--rm", "--build", "prepare"])
    results.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((data_dir / "sample-manifest.json").read_text())
    if len(manifest["sources"]) != 100 or manifest["modulus"] != 100 or manifest["remainder"] != 0:
        raise ValueError("The dataset must contain the hash sample from all 100 files")

    def query(sql):
        return run(docker + ["exec", "nis-clickhouse", "clickhouse-client", "--query", sql],
                   capture=True).strip()

    present = query("SELECT count() FROM system.tables WHERE database = 'nis_smoke' AND name = 'hits'")
    if present == "1" and int(query("SELECT count() FROM nis_smoke.hits")) != manifest["rows"]:
        backup = "hits_backup_" + uuid.uuid4().hex
        query(f"RENAME TABLE nis_smoke.hits TO nis_smoke.{backup}")
    print("Checking the full sample against the independent Parquet reference", flush=True)
    run(["python3", str(root / "scripts/checkpoint-1/verify.py"), *context_args,
         "--data-dir", str(data_dir), "--artifacts-dir", str(results)])

    print("Running all 43 ClickBench queries", flush=True)
    benchmark = root / ".local/results/clickbench"
    previous_runs = set(benchmark.glob("nis-clickbench-*"))
    run(compose + ["run", "--rm", "--build", "benchmark"])
    run_dirs = list(set(benchmark.glob("nis-clickbench-*")) - previous_runs)
    if len(run_dirs) != 1:
        raise ValueError("Expected exactly one full-dataset benchmark run")
    run_dir = run_dirs[0]
    with (run_dir / "run.tsv").open() as report:
        runs = list(csv.DictReader(report, delimiter="\t"))
    if (len(runs) != 43 or {int(row["query"]) for row in runs} != set(range(1, 44))
            or any(row["status"] != "OK" for row in runs)):
        raise ValueError("The benchmark did not complete all 43 queries")
    for row in runs:
        answer = json.loads(row["answer"])
        if not isinstance(answer, list) or any(not isinstance(values, list) for values in answer):
            raise ValueError(f"Invalid answer for query {row['query']}")

    artifacts.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = artifacts / name
        if digest(target) == previous[name]:
            shutil.copy2(results / name, target)
        else:
            print(f"Preserving edits to {target}; new result: {results / name}", flush=True)
    destination = artifacts / "benchmark/run.tsv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if digest(destination) == previous_report:
        shutil.copy2(run_dir / "run.tsv", destination)
    else:
        print(f"Preserving edits to {destination}; new report: {run_dir / 'run.tsv'}", flush=True)
    print(f"Full-dataset checks passed; results: {results}", flush=True)


if __name__ == "__main__":
    main()
