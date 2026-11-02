CREATE DATABASE IF NOT EXISTS nis_skipping;

-- A: ключ с CounterID в начале, гранулярность 8192 (baseline).
CREATE TABLE nis_skipping.by_counter_8192 AS nis_smoke.hits
ENGINE = MergeTree
PRIMARY KEY (CounterID, EventDate, UserID, EventTime, WatchID)
ORDER BY (CounterID, EventDate, UserID, EventTime, WatchID)
SETTINGS
    index_granularity = 8192,
    index_granularity_bytes = 0,
    min_rows_for_wide_part = 0,
    min_bytes_for_wide_part = 0,
    auto_statistics_types = '',
    fsync_after_insert = 1;

-- B: ключ с UserID в начале, гранулярность 2048.
CREATE TABLE nis_skipping.by_user_2048 AS nis_smoke.hits
ENGINE = MergeTree
PRIMARY KEY (UserID, EventDate, CounterID, EventTime, WatchID)
ORDER BY (UserID, EventDate, CounterID, EventTime, WatchID)
SETTINGS
    index_granularity = 2048,
    index_granularity_bytes = 0,
    min_rows_for_wide_part = 0,
    min_bytes_for_wide_part = 0,
    auto_statistics_types = '',
    fsync_after_insert = 1;

-- C: ключ как у A, гранулярность 2048.
CREATE TABLE nis_skipping.by_counter_2048 AS nis_smoke.hits
ENGINE = MergeTree
PRIMARY KEY (CounterID, EventDate, UserID, EventTime, WatchID)
ORDER BY (CounterID, EventDate, UserID, EventTime, WatchID)
SETTINGS
    index_granularity = 2048,
    index_granularity_bytes = 0,
    min_rows_for_wide_part = 0,
    min_bytes_for_wide_part = 0,
    auto_statistics_types = '',
    fsync_after_insert = 1;

-- D: ключ как у B, гранулярность 8192.
CREATE TABLE nis_skipping.by_user_8192 AS nis_smoke.hits
ENGINE = MergeTree
PRIMARY KEY (UserID, EventDate, CounterID, EventTime, WatchID)
ORDER BY (UserID, EventDate, CounterID, EventTime, WatchID)
SETTINGS
    index_granularity = 8192,
    index_granularity_bytes = 0,
    min_rows_for_wide_part = 0,
    min_bytes_for_wide_part = 0,
    auto_statistics_types = '',
    fsync_after_insert = 1;
