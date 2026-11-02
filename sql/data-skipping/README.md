# Таблицы, запросы и настройки эксперимента

К КТ-1 подготовлены SQL создания четырёх таблиц, восемь запросов и общие настройки. Данные и порядок измерений описаны в [плане эксперимента](../../nis/experiment-plan.md).

## Создание таблиц

[create-tables.sql](./create-tables.sql) создаёт четыре пустые таблицы MergeTree со столбцами исходной `nis_smoke.hits`:

| Вариант | Таблица в `nis_skipping` | Первый столбец ключа | Гранулярность |
|---|---|---|---:|
| A, baseline | `by_counter_8192` | `CounterID` | 8192 |
| B | `by_user_2048` | `UserID` | 2048 |
| C | `by_counter_2048` | `CounterID` | 2048 |
| D | `by_user_8192` | `UserID` | 8192 |

Полные `PRIMARY KEY`, `ORDER BY` и одинаковые для всех таблиц настройки заданы в SQL. Для запуска нужны работающий стенд и подготовленная таблица `nis_smoke.hits`; имена новых таблиц должны быть свободны. Из корня репозитория:

```bash
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/data-skipping/create-tables.sql
```

## Запросы

В `queries/` находятся Q01–Q08. Во всех запросах вычисляются `count()` и `sum(ResolutionWidth)`; имя таблицы передаётся параметром. Настройки запросов сохранены в [settings.sql](./settings.sql).

После создания таблиц запрос можно выполнить из корня репозитория:

```bash
cat sql/data-skipping/settings.sql sql/data-skipping/queries/Q01-counter_eq.sql | docker compose exec -T clickhouse clickhouse-client --multiquery --param_database nis_skipping --param_table by_counter_8192 --format JSONEachRow
```

Для остальных вариантов меняется `--param_table`: `by_user_2048`, `by_counter_2048` или `by_user_8192`. Для эталонного ответа используется исходная таблица: `--param_database nis_smoke --param_table hits`. Аналогично выполняются остальные запросы.

Выполнение DDL на командном стенде, загрузку и проверку данных, подключение запросов к сборщику и сравнение результатов готовим к КТ-2. Подготовленный SQL ещё не выполнялся на ClickHouse.
