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
printf 'query\twarmups\trepeats\tstatus\tanswer\n' > "$run_dir/run.tsv"

query_number=0
while IFS= read -r query || [[ -n "$query" ]]; do
    [[ -z "$query" ]] && continue
    query_number=$((query_number + 1))
    echo "Running ClickBench query ${query_number}"
    for ((repeat=1; repeat<=warmup_runs; repeat++)); do
        "${client[@]}" \
            --query_id "${run_id}-q${query_number}-warm${repeat}" \
            --query "$query" --format JSONCompactEachRow > /dev/null
    done
    for ((repeat=1; repeat<=measured_runs; repeat++)); do
        answer="$("${client[@]}" \
            --query_id "${run_id}-q${query_number}-measure${repeat}" \
            --query "$query" --format JSONCompactEachRow)"
    done
    answer="[${answer//$'\n'/,}]"
    printf '%s\t%s\t%s\tOK\t%s\n' "$query_number" "$warmup_runs" "$measured_runs" "$answer" >> "$run_dir/run.tsv"
done < /opt/nis/queries.sql

if (( query_number == 0 )); then
    echo "The workload contains no queries" >&2
    exit 1
fi

echo "Completed ${query_number} queries; report: ${run_dir}/run.tsv"
