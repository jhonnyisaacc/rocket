"""RSS primary and Supadata metadata fallback with exact channel identity."""

from datetime import UTC, datetime

import httpx

from rocket.config import env
from rocket.models import OperationalStatus
from rocket.pit import parse_datetime
from rocket.providers.dispatch import acquire
from rocket.providers.http import get_read
from rocket.providers.protocols import ProviderResult


def discover_videos(*, http=None, api_key=None, now=None):
    from rocket.workflows.cava import CAVA_CHANNEL_ID, CAVA_RSS_URL, CavaVideo, parse_rss

    now = now or datetime.now(UTC)
    owns = http is None
    client = http or httpx.Client(timeout=30, follow_redirects=True)
    def rss():
        response = get_read(client, CAVA_RSS_URL)
        response.raise_for_status()
        videos = parse_rss(response.text)
        return ProviderResult(OperationalStatus.HEALTHY, tuple(vars(v) for v in videos), datetime.now(UTC), source="youtube.rss")
    def metadata():
        key = api_key or env("SUPADATA_API_KEY")
        if not key:
            return ProviderResult(OperationalStatus.UNAVAILABLE, failure_kind="NotConfigured", source="supadata.metadata")
        headers = {"x-api-key": key}
        base = "https://api.supadata.ai/v1/youtube/"
        response = get_read(client, base + "channel/videos", params={"id": CAVA_CHANNEL_ID, "type": "video", "limit": 3}, headers=headers)
        response.raise_for_status()
        ids = response.json()["videoIds"]
        videos = []
        for video_id in ids[:3]:
            response = get_read(client, base + "video", params={"id": video_id}, headers=headers)
            response.raise_for_status()
            row = response.json()
            published = parse_datetime(row.get("uploadDate"))
            if row.get("id") != video_id or row.get("channel", {}).get("id") != CAVA_CHANNEL_ID or not published or published > now or not row.get("title"):
                raise ValueError("video/channel/publication identity mismatch")
            if not row.get("isLive"):
                videos.append(vars(CavaVideo(video_id, row["title"], published, f"https://www.youtube.com/watch?v={video_id}")))
        return ProviderResult(OperationalStatus.HEALTHY, tuple(videos), datetime.now(UTC), source="supadata.metadata")
    try:
        return acquire("cava.video_discovery", [("youtube.rss", rss), ("supadata.metadata", metadata)], retries=0)
    finally:
        if owns:
            client.close()
