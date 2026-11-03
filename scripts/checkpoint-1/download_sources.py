"""Download all published ClickBench Parquet parts without sampling or loading."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def download_part(number, output):
    filename = f"hits_{number}.parquet"
    url = f"https://datasets.clickhouse.com/hits_compatible/athena_partitioned/{filename}"
    headers = {"User-Agent": "nis-project/1"}
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers=headers, method="HEAD")
            with urllib.request.urlopen(request, timeout=90) as response:
                size = int(response.headers["Content-Length"])
                etag = response.headers.get("ETag")
            break
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    target = output / filename
    partial = output / (filename + ".partial")
    metadata = {"part": number, "file": filename, "url": url, "bytes": size, "etag": etag}
    if target.exists():
        if target.stat().st_size != size:
            raise ValueError(f"Unexpected size of existing {filename}")
        return metadata

    for attempt in range(5):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > size:
                raise ValueError(f"Partial file exceeds the expected size: {filename}")
            if offset < size:
                request_headers = dict(headers)
                if offset:
                    request_headers["Range"] = f"bytes={offset}-"
                if etag:
                    request_headers["If-Match"] = etag
                request = urllib.request.Request(url, headers=request_headers)
                with urllib.request.urlopen(request, timeout=90) as source:
                    if offset and (
                        source.status != 206
                        or not source.headers.get("Content-Range", "").startswith(f"bytes {offset}-")
                    ):
                        raise urllib.error.URLError(f"Cannot resume {filename}")
                    with partial.open("ab") as destination:
                        while chunk := source.read(1024 * 1024):
                            destination.write(chunk)
                if partial.stat().st_size != size:
                    raise urllib.error.URLError(f"Incomplete download of {filename}")
            partial.replace(target)
            return metadata
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            if attempt == 4:
                raise
            print(f"Retry {filename}: {error}", flush=True)
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 32:
        parser.error("workers must be between 1 and 32")
    args.output.mkdir(parents=True, exist_ok=True)
    sources = []
    print(f"Downloading 100 ClickBench files with {args.workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks = [pool.submit(download_part, number, args.output) for number in range(100)]
        for task in as_completed(tasks):
            source = task.result()
            sources.append(source)
            print(f"Finished {len(sources)}/100: {source['file']}", flush=True)
    manifest = {
        "source_count": len(sources),
        "total_bytes": sum(source["bytes"] for source in sources),
        "sources": sorted(sources, key=lambda source: source["part"]),
    }
    (args.output / "downloads.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Download complete: {len(sources)} files, {manifest['total_bytes']} bytes", flush=True)


if __name__ == "__main__":
    main()
