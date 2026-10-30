"""Verify the complete ClickBench hash sample and run the Docker workload."""

import argparse
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
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    data_dir = root / ".local/data/checkpoint-1-all"
    results = root / ".local/results/checkpoint-1-all"
    artifacts = root / "artifacts/checkpoint-1"
    names = ("clickbench-sample.json", "clickbench-reference.json", "clickbench-check.json")
    previous = {name: digest(artifacts / name) for name in names}
    docker = ["docker"]
    context_args = []
    if args.context:
        docker.extend(["--context", args.context])
        context_args = ["--context", args.context]

    def run(arguments, capture=False):
        return subprocess.run(arguments, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None).stdout

    print("Waiting for the sample from all 100 source files", flush=True)
    exit_code = run(docker + ["wait", "nis-clickbench-prepare-all"], capture=True).strip()
    if exit_code != "0":
        raise RuntimeError(f"Dataset preparation failed with exit code {exit_code}")
    data_dir.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    for name in ("hits_small.parquet", "sample-manifest.json", "reference.json"):
        run(docker + ["cp", f"nis-clickbench-prepare-all:/data/{name}", str(data_dir / name)])
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
    run(docker + ["run", "--name", "nis-clickbench-full-check", "--label", "nis.project=nis-project",
                  "--network", "container:nis-clickhouse", "--cpus", "1", "--memory", "1g",
                  "--mount", "type=volume,source=nis-clickbench-full-runs,target=/results",
                  "nis-clickbench-benchmark"])
    benchmark = results / "benchmark"
    benchmark.mkdir(exist_ok=True)
    run(docker + ["cp", "nis-clickbench-full-check:/results/.", str(benchmark)])
    runs = list(benchmark.glob("nis-clickbench-*"))
    if len(runs) != 1:
        raise ValueError("Expected exactly one full-dataset benchmark run")
    run_dir = runs[0]
    metadata = json.loads((run_dir / "run.json").read_text())
    measurements = [json.loads(line) for line in (run_dir / "measurements.jsonl").read_text().splitlines()]
    expected = {(query, repeat) for query in range(1, 44) for repeat in range(1, 4)}
    if (metadata["status"] != "complete" or metadata["input_rows"] != manifest["rows"]
            or len(measurements) != 129
            or {(row["query_number"], row["repeat"]) for row in measurements} != expected):
        raise ValueError("The benchmark results are incomplete or use a different dataset")

    for name in names:
        target = artifacts / name
        if digest(target) == previous[name]:
            shutil.copy2(results / name, target)
        else:
            print(f"Preserving edits to {target}; new result: {results / name}", flush=True)
    destination = artifacts / "benchmark/full"
    shutil.copytree(run_dir, destination)
    print(f"Full-dataset checks passed; results: {results}", flush=True)


if __name__ == "__main__":
    main()
