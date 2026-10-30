# Инструкции технических проверок

Команды выполняются из корня репозитория. Команды `curl` и Git ниже приведены для Bash (Linux, macOS или WSL); запуск ClickHouse через Docker описан отдельно. Результаты выполненных проверок сохраняются в [КТ1](./checkpoints/01.md#технические-проверки).

## 1. Проверка ревизий

Получить сведения о коммитах из карточки задания:

```bash
curl --fail-with-body --silent --show-error --location https://api.github.com/repos/ClickHouse/ClickHouse/commits/2da63c1b42ca
curl --fail-with-body --silent --show-error --location https://api.github.com/repos/ClickHouse/ClickBench/commits/fa52f8524ad9
```

Проверить успешность запросов и поле `sha`: полный хеш должен начинаться с соответствующей ревизии из карточки. Зафиксированные ревизии находятся в [source-materials.json](../artifacts/checkpoint-1/source-materials.json).

## 2. Запуск ClickHouse

[Общая инструкция Docker](../docker/checkpoint-1/README.md) содержит получение образа, запуск контейнера, выбор ARM64 или x86-64, проверку клиента и остановку стенда. Команды проверки запуска находятся в её [соответствующем разделе](../docker/checkpoint-1/README.md#проверка-запуска).

Используемый [SQL проверки](../sql/checkpoint-1-smoke.sql) запрашивает версию сервера и хеш сборки, затем выполняет `SELECT 1`. Для выбранного образа ожидается версия 26.9.27.3 и результат `1`.

Запросы и фактические ответы собраны в [одном Markdown-файле](../artifacts/checkpoint-1/docker-image-smoke.md).

## 3. Материалы ClickBench

Подготовленные файлы и их назначение перечислены в [ORIGIN.md](../third_party/clickbench/ORIGIN.md). Все исходные файлы получаются с одной закреплённой ревизии.

Пример получения схемы:

```bash
mkdir -p third_party/clickbench/clickhouse
curl --fail --silent --show-error --location --output third_party/clickbench/clickhouse/create.sql https://raw.githubusercontent.com/ClickHouse/ClickBench/fa52f8524ad9446695018fda6a415aade3a4ccd9/clickhouse/create.sql
```

Для других файлов меняются путь после хеша коммита и соответствующий локальный путь. Ревизия остаётся той же.

Пример проверки происхождения схемы:

```bash
git hash-object third_party/clickbench/clickhouse/create.sql
curl --fail --silent --show-error --location 'https://api.github.com/repos/ClickHouse/ClickBench/contents/clickhouse/create.sql?ref=fa52f8524ad9446695018fda6a415aade3a4ccd9'
```

Локальный Git blob SHA должен совпасть с полем `sha` ответа GitHub API. Аналогичная проверка выполняется для остальных подготовленных файлов; результаты сохранены в [source-materials.json](../artifacts/checkpoint-1/source-materials.json).

## 4. Подготовка уменьшенного ClickBench

Для КТ-1 и эксперимента используется выборка из всех 100 исходных файлов ClickBench. Ко всем частям применяется условие `xxHash64(toString(toUInt64(WatchID))) % 100 = 0`, выбранные строки объединяются и фиксируются для обоих вариантов таблицы. Источники перечислены в [скрипте скачивания](../scripts/checkpoint-1/download_sources.py), правило и ожидаемый объём описаны в [плане эксперимента](./experiment-plan.md#данные-или-нагрузки).

Хешируется десятичная запись идентификатора события как беззнакового 64-битного числа, seed равен нулю. При повторении на тех же данных выбираются те же строки. [Скрипт подготовки](../scripts/checkpoint-1/prepare_sample.py) читает все исходные файлы порциями и сохраняет общий `hits_small.parquet`. В манифест попадают правило отбора, число строк и SHA-256 всех исходников и результата.

Собрать образ и подготовить данные:

```bash
docker build -f docker/checkpoint-1/data.Dockerfile -t nis-clickbench-data scripts/checkpoint-1
docker run --name nis-clickbench-download --cpus 2 --memory 1g --mount type=volume,source=nis-clickbench-sources,target=/data nis-clickbench-data python download_sources.py --output /data --workers 8
docker run --name nis-clickbench-prepare-all --cpus 2 --memory 3g --mount type=volume,source=nis-clickbench-sources,target=/sources,readonly --mount type=volume,source=nis-clickbench-sample-all,target=/data nis-clickbench-data bash -c 'python prepare_sample.py --source-dir /sources --source-count 100 --output /data --modulus 100 --remainder 0 && python reference.py /data/hits_small.parquet --output /data/reference.json'
```

Docker выбирает ARM64 или x86-64 по своему окружению. Исходники читаются по одному и тому же правилу на обеих архитектурах. Контейнер ограничен двумя CPU и 3 ГиБ памяти.

[Независимый расчёт](../scripts/checkpoint-1/reference.py) читает сохранённый Parquet через PyArrow и обычными операциями Python считает строки и сумму `ResolutionWidth` для выбранного `CounterID`. Ожидаемый ответ получается до загрузки в ClickHouse. Фильтр выбирается по присутствующему в данных значению; его параметры и ожидаемый ответ сохраняются в `reference.json`.

Получить файлы из завершённого контейнера:

```bash
mkdir -p .local/data/checkpoint-1-all
docker cp nis-clickbench-prepare-all:/data/hits_small.parquet .local/data/checkpoint-1-all/
docker cp nis-clickbench-prepare-all:/data/sample-manifest.json .local/data/checkpoint-1-all/
docker cp nis-clickbench-prepare-all:/data/reference.json .local/data/checkpoint-1-all/
```

Исходники и итоговая выборка сохраняются в отдельных Docker volume. Локальный каталог `.local/` исключён из Git. Повторный запуск готового контейнера командой `docker start --attach nis-clickbench-prepare-all` проверяет контрольную сумму сохранённого датасета и использует его повторно.

## 5. Загрузка и проверочный запрос

При работающем `nis-clickhouse` выполнить из корня репозитория, используя Python 3.11 или новее:

```bash
python3 scripts/checkpoint-1/verify.py --data-dir .local/data/checkpoint-1-all
```

Для явно выбранного локального Docker-контекста добавить `--context ИМЯ_КОНТЕКСТА`. Этот же контекст должен использоваться в командах подготовки данных.

[Скрипт проверки](../scripts/checkpoint-1/verify.py) создаёт учебную таблицу `nis_smoke.hits` по закреплённой схеме ClickBench и загружает в неё сохранённый Parquet. Повторный запуск проверяет уже заполненную таблицу. Существующие строки сохраняются; при несовпадении с ожидаемыми данными проверка завершается ошибкой.

[Проверочный запрос](../sql/checkpoint-1-clickbench-probe.sql) считает строки и сумму `ResolutionWidth` для `CounterID` из независимого расчёта. Дополнительно сверяются число строк и число разных счётчиков и пользователей; все строки должны удовлетворять правилу отбора по хешу. Сохраняются `EXPLAIN indexes = 1`, сведения о parts, расход памяти и место на диске.

Результаты записываются в [clickbench-sample.json](../artifacts/checkpoint-1/clickbench-sample.json), [clickbench-reference.json](../artifacts/checkpoint-1/clickbench-reference.json) и [clickbench-check.json](../artifacts/checkpoint-1/clickbench-check.json). Ожидается `passed: true`, совпадение проверочного ответа с Python и отсутствие строк вне выбранного остатка хеша.

## 6. Пробный запуск ClickBench в Docker

После загрузки данных выполни [сборку и запуск образа бенчмарка](../docker/checkpoint-1/README.md#пробный-запуск-clickbench). Ожидается успешное выполнение 43 исходных запросов: один прогрев и три измеряемых повтора каждого. В каталоге прогона должны появиться `run.json` со статусом `complete`, 129 ответов в TSV и 129 записей в `measurements.jsonl` с временем, прочитанными строками и байтами, CPU и памятью.

[Фактический результат](../artifacts/checkpoint-1/benchmark/README.md) содержит настройки, SQL, ответы и измерения выполненного прогона.
