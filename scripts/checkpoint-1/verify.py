"""Load the frozen sample and compare ClickHouse with the Parquet reference."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import uuid


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
    commands = []

    def run(arguments, sql_input=None):
        command = docker + arguments
        commands.append(command)
        process = subprocess.run(command, input=sql_input, text=True, capture_output=True)
        if process.returncode:
            raise RuntimeError(f"Command failed: {command}\n{process.stderr}")
        return process.stdout

    def query(sql, query_id=None):
        command = [
            "exec", "-i", args.container, "clickhouse-client", "--format", "JSONEachRow",
            "--param_counter_id", str(reference["counter_id"]), "--query", sql,
        ]
        if query_id:
            command.extend(["--query_id", query_id])
        return [json.loads(line) for line in run(command).splitlines() if line]

    disk_before = query("SELECT name, free_space, total_space FROM system.disks")
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

    query_ids = []
    if int(query("SELECT count() AS rows FROM nis_smoke.hits")[0]["rows"]) == 0:
        run(["exec", args.container, "mkdir", "-p", "/var/lib/clickhouse/user_files/nis-checkpoint-1"])
        run(["cp", str(sample), f"{args.container}:/var/lib/clickhouse/user_files/nis-checkpoint-1/hits_small.parquet"])
        load_id = "nis-checkpoint-1-load-" + uuid.uuid4().hex
        query_ids.append(load_id)
        query(
            "INSERT INTO nis_smoke.hits SELECT * "
            "FROM file('nis-checkpoint-1/hits_small.parquet', Parquet) "
            "SETTINGS max_threads = 2, max_insert_threads = 2, max_memory_usage = 3221225472",
            query_id=load_id,
        )

    stats = query(
        "SELECT count() AS rows, uniqExact(CounterID) AS distinct_counters, "
        "uniqExact(UserID) AS distinct_users, "
        f"countIf(xxHash64(toString(toUInt64(WatchID))) % {manifest['modulus']} "
        f"!= {manifest['remainder']}) AS outside_sample, "
        "toString(min(EventTime), 'UTC') AS first_event_utc, "
        "toString(max(EventTime), 'UTC') AS last_event_utc FROM nis_smoke.hits "
        "SETTINGS max_threads = 2, max_memory_usage = 3221225472"
    )[0]
    probe_sql = (root / "sql/checkpoint-1-clickbench-probe.sql").read_text().strip().rstrip(";")
    probe_id = "nis-checkpoint-1-probe-" + uuid.uuid4().hex
    query_ids.append(probe_id)
    actual = query(probe_sql, query_id=probe_id)[0]
    actual = {key: int(value) for key, value in actual.items()}
    checks = {
        "row_count_matches_parquet": int(stats["rows"]) == reference["rows"],
        "counters_match_parquet": int(stats["distinct_counters"]) == reference["distinct_counters"],
        "users_match_parquet": int(stats["distinct_users"]) == reference["distinct_users"],
        "all_rows_satisfy_hash_predicate": int(stats["outside_sample"]) == 0,
        "probe_matches_python_reference": actual == reference["expected"],
    }
    explain_sql = probe_sql.replace(
        "SETTINGS max_threads = 2, use_query_cache = 0",
        "SETTINGS max_threads = 2, use_query_cache = 0, "
        "use_query_condition_cache = 0, use_skip_indexes_on_data_read = 0",
    )
    explain = query("EXPLAIN indexes = 1 " + explain_sql)
    parts = query(
        "SELECT name, rows, marks, bytes_on_disk, data_uncompressed_bytes "
        "FROM system.parts WHERE database = 'nis_smoke' AND table = 'hits' "
        "AND active ORDER BY name"
    )
    query("SYSTEM FLUSH LOGS")
    quoted_ids = ", ".join("'" + value + "'" for value in query_ids)
    profiles = query(
        "SELECT query_id, query_duration_ms, read_rows, read_bytes, written_rows, memory_usage "
        f"FROM system.query_log WHERE type = 'QueryFinish' AND (query_id IN ({quoted_ids}) "
        f"OR (query_id LIKE 'nis-checkpoint-1-load-%' AND written_rows = {manifest['rows']})) "
        "ORDER BY event_time_microseconds"
    )
    result = {
        "server_version": query("SELECT version() AS version")[0]["version"],
        "resources": {"architecture": architecture, "cpus": int(cpus), "memory_bytes": int(memory)},
        "stats": stats,
        "counter_id": reference["counter_id"],
        "expected": reference["expected"],
        "actual": actual,
        "checks": checks,
        "passed": all(checks.values()),
        "parts": parts,
        "explain": explain,
        "query_profiles": profiles,
        "disk_before": disk_before,
        "disk_after": query("SELECT name, free_space, total_space FROM system.disks"),
        "ddl": query("SHOW CREATE TABLE nis_smoke.hits"),
        "granularity": query(
            "SELECT name, value FROM system.merge_tree_settings "
            "WHERE name IN ('index_granularity', 'index_granularity_bytes')"
        ),
        "commands": commands,
    }
    (artifacts / "clickbench-sample.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (artifacts / "clickbench-reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    (artifacts / "clickbench-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "stats": stats, "expected": reference["expected"], "actual": actual}), flush=True)
    if not result["passed"]:
        raise SystemExit("ClickHouse result differs from the independent Parquet reference")


if __name__ == "__main__":
    main()
