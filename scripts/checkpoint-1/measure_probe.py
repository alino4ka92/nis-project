"""Collect all five required metrics on participant 1's verified ClickBench query."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

from summarize_metrics import write_summary


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context")
    parser.add_argument("--container", default="nis-clickhouse")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.warmups < 1 or args.repeats < 3:
        parser.error("Use at least one warmup and three measured repetitions")
    root = Path(__file__).resolve().parents[2]
    sources = root / "artifacts/checkpoint-1"
    reference = json.loads((sources / "clickbench-reference.json").read_text())
    manifest = json.loads((sources / "clickbench-sample.json").read_text())
    counter_id = int(reference["counter_id"])
    probe = (root / "sql/checkpoint-1-clickbench-probe.sql").read_text().strip().rstrip(";")
    probe = probe.replace("{counter_id:UInt32}", str(counter_id))
    metrics_sql = (root / "sql/checkpoint-1-probe-metrics.sql").read_text()
    run_id = "nis-kt1-metrics-" + uuid.uuid4().hex
    output = args.output_dir or root / ".local/results/checkpoint-1-metrics" / run_id
    if output.exists() and any(output.iterdir()):
        parser.error(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    docker = ["docker"] + (["--context", args.context] if args.context else [])
    settings = {
        "max_threads": 2, "max_memory_usage": 3221225472,
        "use_query_cache": 0, "use_query_condition_cache": 0,
        "use_skip_indexes_on_data_read": 0,
        "log_queries": 1, "log_profile_events": 1,
        "log_queries_probability": 1, "log_query_settings": 1,
    }
    client = docker + ["exec", "-i", args.container, "clickhouse-client",
                       "--output_format_json_quote_64bit_integers", "0"]
    for key, value in settings.items():
        client.extend(["--" + key, str(value)])

    def query(sql, query_id=None, parameters=None, raw=False):
        command = client + ["--query", sql, "--format", "TSVRaw" if raw else "JSONEachRow"]
        if query_id:
            command.extend(["--query_id", query_id])
        for key, value in (parameters or {}).items():
            command.extend(["--param_" + key, str(value)])
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return result.stdout if raw else [json.loads(line) for line in result.stdout.splitlines()]

    run = {
        "run_id": run_id, "status": "running", "queries": 1,
        "warmup_runs": args.warmups, "measured_runs": args.repeats,
        "table": "nis_smoke.hits", "query_sha256": hashlib.sha256(probe.encode()).hexdigest(),
        "sample_sha256": manifest["sample_sha256"],
        "clickbench_revision": manifest["clickbench_revision"],
        "input_rows": manifest["rows"], "settings": settings,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": ["python3", "scripts/checkpoint-1/measure_probe.py", *sys.argv[1:]],
        "host_platform": platform.platform(),
    }
    write_json(output / "run.json", run)
    try:
        run["server_version"] = query("SELECT version() AS version")[0]["version"]
        run["docker_context"] = args.context or subprocess.run(
            ["docker", "context", "show"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        info = json.loads(subprocess.run(
            docker + ["info", "--format", "{{json .}}"],
            text=True, capture_output=True, check=True,
        ).stdout)
        run["resources"] = {key: info[key] for key in ("Architecture", "NCPU", "MemTotal", "KernelVersion")}
        stats = query(
            "SELECT count() AS rows, "
            "countIf(xxHash64(toString(toUInt64(WatchID))) % 100 != 0) AS outside_sample "
            "FROM nis_smoke.hits"
        )[0]
        if stats["rows"] != reference["rows"] or stats["rows"] != manifest["rows"] or stats["outside_sample"]:
            raise ValueError("The input table does not match participant 1's frozen sample")
        run["input_checks"] = stats
        (output / "probe.sql").write_text(probe + ";\n")
        (output / "table.sql").write_text(query("SHOW CREATE TABLE nis_smoke.hits", raw=True))
        parts = query(
            "SELECT name, rows, marks, bytes_on_disk FROM system.parts "
            "WHERE database = 'nis_smoke' AND table = 'hits' AND active ORDER BY name"
        )
        write_json(output / "parts.json", parts)
        answers = []
        for phase, count in (("warm", args.warmups), ("measure", args.repeats)):
            for repeat in range(1, count + 1):
                query_id = f"{run_id}-q1-{phase}{repeat}"
                actual = query(probe, query_id=query_id)
                answers.append({"phase": phase, "repeat": repeat, "query_id": query_id, "answer": actual})
                if actual != [reference["expected"]]:
                    raise ValueError(f"Unexpected query result in {query_id}: {actual}")
        (output / "answers.jsonl").write_text("".join(json.dumps(row) + "\n" for row in answers))
        (output / "explain.txt").write_text(query("EXPLAIN indexes = 1 " + probe, raw=True))
        for attempt in range(5):
            query("SYSTEM FLUSH LOGS")
            measurements = query(metrics_sql, parameters={"run_prefix": run_id + "-"})
            if len(measurements) == args.repeats:
                break
            time.sleep(0.2)
        logged = query(
            "SELECT type, query_id FROM system.query_log "
            "WHERE startsWith(query_id, {run_prefix:String}) AND is_initial_query = 1 "
            "AND type != 'QueryStart' ORDER BY query_id",
            parameters={"run_prefix": run_id + "-"},
        )
        expected_ids = {row["query_id"] for row in answers}
        if (len(logged) != len(expected_ids) or {row["query_id"] for row in logged} != expected_ids
                or any(row["type"] != "QueryFinish" for row in logged)):
            raise ValueError("The query log is missing warmups/repetitions or contains failed queries")
        write_json(output / "query-log-check.json", logged)
        (output / "measurements.jsonl").write_text("".join(json.dumps(row) + "\n" for row in measurements))
        run.update({"status": "complete", "answers_match_reference": True,
                    "finished_at_utc": datetime.now(timezone.utc).isoformat()})
        write_json(output / "run.json", run)
        write_summary(output)
    except Exception as error:
        run.update({"status": "failed", "error": str(error)})
        write_json(output / "run.json", run)
        raise
    print(json.dumps({"passed": True, "output_dir": str(output), "measurements": len(measurements)}))


if __name__ == "__main__":
    main()
