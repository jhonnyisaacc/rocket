"""Bounded retries for idempotent read requests; never retry credential errors."""

from typing import Any

import httpx


def get_read(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    for attempt in range(2):
        try:
            response = client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if attempt or exc.response.status_code not in {429, 500, 502, 503, 504}:
                raise
        except httpx.TransportError:
            if attempt:
                raise
    raise AssertionError("unreachable retry state")
