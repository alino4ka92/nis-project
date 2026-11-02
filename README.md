# ClickHouse: отсечение данных

**Задание:** [P12-A](https://distsys.ru/osukhoroslov/nis2/src/branch/main/project-tasks/p12-a-clickhouse-data-skipping.md)

**Участники:**

- Полное имя
- Andrey Balabekyan (V0S7ER)
- Поливин Никита Евгеньевич

## Запуск

Нужны Docker Compose и Python 3.11+. [Команды запуска](docker/checkpoint-1/README.md), настройки — в [compose.yaml](compose.yaml). Датасет создаётся локально из всех 100 частей ClickBench с отбором по хешу.

## Материалы

- [Проект](nis/project.md), [план эксперимента](nis/experiment-plan.md), [КТ-1](nis/checkpoints/01.md).
- [Технические проверки](nis/technical-checks.md) и [результат запуска бенчмарка](artifacts/checkpoint-1/benchmark/run.tsv).
- [Проверка пяти метрик](artifacts/checkpoint-1/metrics/README.md): ответы проверочного запроса, измерения, `EXPLAIN` и сводка повторов.
- [SQL запросов и настройки сравнения](sql/data-skipping/README.md).
- [Код](scripts/checkpoint-1/), [SQL](sql/), [манифест датасета](artifacts/checkpoint-1/clickbench-sample.json). Данные хранятся в Docker volume и `.local/`.
- [Состояние](nis/status.md), [результаты](nis/results.md), [финальная сдача](nis/final.md).
