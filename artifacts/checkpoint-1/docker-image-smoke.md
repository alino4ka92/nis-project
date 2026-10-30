# Проверка запуска ClickHouse

Запросы выполнены через `clickhouse-client` в контейнере `nis-clickhouse`. Ниже приведены SQL и фактические ответы из [сохранённого вывода](./docker-image-smoke.jsonl). Для повторного запуска используется [SQL-файл](../../sql/checkpoint-1-smoke.sql).

## Версия сервера

```sql
SELECT version() AS version;
```

Полученный ответ:

```json
{"version":"26.9.27.3"}
```

Версия совпала с выбранным образом `clickhouse/clickhouse-server:26.9.27.3`.

## Коммит, из которого собран сервер

```sql
SELECT value AS source_commit
FROM system.build_options
WHERE name = 'VERSION_GITHASH';
```

Полученный ответ:

```json
{"source_commit":"4bea8b37b2588dd169ac54ac746bb82f09fd2c7b"}
```

Это хеш исходников запущенной сборки ClickHouse.

## Пробный запрос

```sql
SELECT 1 AS result;
```

Ожидаемый ответ — `1`. Полученный ответ:

```json
{"result":1}
```
