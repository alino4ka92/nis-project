# Запуск стенда

Нужны Docker Compose и Python 3.11+. Команды выполняются из корня репозитория. Версии, тома и параметры заданы в [compose.yaml](../../compose.yaml).

## SIMD и архитектура процессора

Docker автоматически выбирает ARM64 или x86-64. Используйте родную архитектуру без эмуляции; [требования к CPU](https://clickhouse.com/docs/get-started/setup/self-managed/docker#compatibility).

## Первоначальная подготовка

```bash
docker compose up --wait clickhouse
```

## Проверка запуска

```bash
docker compose exec -T clickhouse clickhouse-client --multiquery --queries-file /opt/nis/sql/checkpoint-1-smoke.sql --format JSONEachRow
```

[SQL и полученные ответы](../../artifacts/checkpoint-1/docker-image-smoke.md).

## Подготовка данных

```bash
docker compose run --rm --build download
docker compose run --rm --build prepare
python3 scripts/checkpoint-1/verify.py
```

Скачиваются все 100 частей. Отбор по хешу сохраняет общий Parquet в `.local/data/checkpoint-1-all/`. Проверка загрузки сравнивает ClickHouse с независимым расчётом Python.

## Пробный запуск ClickBench

```bash
docker compose run --rm --build benchmark
```

Один прогрев и три повтора каждого запроса. В `.local/results/clickbench/` создаётся каталог прогона с одним `run.tsv`: номер запроса, ответ последнего повтора и статус выполнения. [Сохранённый результат](../../artifacts/checkpoint-1/benchmark/run.tsv).

Настройки прогрева, повторов и ресурсов меняются в сервисе `benchmark` файла `compose.yaml`.

## Проверка метрик

После загрузки выборки:

```bash
python3 scripts/checkpoint-1/measure_probe.py
```

Сохраняются ответы, пять обязательных метрик, `EXPLAIN` и сводка трёх повторов. [Описание проверки](../../nis/technical-checks.md#7-проверка-метрик), [сохранённый результат](../../artifacts/checkpoint-1/metrics/README.md).

## SQL-клиент и остановка

```bash
docker compose exec clickhouse clickhouse-client
docker compose stop clickhouse
```

Данные остаются в томе. Если старый контейнер создан через `docker run`, один раз выполните перед запуском Compose:

```bash
docker stop nis-clickhouse
docker rename nis-clickhouse nis-clickhouse-before-compose
```
