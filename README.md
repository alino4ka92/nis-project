# ClickHouse: отсечение данных

**Проектное задание:** [P12-A. ClickHouse: отсечение данных](https://distsys.ru/osukhoroslov/nis2/src/branch/main/project-tasks/p12-a-clickhouse-data-skipping.md)

**Участники:**

- Полное имя
- Полное имя
- Полное имя

## Сокращённый запуск

Для стенда нужен Docker с Linux-контейнерами, для скрипта проверки — Python 3.11 или новее. Установка и проверка ClickHouse описаны в [инструкции Docker](docker/checkpoint-1/README.md), подготовка данных и проверочный пример — в [инструкции технических проверок](nis/technical-checks.md). Фактические результаты приведены в [КТ-1](nis/checkpoints/01.md).

Исходные данные и подготовленный Parquet хранятся в Docker volume и локальном каталоге `.local/`. В репозитории находятся инструкции и скрипты для скачивания всех 100 частей и отбора по хешу, [манифест с источниками и контрольными суммами](artifacts/checkpoint-1/clickbench-sample.json) и результаты проверок.

## Навигация

- [Описание проекта](nis/project.md)
- [План эксперимента](nis/experiment-plan.md)
- [Контрольная точка 1](nis/checkpoints/01.md)
- [Контрольная точка 2](nis/checkpoints/02.md)
- [Контрольная точка 3](nis/checkpoints/03.md)
- [Состояние проекта](nis/status.md)
- [Результаты](nis/results.md)
- [Финальная версия](nis/final.md)
- Код подготовки и проверки: [scripts/checkpoint-1](scripts/checkpoint-1/)
- SQL: [sql](sql/)
- Docker: [docker/checkpoint-1](docker/checkpoint-1/)
- Источники данных и правило выборки: [план эксперимента](nis/experiment-plan.md#данные-или-нагрузки)
- Материалы технических проверок: [artifacts/checkpoint-1](artifacts/checkpoint-1/)
