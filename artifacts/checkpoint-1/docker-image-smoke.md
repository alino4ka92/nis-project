# Проверка запуска ClickHouse

Запросы выполнены через `clickhouse-client` в контейнере `nis-clickhouse`. [SQL-файл](../../sql/checkpoint-1-smoke.sql).

| Запрос | Полученный ответ |
|---|---|
| `SELECT version()` | `26.9.27.3` |
| `SELECT value FROM system.build_options WHERE name = 'VERSION_GITHASH'` | `4bea8b37b2588dd169ac54ac746bb82f09fd2c7b` |
| `SELECT 1` | `1`, как и ожидалось |
