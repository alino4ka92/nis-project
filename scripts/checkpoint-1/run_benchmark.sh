#!/usr/bin/env bash
set -euo pipefail

database="${NIS_DATABASE:-nis_smoke}"
warmup_runs="${NIS_WARMUP_RUNS:-1}"
measured_runs="${NIS_MEASURED_RUNS:-3}"
max_threads="${NIS_MAX_THREADS:-2}"
memory_limit="${NIS_MEMORY_LIMIT_BYTES:-3221225472}"
output_dir="${NIS_OUTPUT_DIR:-/results}"

for value in "$warmup_runs" "$measured_runs" "$max_threads" "$memory_limit"; do
    if [[ ! "$value" =~ ^[0-9]+$ ]] || (( value < 1 )); then
        echo "Warmups, repetitions, threads and memory limit must be positive integers" >&2
        exit 1
    fi
done

client=(
    clickhouse-client
    --host "${NIS_CLICKHOUSE_HOST:-127.0.0.1}"
    --database "$database"
    --max_threads "$max_threads"
    --max_memory_usage "$memory_limit"
    --use_query_cache 0
    --log_queries 1
    --log_profile_events 1
    --output_format_json_quote_64bit_integers 0
)

rows="$("${client[@]}" --query 'SELECT count() FROM hits' --format TSVRaw)"
if [[ ! "$rows" =~ ^[0-9]+$ ]] || (( rows == 0 )); then
    echo "The input table must contain data" >&2
    exit 1
fi

read -r run_uuid < /proc/sys/kernel/random/uuid
run_id="nis-clickbench-${run_uuid}"
run_dir="${output_dir}/${run_id}"
mkdir -p "$run_dir"
cp /opt/nis/queries.sql "$run_dir/queries.sql"
read -r workload_sha256 _ < <(sha256sum /opt/nis/queries.sql)

query_number=0
while IFS= read -r query || [[ -n "$query" ]]; do
    [[ -z "$query" ]] && continue
    query_number=$((query_number + 1))
    printf -v query_label '%02d' "$query_number"
    echo "Running ClickBench query ${query_number}"
    for ((repeat=1; repeat<=warmup_runs; repeat++)); do
        "${client[@]}" \
            --query_id "${run_id}-q${query_number}-warm${repeat}" \
            --query "$query" --format TSV > /dev/null
    done
    for ((repeat=1; repeat<=measured_runs; repeat++)); do
        "${client[@]}" \
            --query_id "${run_id}-q${query_number}-measure${repeat}" \
            --query "$query" --format TSV > "$run_dir/q${query_label}-r${repeat}.tsv"
    done
done < /opt/nis/queries.sql

expected_measurements=$((query_number * measured_runs))
for attempt in 1 2 3 4 5; do
    "${client[@]}" --query 'SYSTEM FLUSH LOGS'
    "${client[@]}" --param_run_prefix "${run_id}-" \
        --queries-file /opt/nis/metrics.sql --format JSONEachRow > "$run_dir/measurements.jsonl"
    actual_measurements="$(wc -l < "$run_dir/measurements.jsonl")"
    (( actual_measurements == expected_measurements )) && break
    sleep 0.2
done
if (( actual_measurements != expected_measurements )); then
    echo "Expected ${expected_measurements} measurements, got ${actual_measurements}" >&2
    exit 1
fi

"${client[@]}" \
    --param_run_id "$run_id" \
    --param_revision "$NIS_CLICKBENCH_REVISION" \
    --param_workload_sha256 "$workload_sha256" \
    --param_queries "$query_number" \
    --param_warmups "$warmup_runs" \
    --param_repeats "$measured_runs" \
    --param_rows "$rows" \
    --param_threads "$max_threads" \
    --param_memory "$memory_limit" \
    --query "SELECT {run_id:String} AS run_id, version() AS server_version,
        currentDatabase() AS database, {revision:String} AS clickbench_revision,
        {workload_sha256:String} AS workload_sha256,
        {queries:UInt32} AS queries, {warmups:UInt32} AS warmup_runs,
        {repeats:UInt32} AS measured_runs, {rows:UInt64} AS input_rows,
        {threads:UInt32} AS max_threads, {memory:UInt64} AS memory_limit_bytes,
        'complete' AS status" \
    --format JSONEachRow > "$run_dir/run.json"

echo "Completed ${query_number} queries; results: ${run_dir}"
