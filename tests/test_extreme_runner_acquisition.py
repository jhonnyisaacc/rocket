"""Network byte ceilings must hold before any large archive is accepted."""

import io

import httpx
import pytest

from rocket.research.extreme_runner_acquisition import RangeArchive, bounded_download


def test_range_cache_and_cumulative_bound(tmp_path):
    requests = []

    def handle(request):
        requests.append(request.headers["range"])
        return httpx.Response(206, headers={"content-range": "bytes 0-3/8"}, content=b"abcd")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        source = RangeArchive("https://example.test/data", 8, client, tmp_path, maximum_bytes=4)
        assert source.read(4) == b"abcd"
        source.seek(0)
        assert source.read(4) == b"abcd"
        assert source.transferred == 4
        assert len(requests) == 1
        source.seek(-4, io.SEEK_END)
        with pytest.raises(ValueError, match="TRANSFER_BOUND"):
            source.read(4)
        assert len(requests) == 1
        assert len(source.requests) == 1
        assert len(list(tmp_path.glob("*.range"))) == 1


@pytest.mark.parametrize(
    "status,headers,body,error",
    [
        (200, {}, b"abcd", "RANGE_UNSUPPORTED"),
        (206, {"content-range": "bytes 1-4/8"}, b"abcd", "range mismatch"),
        (206, {"content-range": "bytes 0-3/8"}, b"abc", "truncated"),
        (206, {"content-range": "bytes 0-3/8"}, b"abcde", "overflow"),
    ],
)
def test_nonconforming_range_never_saved(tmp_path, status, headers, body, error):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, headers=headers, content=body)
        )
    ) as client:
        source = RangeArchive("https://example.test/data", 8, client, tmp_path)
        with pytest.raises(ValueError, match=error):
            source.read(4)
    assert not list(tmp_path.iterdir())


def test_bounded_download_does_not_save_overflow(tmp_path):
    output = tmp_path / "source.txt"
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"oversize"))
        ) as client,
        pytest.raises(ValueError, match="DOWNLOAD_TRANSFER_BOUND"),
    ):
        bounded_download(client, "https://example.test/data", output, 4)
    assert not output.exists()


def test_truncated_body_consumes_budget(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(206, headers={"content-range": "bytes 0-3/8"}, content=b"abc")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        source = RangeArchive("https://example.test/data", 8, client, tmp_path, maximum_bytes=4)
        with pytest.raises(ValueError, match="truncated"):
            source.read(4)
        assert source.transferred == 3
        source.seek(0)
        with pytest.raises(ValueError, match="TRANSFER_BOUND"):
            source.read(4)
        assert len(calls) == 1
