"""Freeze a hash sample of the published ClickBench Parquet files."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import resource
import time
import urllib.error
import urllib.request
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import xxhash


def source_url(number):
    return (
        "https://datasets.clickhouse.com/hits_compatible/"
        f"athena_partitioned/hits_{number}.parquet"
    )


def download(url, destination):
    headers = {"User-Agent": "nis-project/1"}
    request = urllib.request.Request(url, headers=headers, method="HEAD")
    with urllib.request.urlopen(request, timeout=90) as response:
        size = int(response.headers["Content-Length"])
        etag = response.headers.get("ETag")
    with destination.open("wb") as target:
        target.truncate(size)

    def download_range(bounds):
        start, end = bounds
        range_headers = {**headers, "Range": f"bytes={start}-{end}"}
        if etag:
            range_headers["If-Match"] = etag
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers=range_headers)
                with urllib.request.urlopen(request, timeout=90) as source:
                    expected_range = f"bytes {start}-{end}/{size}"
                    if source.status != 206 or source.headers.get("Content-Range") != expected_range:
                        raise urllib.error.URLError("server did not return the requested byte range")
                    received = 0
                    with destination.open("r+b") as target:
                        target.seek(start)
                        while chunk := source.read(1024 * 1024):
                            target.write(chunk)
                            received += len(chunk)
                    if received != end - start + 1:
                        raise urllib.error.URLError("incomplete byte range")
                return
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    chunk_size = (size + 15) // 16
    ranges = [(start, min(start + chunk_size, size) - 1) for start in range(0, size, chunk_size)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(download_range, ranges))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, help="directory with downloaded hits_N.parquet files")
    parser.add_argument("--source-wait-timeout", type=int, default=0,
                        help="seconds to wait for each file in source-dir")
    parser.add_argument("--modulus", type=int, default=100)
    parser.add_argument("--remainder", type=int, default=0)
    parser.add_argument("--source-count", type=int, default=100)
    args = parser.parse_args()
    if args.modulus < 1 or not 0 <= args.remainder < args.modulus:
        parser.error("require modulus > 0 and 0 <= remainder < modulus")
    if not 1 <= args.source_count <= 100:
        parser.error("source-count must be between 1 and 100")
    if args.source_wait_timeout < 0:
        parser.error("source-wait-timeout must be nonnegative")
    if args.source_wait_timeout and args.source_dir is None:
        parser.error("source-wait-timeout requires source-dir")

    args.output.mkdir(parents=True, exist_ok=True)
    sample_path = args.output / "hits_small.parquet"
    manifest_path = args.output / "sample-manifest.json"
    if manifest_path.exists() and sample_path.exists():
        manifest = json.loads(manifest_path.read_text())
        with sample_path.open("rb") as sample:
            digest = hashlib.file_digest(sample, "sha256").hexdigest()
        if (
            manifest["modulus"] == args.modulus
            and manifest["remainder"] == args.remainder
            and len(manifest["sources"]) == args.source_count
            and manifest["sample_sha256"] == digest
        ):
            print(f"Reusing verified sample: {manifest['rows']} rows", flush=True)
            return
        parser.error("existing sample does not match the requested selection")
    if sample_path.exists() or manifest_path.exists():
        parser.error("incomplete sample exists; choose an empty directory")

    if args.source_dir is not None and not args.source_wait_timeout:
        missing = [
            number for number in range(args.source_count)
            if not (args.source_dir / f"hits_{number}.parquet").is_file()
        ]
        if missing:
            parser.error(f"source files are missing: {missing}")

    started = time.monotonic()
    sources = []
    writer = None
    try:
        for number in range(args.source_count):
            url = source_url(number)
            file_started = time.monotonic()
            if args.source_dir is None:
                raw_path = args.output / f"source_{number}.parquet"
                print(f"Downloading source {number + 1}/{args.source_count}", flush=True)
                download(url, raw_path)
            else:
                raw_path = args.source_dir / f"hits_{number}.parquet"
                if not raw_path.is_file():
                    print(f"Waiting for source {number + 1}/{args.source_count}", flush=True)
                    deadline = time.monotonic() + args.source_wait_timeout
                    while not raw_path.is_file():
                        if time.monotonic() >= deadline:
                            raise FileNotFoundError(raw_path)
                        time.sleep(5)
                print(f"Reading source {number + 1}/{args.source_count}", flush=True)
            parquet = pq.ParquetFile(raw_path)
            selected = []
            for batch in parquet.iter_batches(batch_size=32768):
                watch_ids = batch.column(batch.schema.get_field_index("WatchID"))
                mask = pa.array([
                    xxhash.xxh64_intdigest(str(int(value) % (1 << 64)).encode("ascii"))
                    % args.modulus == args.remainder
                    for value in watch_ids.to_pylist()
                ])
                filtered = batch.filter(mask)
                if filtered.num_rows:
                    selected.append(filtered)

            if writer is None:
                writer = pq.ParquetWriter(sample_path, parquet.schema_arrow, compression="zstd")
            selected_rows = sum(batch.num_rows for batch in selected)
            if selected:
                writer.write_table(pa.Table.from_batches(selected))
            with raw_path.open("rb") as raw_file:
                source_sha256 = hashlib.file_digest(raw_file, "sha256").hexdigest()
            source = {
                "url": url,
                "sha256": source_sha256,
                "bytes": raw_path.stat().st_size,
                "rows": parquet.metadata.num_rows,
                "selected_rows": selected_rows,
            }
            parquet.close()
            sources.append(source)
            if args.source_dir is None:
                raw_path.unlink()
            print(
                f"Source {number + 1}/{args.source_count}: "
                f"{selected_rows}/{source['rows']} rows, "
                f"{time.monotonic() - file_started:.1f}s",
                flush=True,
            )
    finally:
        if writer is not None:
            writer.close()

    with sample_path.open("rb") as sample:
        sample_sha256 = hashlib.file_digest(sample, "sha256").hexdigest()
    manifest = {
        "clickbench_revision": "fa52f8524ad9446695018fda6a415aade3a4ccd9",
        "hash": "xxHash64 of the ASCII unsigned-decimal WatchID, seed 0",
        "sql_predicate": (
            f"xxHash64(toString(toUInt64(WatchID))) % {args.modulus} = {args.remainder}"
        ),
        "modulus": args.modulus,
        "remainder": args.remainder,
        "source_rows": sum(source["rows"] for source in sources),
        "rows": sum(source["selected_rows"] for source in sources),
        "columns": len(pq.ParquetFile(sample_path).schema_arrow),
        "sample_file": sample_path.name,
        "sample_bytes": sample_path.stat().st_size,
        "sample_sha256": sample_sha256,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "preparation_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "sources": sources,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: value for key, value in manifest.items() if key != "sources"}), flush=True)


if __name__ == "__main__":
    main()
