SELECT version() AS version;

SELECT value AS source_commit
FROM system.build_options
WHERE name = 'VERSION_GITHASH';

SELECT 1 AS result;
