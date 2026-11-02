SELECT
    toUInt32(extract(query_id, '-q([0-9]+)-')) AS query_number,
    toUInt32(extract(query_id, '-measure([0-9]+)$')) AS repeat,
    query_id,
    query_duration_ms AS elapsed_ms,
    read_rows,
    read_bytes,
    ProfileEvents['UserTimeMicroseconds'] AS user_cpu_time_us,
    ProfileEvents['SystemTimeMicroseconds'] AS system_cpu_time_us,
    user_cpu_time_us + system_cpu_time_us AS cpu_time_us,
    mapContains(ProfileEvents, 'UserTimeMicroseconds')
        OR mapContains(ProfileEvents, 'SystemTimeMicroseconds') AS has_cpu_events,
    memory_usage AS memory_usage_bytes
FROM system.query_log
WHERE type = 'QueryFinish'
    AND is_initial_query = 1
    AND exception_code = 0
    AND startsWith(query_id, {run_prefix:String})
    AND match(query_id, '-q[0-9]+-measure[0-9]+$')
ORDER BY query_number, repeat;
