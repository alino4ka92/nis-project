FROM clickhouse/clickhouse-server:26.9.27.3

ENV NIS_CLICKBENCH_REVISION=fa52f8524ad9446695018fda6a415aade3a4ccd9

COPY third_party/clickbench/clickhouse/queries.sql /opt/nis/queries.sql
COPY third_party/clickbench/LICENSE /opt/nis/ClickBench-LICENSE
COPY sql/checkpoint-1-benchmark-metrics.sql /opt/nis/metrics.sql
COPY scripts/checkpoint-1/run_benchmark.sh /opt/nis/run_benchmark.sh

ENTRYPOINT ["/bin/bash", "/opt/nis/run_benchmark.sh"]
CMD []
