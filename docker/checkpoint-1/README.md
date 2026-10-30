# ClickHouse в Docker: ARM64 и x86-64

Используем готовый официальный образ **`clickhouse/clickhouse-server:26.9.27.3`**. Он опубликован для `linux/arm64` и `linux/amd64`; Docker выбирает подходящий вариант для своего окружения. Нужен работающий Docker с Linux-контейнерами: Docker Engine на Linux либо Docker Desktop на Windows/macOS.

Результаты выполненного запуска и использованные версии приведены в [КТ-1](../../nis/checkpoints/01.md#подготовка-и-проверка-стенда).

Команды выполняются из корня репозитория в Bash или PowerShell. Перед началом выбери свой локальный Docker-контекст и проверь его:

```bash
docker version
docker info --format '{{.Architecture}}'
```

## Первоначальная подготовка

```bash
docker pull clickhouse/clickhouse-server:26.9.27.3
docker run --detach --name nis-clickhouse --ulimit nofile=262144:262144 --mount type=volume,source=nis-clickhouse-data-26-9-27-3,target=/var/lib/clickhouse clickhouse/clickhouse-server:26.9.27.3
```

Данные сохраняются в именованном Docker volume. Клиент запускается в том же контейнере; устанавливать ClickHouse на компьютер отдельно не требуется.

### Что менять в зависимости от процессора

Обычно в командах выше менять ничего не нужно. Для явного выбора добавь одинаковый параметр `--platform` к `docker pull` и `docker run`:

| Процессор компьютера | Параметр | Примеры компьютеров |
|---|---|---|
| ARM64 (`arm64`, `aarch64`) | `--platform linux/arm64` | Apple Silicon, Linux-серверы на ARM |
| x86-64 (`amd64`, `x86_64`) | `--platform linux/amd64` | Intel/AMD на Linux или Windows, Intel Mac |

Например, команда получения образа для ARM64:

```bash
docker pull --platform linux/arm64 clickhouse/clickhouse-server:26.9.27.3
```

Для x86-64 в ней меняется только `linux/arm64` на `linux/amd64`. Платформа должна соответствовать процессору: запуск чужой архитектуры через эмуляцию меняет производительность и не подходит для наших измерений.

У образа есть требования к CPU: для AMD64 указан уровень x86-64-v3 с AVX2, для ARM64 — ARMv8.2-A с RCpc. [Требования официального образа](https://clickhouse.com/docs/get-started/setup/self-managed/docker#compatibility).

## Проверка запуска

Дождись в журнале строки `Ready for connections.`:

```bash
docker logs --tail 50 nis-clickhouse
```

Затем выполни проверку из репозитория:

```bash
docker cp sql/checkpoint-1-smoke.sql nis-clickhouse:/tmp/checkpoint-1-smoke.sql
docker exec nis-clickhouse clickhouse-client --multiquery --queries-file /tmp/checkpoint-1-smoke.sql --format JSONEachRow
```

Ожидаются версия **26.9.27.3**, хеш исходников запущенной сборки и `result = 1`. Результат и архитектуру нужно сохранить для своей машины в материалах проверки. Наличие обеих платформ в образе не заменяет фактический запуск на компьютере участника.

Для интерактивного SQL-клиента:

```bash
docker exec -it nis-clickhouse clickhouse-client
```

## Пробный запуск ClickBench

Перед запуском подготовь выборку и загрузи `nis_smoke.hits` по [инструкции технических проверок](../../nis/technical-checks.md#4-подготовка-уменьшенного-clickbench). ClickHouse должен работать в контейнере `nis-clickhouse`.

Собери образ из корня репозитория и запусти бенчмарк:

```bash
docker build -f docker/checkpoint-1/benchmark.Dockerfile -t nis-clickbench-benchmark .
docker run --name nis-clickbench-benchmark --network container:nis-clickhouse --cpus 1 --memory 1g --mount type=volume,source=nis-clickbench-runs,target=/results nis-clickbench-benchmark
```

[Образ](./benchmark.Dockerfile) содержит клиент ClickHouse, исходные 43 запроса закреплённой ревизии ClickBench и [скрипт запуска](../../scripts/checkpoint-1/run_benchmark.sh). Docker выбирает нативную архитектуру, ARM64 или x86-64. Клиент подключается к серверу через общую сеть контейнеров; публиковать порты на компьютере не требуется.

Для каждого запроса выполняются один прогрев и три измеряемых повтора. Кэш готовых ответов отключён; системный файловый кэш между повторами сохраняется. Ответы запросов записываются в TSV, а время, прочитанные строки и байты, CPU и память — в `measurements.jsonl` из `system.query_log`. Настройки и ревизия нагрузки сохраняются в `run.json`.

По умолчанию запрос использует до двух потоков и до 3 ГиБ памяти на сервере. Параметры `--cpus 1 --memory 1g` ограничивают контейнер клиента. Для изменения настроек запроса добавь перед именем образа, например, `-e NIS_MAX_THREADS=4 -e NIS_MEMORY_LIMIT_BYTES=4294967296`. Число прогревов и повторов задаётся через `NIS_WARMUP_RUNS` и `NIS_MEASURED_RUNS`, база — через `NIS_DATABASE`.

В конце выводится путь отдельного каталога прогона. Скопировать все сохранённые результаты:

```bash
mkdir -p artifacts/checkpoint-1/benchmark
docker cp nis-clickbench-benchmark:/results/. artifacts/checkpoint-1/benchmark/
```

Повторный прогон запускается той же командой внутри уже созданного контейнера:

```bash
docker start --attach nis-clickbench-benchmark
```

Для него создаётся новый каталог в том же volume. [Результат выполненного пробного прогона](../../artifacts/checkpoint-1/benchmark/README.md) сохранён в репозитории.

## SIMD и архитектура процессора

SIMD — способ обрабатывать несколько элементов одной инструкцией. **AVX/AVX2 относятся к x86-64; у ARM64 есть свои SIMD-инструкции, в частности Neon.** Это определяется процессором, а не названием операционной системы. Поэтому Intel Mac и Mac на Apple Silicon используют разные варианты образа. Подробнее: [Arm Neon](https://www.arm.com/technologies/neon), [выбор платформы Docker](https://docs.docker.com/build/building/multi-platform/).

Условия сравнения на одной машине и учёт серий на разных архитектурах описаны в [плане эксперимента](../../nis/experiment-plan.md#конфигурации-и-план-запусков).

## Повторный запуск и остановка

```bash
docker start nis-clickhouse
docker stop nis-clickhouse
```

`start` используется для уже созданного контейнера; данные остаются в volume после `stop`. Команды установки и остановки самого Docker зависят от выбранного инструмента на компьютере участника и не являются частью эксперимента.

Для подключения к уже подготовленному локальному стенду используется контекст `colima-nis-project`: `docker --context colima-nis-project exec -it nis-clickhouse clickhouse-client`.
