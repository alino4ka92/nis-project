FROM clickhouse/clickhouse-server:26.9.27.3

COPY third_party/clickbench/clickhouse/queries.sql /opt/nis/queries.sql
COPY third_party/clickbench/LICENSE /opt/nis/ClickBench-LICENSE
COPY scripts/checkpoint-1/run_benchmark.sh /opt/nis/run_benchmark.sh

ENTRYPOINT ["/bin/bash", "/opt/nis/run_benchmark.sh"]
CMD []
