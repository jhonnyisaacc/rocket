from datetime import timedelta

from rocket.models import ResearchStatus
from rocket.providers.claim_verification import verify_claims
from rocket.providers.supadata import Transcript
from rocket.store import ResearchStore
from rocket.workflows.cava import CavaWorkflow
from tests.harness import assert_research_result
from tests.workflows.test_cava import NOW, RSS, FixtureTranscript


def test_commentary_delivers_full_transcript_once_without_overlay(tmp_path):
    store = ResearchStore(tmp_path)
    store.save_state('cava_cursor', {'processed_video_ids': ['old-video']})
    text = 'Las tendencias requieren paciencia. ' * 500 + 'La gestión del riesgo es esencial.'
    provider = FixtureTranscript(Transcript(text, 'es', 'fixture', NOW))
    workflow = CavaWorkflow(store=store)
    result = workflow.run(rss_xml=RSS, transcript_provider=provider, now=NOW)
    assert_research_result(result)
    assert result.status is ResearchStatus.ACTION_REQUIRED
    assert result.payload['summary_request']['transcript'] == text
    assert result.payload['summary_status'] == 'AWAITING_CALLER_BOT'
    assert result.payload['corroboration_status'] == 'NOT_APPLICABLE'
    assert not result.payload['overlay_validated']
    assert store.load_context('cava') is None
    assert result.payload['cursor_advanced']
    again = workflow.run(rss_xml=RSS, transcript_provider=provider, now=NOW)
    assert again.status is ResearchStatus.NO_SETUP
    assert provider.calls == ['new-video']


def test_future_transcript_cannot_be_delivered_or_consumed(tmp_path):
    store = ResearchStore(tmp_path)
    result = CavaWorkflow(store=store).run(rss_xml=RSS, now=NOW,
        transcript_provider=FixtureTranscript(Transcript('Paciencia y disciplina.', 'es', 'fixture',
                                                         NOW + timedelta(hours=1))))
    assert_research_result(result)
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.payload['summary_request'] is None
    assert store.load_state('cava_cursor') is None


def test_failed_named_measure_is_not_disguised_as_summary(tmp_path):
    def unavailable(measure):
        raise RuntimeError('unavailable')
    result = CavaWorkflow(store=ResearchStore(tmp_path)).run(rss_xml=RSS, now=NOW,
        transcript_provider=FixtureTranscript(Transcript('DXY is above 100.', 'en', 'fixture', NOW)),
        corroborate=lambda v, c, t: verify_claims(c, t, fetcher=unavailable))
    assert_research_result(result)
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert 'summary_request' not in result.payload
    assert not result.payload['cursor_advanced']
