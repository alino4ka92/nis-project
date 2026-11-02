SELECT 'source' AS variant, count() AS rows,
    uniqExact(CounterID) AS counters, uniqExact(UserID) AS users,
    sumWithOverflow(cityHash64(*)) AS row_hash_sum,
    groupBitXor(cityHash64(*)) AS row_hash_xor
FROM nis_smoke.hits
UNION ALL
SELECT 'A' AS variant, count() AS rows,
    uniqExact(CounterID) AS counters, uniqExact(UserID) AS users,
    sumWithOverflow(cityHash64(*)) AS row_hash_sum,
    groupBitXor(cityHash64(*)) AS row_hash_xor
FROM nis_skipping.by_counter_8192
UNION ALL
SELECT 'B' AS variant, count() AS rows,
    uniqExact(CounterID) AS counters, uniqExact(UserID) AS users,
    sumWithOverflow(cityHash64(*)) AS row_hash_sum,
    groupBitXor(cityHash64(*)) AS row_hash_xor
FROM nis_skipping.by_user_2048
UNION ALL
SELECT 'C' AS variant, count() AS rows,
    uniqExact(CounterID) AS counters, uniqExact(UserID) AS users,
    sumWithOverflow(cityHash64(*)) AS row_hash_sum,
    groupBitXor(cityHash64(*)) AS row_hash_xor
FROM nis_skipping.by_counter_2048
UNION ALL
SELECT 'D' AS variant, count() AS rows,
    uniqExact(CounterID) AS counters, uniqExact(UserID) AS users,
    sumWithOverflow(cityHash64(*)) AS row_hash_sum,
    groupBitXor(cityHash64(*)) AS row_hash_xor
FROM nis_skipping.by_user_8192
SETTINGS max_threads = 2, max_memory_usage = 3221225472;

SELECT table, count() AS active_parts, sum(rows) AS rows,
    sum(marks) AS marks, sum(bytes_on_disk) AS bytes_on_disk
FROM system.parts
WHERE database = 'nis_skipping' AND active
GROUP BY table ORDER BY table;

SELECT name, sorting_key, primary_key, create_table_query
FROM system.tables
WHERE database = 'nis_skipping' ORDER BY name;
