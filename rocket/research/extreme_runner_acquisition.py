"""Bounded public archive reads; evidence and byte budgets precede row inspection."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx


class RangeArchive(io.RawIOBase):
    """Seekable HTTP range input with a strict cumulative transfer cap.

    Server fallback to a whole file is rejected before reading its body. Arrow
    can inspect footers/projected row groups without downloading a multi-GB corpus.
    """

    def __init__(
        self,
        url: str,
        length: int,
        client: httpx.Client,
        directory: Path,
        maximum_bytes: int = 64 * 1024 * 1024,
    ):
        self.url, self.length, self.client = url, length, client
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.maximum_bytes = maximum_bytes
        self.transferred = 0
        self.position = 0
        self.requests: list[dict] = []
        self.cache: dict[tuple[int, int], bytes] = {}

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        target = (
            offset
            if whence == io.SEEK_SET
            else (self.position + offset if whence == io.SEEK_CUR else self.length + offset)
        )
        if target < 0:
            raise ValueError("negative archive offset")
        self.position = target
        return target

    def read(self, size=-1):
        size = self.length - self.position if size < 0 else min(size, self.length - self.position)
        if size <= 0:
            return b""
        start, stop = self.position, self.position + size
        self.position = stop
        key = (start, stop)
        if key in self.cache:
            return self.cache[key]
        if self.transferred + size > self.maximum_bytes:
            raise ValueError("ARCHIVE_TRANSFER_BOUND")
        started = datetime.now(UTC).isoformat()
        with self.client.stream(
            "GET", self.url, headers={"Range": f"bytes={start}-{stop - 1}"}
        ) as response:
            if response.status_code != 206:
                raise ValueError(f"RANGE_UNSUPPORTED_HTTP_{response.status_code}")
            if response.headers.get("content-range") != f"bytes {start}-{stop - 1}/{self.length}":
                raise ValueError("archive content range mismatch")
            data = bytearray()
            for chunk in response.iter_bytes(chunk_size=min(size, 65536)):
                # Failed/truncated responses still consume the transfer budget.
                self.transferred += len(chunk)
                if len(data) + len(chunk) > size:
                    raise ValueError("archive range byte overflow")
                data.extend(chunk)
            if len(data) != size:
                raise ValueError("archive range truncated")
        body = bytes(data)
        sha = hashlib.sha256(body).hexdigest()
        filename = f"{start}-{stop}-{sha}.range"
        (self.directory / filename).write_bytes(body)
        self.requests.append(
            {
                "url": self.url,
                "range": [start, stop],
                "bytes": size,
                "dispatch_at": started,
                "received_at": datetime.now(UTC).isoformat(),
                "sha256": sha,
                "raw_file": filename,
            }
        )
        self.cache[key] = body
        (self.directory / "range-manifest.json").write_text(
            json.dumps(self.requests, indent=2) + "\n"
        )
        return body


def bounded_download(client: httpx.Client, url: str, path: Path, maximum_bytes: int) -> dict:
    """Exact body preservation for small sources with explicit size ceiling."""
    started = datetime.now(UTC).isoformat()
    body = bytearray()
    with client.stream("GET", url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            if len(body) + len(chunk) > maximum_bytes:
                raise ValueError("DOWNLOAD_TRANSFER_BOUND")
            body.extend(chunk)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "url": url,
        "dispatch_at": started,
        "received_at": datetime.now(UTC).isoformat(),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "raw_file": str(path),
    }
