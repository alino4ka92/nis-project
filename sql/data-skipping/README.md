# Запросы и настройки эксперимента

К КТ-1 подготовлены восемь запросов и общие настройки. Четыре комбинации ключа и гранулярности, данные и порядок измерений описаны в [плане эксперимента](../../nis/experiment-plan.md).

В `queries/` находятся Q01–Q08. Во всех запросах вычисляются `count()` и `sum(ResolutionWidth)`; имя таблицы передаётся параметром. Настройки запросов сохранены в [settings.sql](./settings.sql).

После создания таблиц запрос можно выполнить из корня репозитория:

```bash
cat sql/data-skipping/settings.sql sql/data-skipping/queries/Q01-counter_eq.sql | docker compose exec -T clickhouse clickhouse-client --multiquery --param_database nis_skipping --param_table by_counter_8192 --format JSONEachRow
```

Для остальных вариантов меняется `--param_table`: `by_user_2048`, `by_counter_2048` или `by_user_8192`. Для эталонного ответа используется исходная таблица: `--param_database nis_smoke --param_table hits`. Аналогично выполняются остальные запросы.

Создание, загрузку и проверку четырёх таблиц, подключение запросов к сборщику и сравнение результатов готовим к КТ-2. Новые таблицы и измерения сравнения к КТ-1 не выполнялись.
