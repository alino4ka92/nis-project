"""Calculate an expected query result from Parquet without ClickHouse."""

import argparse
from collections import Counter
import json
from pathlib import Path

import pyarrow.parquet as pq


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    counters = Counter()
    widths = Counter()
    users = set()
    parquet = pq.ParquetFile(args.sample)
    for batch in parquet.iter_batches(
        batch_size=32768, columns=["CounterID", "ResolutionWidth", "UserID"]
    ):
        columns = batch.to_pydict()
        for counter, width in zip(columns["CounterID"], columns["ResolutionWidth"]):
            counters[counter] += 1
            widths[counter] += width
        users.update(columns["UserID"])

    if not counters:
        raise ValueError("the sample is empty")
    target_count = max(100, parquet.metadata.num_rows // 1000)
    counter_id = min(counters, key=lambda key: (abs(counters[key] - target_count), key))
    query = (
        "SELECT count() AS matched_rows, sum(ResolutionWidth) AS width_sum "
        f"FROM nis_smoke.hits WHERE CounterID = {counter_id}"
    )
    reference = {
        "method": "PyArrow reads the frozen Parquet; Python counts and sums the original values",
        "rows": parquet.metadata.num_rows,
        "distinct_counters": len(counters),
        "distinct_users": len(users),
        "counter_id": counter_id,
        "query": query,
        "expected": {"matched_rows": counters[counter_id], "width_sum": widths[counter_id]},
    }
    args.output.write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference), flush=True)


if __name__ == "__main__":
    main()
