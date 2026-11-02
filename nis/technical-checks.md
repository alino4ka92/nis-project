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
