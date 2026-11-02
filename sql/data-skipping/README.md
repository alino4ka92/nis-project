# Подготовка сравнения вариантов хранения

SQL и параметры соответствуют [плану эксперимента](../../nis/experiment-plan.md). Это подготовленные материалы для следующего запуска на командном стенде; результаты сравнения A/B ещё не получены.

## Входные условия

Нужен запущенный ClickHouse из `compose.yaml` и проверенная таблица `nis_smoke.hits` с 1 000 659 строками из закреплённого Parquet. Подготовка выполняется по [инструкции стенда](../../docker/checkpoint-1/README.md). На время подготовки и измерений исходная таблица не изменяется.

## Создание и загрузка основной пары

Из корня репозитория:

```bash
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/data-skipping/create-main.sql
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/data-skipping/load-main.sql
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/data-skipping/check-main.sql --format JSONEachRow
```

Создаются A (`by_counter_8192`) и B (`by_user_2048`). Таблицы наследуют столбцы исходной таблицы; ключи и общие настройки задаются явно. DDL откажет при существующем имени. Загрузка добавляет данные только в пустую таблицу; частично загруженная таблица должна быть разобрана до серии. Существующие результаты и таблицы автоматически не удаляются.

Проверка должна показать одинаковые число строк, кардинальности, сумму и XOR хешей полных строк для исходника и вариантов. Хеши — контрольные отпечатки, не доказательство полного равенства. Для A/B ожидается ровно по одному активному part и суммарно 1 000 659 строк. Проверяются также ключи и фактические настройки из DDL. После подготовки не должно быть активных слияний и мутаций этих таблиц.

Сохраняйте stdout проверок, `SHOW CREATE TABLE`, сведения о parts и параметры сервера в отдельный каталог серии. Число `marks` может включать конечные метки; число выбранных гранул берётся из `EXPLAIN`.

## Профиль фильтров

```bash
docker compose exec -T clickhouse clickhouse-client --queries-file /opt/nis/sql/data-skipping/profile-workload.sql --format JSONEachRow
```

Полученные Q01–Q08 сравниваются с `expected_matched_rows` в [конфигурации](../../experiments/data-skipping.json). Для Q02/Q03 профиль впервые фиксирует точные числа. Требуются `0 < Q03 <= Q02 < total_rows`; ожидаемые числа остальных запросов должны совпасть. Затем сохраняются ответы `matched_rows` и `width_sum` всех восьми запросов на исходной таблице — это эталон основной серии.

## Одиночный запуск запроса

```bash
cat sql/data-skipping/settings.sql sql/data-skipping/queries/Q01-counter_eq.sql | docker compose exec -T clickhouse clickhouse-client --multiquery --param_database nis_skipping --param_table by_counter_8192 --format JSONEachRow
```

Для эталонного ответа используются `--param_database nis_smoke --param_table hits`. Для B меняется только `--param_table by_user_2048`. Аналогично запускаются остальные файлы Q01–Q08. Сначала в той же клиентской сессии применяются настройки, затем выполняется запрос. Уникальный `query_id` и выгрузку метрик для серии должен задавать сборщик.

Чтобы получить `EXPLAIN indexes = 1`, перед `SELECT` того же запроса добавляется соответствующий префикс; настройки сохраняются. Команды проверки и планирования не включаются в измеряемые повторы.

## Контроль двух факторов

После проверки доступного места создаются C (`by_counter_2048`) и D (`by_user_8192`):

```bash
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/data-skipping/create-controls.sql
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/data-skipping/load-controls.sql
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/data-skipping/check-all.sql --format JSONEachRow
```

Контрольная серия заново измеряет все четыре конфигурации. Порядок, прогревы и повторы закреплены в JSON-плане. Она позволяет раздельно сравнить ключи при одинаковой гранулярности и гранулярность при одинаковом ключе.

## Проверка подготовленных материалов

Для проверки параметров по сохранённым ответам достаточно Python 3.11+. Для разбора SQL дополнительно используется SQLGlot 30.27.0 в отдельном окружении:

```bash
python3 -m venv .local/design-check-venv
.local/design-check-venv/bin/pip install sqlglot==30.27.0
.local/design-check-venv/bin/python scripts/checkpoint-1/validate_design.py --require-sqlglot --output .local/results/design-check.json
```

Проверка сверяет параметры с артефактами, ссылки на SQL, схему ответов и настройки конфигураций. SQLGlot разбирает DDL и запросы в диалекте ClickHouse; `OPTIMIZE ... FINAL` поддерживается им только как непрозрачная команда и отдельно перечисляется в отчёте. Такой разбор не заменяет выполнение на ClickHouse 26.9.27.3. Сохранённая проверка подготовки находится в [design-check.json](../../artifacts/checkpoint-1/design-check.json).

Существующий `measure_probe.py` проверяет один запрос к `nis_smoke.hits`. Его расширение на новую нагрузку, сверка независимых агрегатов и полный сбор основной серии запланированы к КТ-2.
