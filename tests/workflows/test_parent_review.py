from datetime import timedelta

import pytest

from rocket.models import ResearchStatus
from rocket.providers.ism import ISMReport
from rocket.providers.supadata import Transcript
from rocket.store import ResearchStore
from rocket.workflows.cava import CavaWorkflow, corroborate_claims
from rocket.workflows.ism import IsmWorkflow
from tests.workflows.test_cava import NOW, RSS, FixtureTranscript


@pytest.mark.parametrize('text,window', [('Las tasas importan.', 7), ('La liquidez importa.', 14), ('La inflación importa.', 62)])
@pytest.mark.parametrize('extra', [0, 1])
def test_cava_calendar_boundary_through_real_corroborator(tmp_path, text, window, extra):
    day = (NOW - timedelta(days=window + extra)).date().isoformat()
    result = CavaWorkflow(store=ResearchStore(tmp_path)).run(
        rss_xml=RSS, now=NOW,
        transcript_provider=FixtureTranscript(Transcript(text, 'es', 'fixture', NOW)),
        corroborate=lambda v, c, t: corroborate_claims(c, t, series_fetcher=lambda s: {
            'records': [{'date': day, 'value': 3}], 'retrieved_at': NOW.isoformat()}))
    assert result.payload['cursor_advanced'] is (extra == 0)
    assert result.status is (ResearchStatus.SETUP_FOUND if extra == 0 else ResearchStatus.INSUFFICIENT_EVIDENCE)


@pytest.mark.parametrize('month,value,expected', [
    ('2026-08', 54.6, 54.6), ('2026-07', 54.6, None),
    ('2026-08', '54.6', None), ('2026-08', None, None),
    ('2026-08', True, None), ('2026-08', float('nan'), None),
])
def test_napm_fallback_requires_matching_month_and_numeric_value(month, value, expected):
    reports = {k: ISMReport(k, 'August 2026', None) for k in ('manufacturing', 'services')}
    result = IsmWorkflow().run(now=NOW, reports=reports, napm={'reference_month': month, 'value': value})
    assert result.payload['reports']['manufacturing']['pmi'] == expected
    assert result.payload['reports']['services']['pmi'] is None


def test_napm_never_overwrites_publisher_headline():
    result = IsmWorkflow().run(now=NOW,
        reports={'manufacturing': ISMReport('manufacturing', 'August 2026', 52)},
        napm={'reference_month': '2026-08', 'value': 54.6})
    assert result.payload['reports']['manufacturing']['pmi'] == 52
    assert result.payload['reports']['manufacturing']['pmi_source'] == 'ISM publisher release'
