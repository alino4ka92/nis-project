INSERT INTO nis_skipping.by_counter_2048
SELECT * FROM nis_smoke.hits
WHERE (SELECT count() FROM nis_skipping.by_counter_2048) = 0
SETTINGS max_threads = 1, max_insert_threads = 1, max_memory_usage = 3221225472;

OPTIMIZE TABLE nis_skipping.by_counter_2048 FINAL;

INSERT INTO nis_skipping.by_user_8192
SELECT * FROM nis_smoke.hits
WHERE (SELECT count() FROM nis_skipping.by_user_8192) = 0
SETTINGS max_threads = 1, max_insert_threads = 1, max_memory_usage = 3221225472;

OPTIMIZE TABLE nis_skipping.by_user_8192 FINAL;
