# Материалы ClickBench для КТ1

Источник: [ClickHouse/ClickBench](https://github.com/ClickHouse/ClickBench), ревизия [`fa52f8524ad9446695018fda6a415aade3a4ccd9`](https://github.com/ClickHouse/ClickBench/tree/fa52f8524ad9446695018fda6a415aade3a4ccd9). Исходные файлы сохранены без изменений содержимого.

Подготовлен набор исходных материалов для знакомства со схемой и нагрузкой:

- [README.md](./README.md) — описание нагрузки, данных и методики авторов.
- [clickhouse/create.sql](./clickhouse/create.sql) — исходное определение таблицы.
- [clickhouse/queries.sql](./clickhouse/queries.sql) — исходные запросы.
- [clickhouse/load](./clickhouse/load) — инструкция загрузки авторского стенда.
- [clickhouse/install](./clickhouse/install) — установка и настройки авторского стенда.
- [LICENSE](./LICENSE) — Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International.

Файлы получены по адресам вида `https://raw.githubusercontent.com/ClickHouse/ClickBench/fa52f8524ad9446695018fda6a415aade3a4ccd9/<путь>`. Их SHA-256 и результаты сверки Git blob SHA с GitHub API сохранены в [source-materials.json](../../artifacts/checkpoint-1/source-materials.json).

Это исходные материалы для адаптации. Скрипты `install` и `load` сохранены для чтения: они рассчитаны на установку в системные каталоги авторского стенда. Локальная подготовка и загрузка данных описаны в [инструкции](../../nis/technical-checks.md#4-подготовка-уменьшенного-clickbench), результаты проверок — в [КТ-1](../../nis/checkpoints/01.md#данные-и-проверочный-пример).
