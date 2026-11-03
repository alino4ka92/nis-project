# Технические проверки

## 1. Проверка ревизий

Ревизии компонентов и контрольные суммы исходных файлов записаны в [source-materials.json](../artifacts/checkpoint-1/source-materials.json).

## 2. Запуск ClickHouse

[Команды запуска](../docker/checkpoint-1/README.md#первоначальная-подготовка). Ожидаются версия `26.9.27.3` и ответ `1` на `SELECT 1`. [SQL и ответы](../artifacts/checkpoint-1/docker-image-smoke.md).

## 3. Материалы ClickBench

[Происхождение схемы и запросов](../third_party/clickbench/ORIGIN.md). В репозитории сохранены файлы закреплённой ревизии.

## 4. Подготовка уменьшенного ClickBench

[Команды подготовки](../docker/checkpoint-1/README.md#подготовка-данных) скачивают все 100 частей и применяют `xxHash64(toString(toUInt64(WatchID))) % 100 = 0`. Результат — общий Parquet со всеми колонками; правило и контрольная сумма находятся в [манифесте](../artifacts/checkpoint-1/clickbench-sample.json).

## 5. Загрузка и проверочный запрос

[verify.py](../scripts/checkpoint-1/verify.py) загружает набор в `nis_smoke.hits` и сравнивает число строк и результат [SQL-запроса](../sql/checkpoint-1-clickbench-probe.sql) с независимым расчётом Python. Ожидается `passed: true` в [результате проверки](../artifacts/checkpoint-1/clickbench-check.json); [ожидаемый ответ](../artifacts/checkpoint-1/clickbench-reference.json) сохранён отдельно.

## 6. Пробный запуск ClickBench

[Команда запуска](../docker/checkpoint-1/README.md#пробный-запуск-clickbench). Ожидаются 43 строки с ответами и статусом `OK` в [run.tsv](../artifacts/checkpoint-1/benchmark/run.tsv).

## 7. Проверка метрик

При работающем `nis-clickhouse` и загруженной выборке выполнить из корня репозитория:

```bash
python3 scripts/checkpoint-1/measure_probe.py
```

Один прогрев и три измеряемых повтора; два потока и лимит памяти запроса 3 ГиБ. Для другого Docker-контекста добавить `--context ИМЯ_КОНТЕКСТА`.

Ожидаются `passed: true`, ответ `matched_rows = 1004`, `width_sum = 1522846` во всех выполнениях и три записи со всеми пятью метриками. Пропуски, дубликаты и несовпадения завершают проверку ошибкой.

Каталог прогона создаётся в `.local/results/checkpoint-1-metrics/`: настройки и статус — в `run.json`, ответы — в `answers.jsonl`, метрики — в `measurements.jsonl`, сводка — в `summary.tsv`. Также сохраняются `EXPLAIN`, DDL, parts и подтверждение завершения запросов.

[Фактический результат](../artifacts/checkpoint-1/metrics/README.md). Повторная обработка сохранённых измерений без Docker и тесты:

```bash
python3 scripts/checkpoint-1/summarize_metrics.py artifacts/checkpoint-1/metrics
python3 -m unittest discover -s scripts/checkpoint-1 -p 'test_*.py' -v
```
