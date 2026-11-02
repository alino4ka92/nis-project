SELECT count() AS matched_rows, sum(ResolutionWidth) AS width_sum
FROM nis_smoke.hits
WHERE CounterID = 251755
SETTINGS max_threads = 2, use_query_cache = 0;
