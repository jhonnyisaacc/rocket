"""ER-001 bounded public source semantics; no vendor outcomes accepted as labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx
import pyarrow.parquet as pq

from rocket.research.extreme_runner_acquisition import RangeArchive, bounded_download
from rocket.research.governance import require_experiment_step


def inspect(plan: Path, root: Path) -> dict:
    require_experiment_step("ER-001", "dataset_acquisition")
    specification = json.loads(plan.read_text())
    manifest = {"schema": "rocket.er001-source-semantics.v1", "sources": []}
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for item in specification:
            directory = root / item["name"]
            directory.mkdir(parents=True, exist_ok=True)
            row = dict(item)
            try:
                url = item["url"]
                if item["format"] != "parquet":
                    row["acquisition"] = bounded_download(
                        client, url, directory / "source.txt", item.get("maximum_bytes", 1_000_000)
                    )
                else:
                    head = client.head(url)
                    head.raise_for_status()
                    length = int(head.headers["content-length"])
                    source = RangeArchive(
                        url,
                        length,
                        client,
                        directory,
                        maximum_bytes=item.get("maximum_bytes", 64 * 1024 * 1024),
                    )
                    parquet = pq.ParquetFile(source)
                    row.update(
                        file_bytes=length,
                        rows=parquet.metadata.num_rows,
                        row_groups=parquet.metadata.num_row_groups,
                        schema=str(parquet.schema_arrow),
                        columns=parquet.schema_arrow.names,
                    )
                    (directory / "schema.json").write_text(json.dumps(row, indent=2) + "\n")
                    print(item["name"], length, row["rows"], row["columns"], flush=True)
                    columns = item.get("sample_columns")
                    if columns is not None:
                        if columns == ["*"]:
                            columns = parquet.schema_arrow.names
                        columns = [c for c in columns if c in parquet.schema_arrow.names]
                        sample = parquet.read_row_group(0, columns=columns)
                        pq.write_table(sample, directory / "sample.parquet")
                        row.update(sample_rows=sample.num_rows, sampled_columns=columns)
                    row["transferred_bytes"] = source.transferred
                    row["ranges"] = source.requests
            except (ValueError, KeyError, OSError, httpx.HTTPError) as exc:
                row["error"] = {"kind": type(exc).__name__, "detail": str(exc)}
                print(item["name"], "FAILED", type(exc).__name__, str(exc), flush=True)
            manifest["sources"].append(row)
            (root / "semantic-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    inspect(args.plan, args.out)
