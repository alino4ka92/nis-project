"""Load the frozen sample and compare ClickHouse with the Parquet reference."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context")
    parser.add_argument("--container", default="nis-clickhouse")
    parser.add_argument("--data-dir", type=Path, default=Path(".local/data/checkpoint-1-all"))
    parser.add_argument("--artifacts-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    artifacts = args.artifacts_dir or root / "artifacts/checkpoint-1"
    artifacts.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.data_dir / "sample-manifest.json").read_text())
    reference = json.loads((args.data_dir / "reference.json").read_text())
    sample = args.data_dir / "hits_small.parquet"
    with sample.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != manifest["sample_sha256"] or manifest["rows"] != reference["rows"]:
        raise ValueError("sample, manifest and reference do not match")

    docker = ["docker"]
    if args.context:
        docker.extend(["--context", args.context])

    def run(arguments, sql_input=None):
        command = docker + arguments
        process = subprocess.run(command, input=sql_input, text=True, capture_output=True)
        if process.returncode:
            raise RuntimeError(f"Command failed: {command}\n{process.stderr}")
        return process.stdout

    def query(sql):
        command = [
            "exec", "-i", args.container, "clickhouse-client", "--format", "JSONEachRow",
            "--param_counter_id", str(reference["counter_id"]), "--query", sql,
        ]
        return [json.loads(line) for line in run(command).splitlines() if line]

    architecture, cpus, memory = run([
        "info", "--format", "{{.Architecture}} {{.NCPU}} {{.MemTotal}}",
    ]).split()
    exists = query(
        "SELECT count() AS present FROM system.tables "
        "WHERE database = 'nis_smoke' AND name = 'hits'"
    )[0]
    if int(exists["present"]) == 0:
        query("CREATE DATABASE IF NOT EXISTS nis_smoke")
        ddl = (root / "third_party/clickbench/clickhouse/create.sql").read_text()
        run([
            "exec", "-i", args.container, "clickhouse-client", "--database", "nis_smoke",
            "--multiquery",
        ], sql_input=ddl)

    if int(query("SELECT count() AS rows FROM nis_smoke.hits")[0]["rows"]) == 0:
        run(["exec", args.container, "mkdir", "-p", "/var/lib/clickhouse/user_files/nis-checkpoint-1"])
        run(["cp", str(sample), f"{args.container}:/var/lib/clickhouse/user_files/nis-checkpoint-1/hits_small.parquet"])
        query(
            "INSERT INTO nis_smoke.hits SELECT * "
            "FROM file('nis-checkpoint-1/hits_small.parquet', Parquet) "
            "SETTINGS max_threads = 2, max_insert_threads = 2, max_memory_usage = 3221225472",
        )

    stats = query(
        "SELECT count() AS rows, uniqExact(CounterID) AS distinct_counters, "
        "uniqExact(UserID) AS distinct_users, "
        f"countIf(xxHash64(toString(toUInt64(WatchID))) % {manifest['modulus']} "
        f"!= {manifest['remainder']}) AS outside_sample FROM nis_smoke.hits "
        "SETTINGS max_threads = 2, max_memory_usage = 3221225472"
    )[0]
    probe_sql = (root / "sql/checkpoint-1-clickbench-probe.sql").read_text().strip().rstrip(";")
    actual = query(probe_sql)[0]
    actual = {key: int(value) for key, value in actual.items()}
    checks = {
        "row_count_matches_parquet": int(stats["rows"]) == reference["rows"],
        "counters_match_parquet": int(stats["distinct_counters"]) == reference["distinct_counters"],
        "users_match_parquet": int(stats["distinct_users"]) == reference["distinct_users"],
        "all_rows_satisfy_hash_predicate": int(stats["outside_sample"]) == 0,
        "probe_matches_python_reference": actual == reference["expected"],
    }
    table_bytes = query(
        "SELECT sum(bytes_on_disk) AS bytes "
        "FROM system.parts WHERE database = 'nis_smoke' AND table = 'hits' "
        "AND active"
    )[0]["bytes"]
    free_bytes = query("SELECT min(free_space) AS bytes FROM system.disks")[0]["bytes"]
    result = {
        "server_version": query("SELECT version() AS version")[0]["version"],
        "resources": {
            "architecture": architecture, "cpus": int(cpus), "memory_bytes": int(memory),
            "table_bytes": int(table_bytes), "free_disk_bytes": int(free_bytes),
            "preparation_peak_rss_bytes": manifest["preparation_peak_rss_bytes"],
        },
        "stats": stats,
        "counter_id": reference["counter_id"],
        "expected": reference["expected"],
        "actual": actual,
        "checks": checks,
        "passed": all(checks.values()),
    }
    sample_info = {key: manifest[key] for key in (
        "clickbench_revision", "sql_predicate", "source_rows", "rows", "columns",
        "sample_file", "sample_bytes", "sample_sha256",
    )}
    sample_info["source_count"] = len(manifest["sources"])
    sample_info["source_url_template"] = (
        manifest["sources"][0]["url"].rsplit("/", 1)[0] + "/hits_{part}.parquet"
    )
    expected = {key: reference[key] for key in (
        "method", "rows", "distinct_counters", "distinct_users", "counter_id", "query", "expected",
    )}
    (artifacts / "clickbench-sample.json").write_text(json.dumps(sample_info, indent=2) + "\n")
    (artifacts / "clickbench-reference.json").write_text(json.dumps(expected, indent=2) + "\n")
    (artifacts / "clickbench-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "stats": stats, "expected": reference["expected"], "actual": actual}), flush=True)
    if not result["passed"]:
        raise SystemExit("ClickHouse result differs from the independent Parquet reference")


if __name__ == "__main__":
    main()
