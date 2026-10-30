SELECT
    toUInt32(extract(query_id, '-q([0-9]+)-')) AS query_number,
    toUInt32(extract(query_id, '-measure([0-9]+)$')) AS repeat,
    query_id,
    query_duration_ms AS elapsed_ms,
    read_rows,
    read_bytes,
    ProfileEvents['UserTimeMicroseconds']
        + ProfileEvents['SystemTimeMicroseconds'] AS cpu_time_us,
    memory_usage AS memory_usage_bytes
FROM system.query_log
WHERE type = 'QueryFinish'
    AND startsWith(query_id, {run_prefix:String})
    AND position(query_id, '-measure') > 0
ORDER BY query_number, repeat;
