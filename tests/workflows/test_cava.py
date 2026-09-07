from datetime import UTC, datetime

from rocket.models import Evidence, EvidenceKind, OperationalStatus, Provenance, ResearchStatus
from rocket.providers.supadata import Transcript, TranscriptUnavailable
from rocket.store import ResearchStore
from rocket.workflows.cava import CavaCorroboration, CavaWorkflow, parse_rss
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
RSS = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>yt:video:new-video</id><title>Nuevo análisis macro</title>
    <published>2026-09-04T10:00:00Z</published>
  </entry>
  <entry>
    <id>yt:video:new-video</id><title>Nuevo análisis macro</title>
    <published>2026-09-04T10:00:00Z</published>
  </entry>
  <entry>
    <id>yt:video:old-video</id><title>Video anterior</title>
    <published>2026-09-03T10:00:00Z</published>
  </entry>
</feed>"""


class FixtureTranscript:
    def __init__(self, transcript: Transcript | None = None, error: str | None = None):
        self.transcript = transcript
        self.error = error
        self.calls: list[str] = []

    def fetch(self, video_id: str) -> Transcript:
        self.calls.append(video_id)
        if self.error:
            raise TranscriptUnavailable(self.error)
        assert self.transcript is not None
        return self.transcript


def test_cava_is_registered():
    assert is_registered("cava")


def test_rss_deduplicates_and_sorts_newest_first():
    videos = parse_rss(RSS)
    assert [video.video_id for video in videos] == ["new-video", "old-video"]


def test_transcript_unavailable_does_not_advance_cursor(tmp_path):
    store = ResearchStore(tmp_path)
    provider = FixtureTranscript(error="quota temporarily unavailable")
    result = CavaWorkflow(store=store).run(rss_xml=RSS, transcript_provider=provider, now=NOW)
    assert_research_result(result)
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.operational.status is OperationalStatus.PARTIAL
    assert result.payload["cursor_advanced"] is False
    assert store.load_state("cava_cursor") is None
    assert provider.calls == ["new-video"]


def test_no_new_video_is_healthy_no_setup(tmp_path):
    store = ResearchStore(tmp_path)
    store.save_state("cava_cursor", {"processed_video_ids": ["new-video", "old-video"]})
    result = CavaWorkflow(store=store).run(
        rss_xml=RSS,
        transcript_provider=FixtureTranscript(error="unused"),
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.NO_SETUP
    assert result.operational.status is OperationalStatus.HEALTHY


def test_validated_context_advances_cursor(tmp_path):
    store = ResearchStore(tmp_path)
    transcript = Transcript(
        text="La inflación podría mantenerse alta. Esto significa que la liquidez importa.",
        language="es",
        source="supadata",
        available_at=NOW,
    )

    def corroborate(video, claims, decision_time):
        del video, claims
        topics = ("inflation", "liquidity")
        return CavaCorroboration(
            evidence=tuple(
                Evidence(
                    source="official.example",
                    reference=f"macro-source-{topic}",
                    claim="Official macro series is available",
                    kind=EvidenceKind.FACT,
                    event_time=decision_time,
                    available_at=decision_time,
                    retrieved_at=decision_time,
                    decision_time=decision_time,
                    provenance=Provenance.PROVIDER_RESULT,
                    metadata={"topic": topic},
                )
                for topic in topics
            )
        )

    result = CavaWorkflow(store=store).run(
        rss_xml=RSS,
        transcript_provider=FixtureTranscript(transcript=transcript),
        corroborate=corroborate,
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.SETUP_FOUND
    assert result.payload["cursor_advanced"] is True
    assert "new-video" in (store.load_state("cava_cursor") or {}).get("processed_video_ids", [])
