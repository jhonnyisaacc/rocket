"""Rebuild reviewable synthetic output examples; never calls live providers."""

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from rocket.models import Mode
from rocket.providers.claim_verification import verify_claims
from rocket.providers.ism import ISMIndustryRanking, ISMReport
from rocket.providers.supadata import Transcript
from rocket.store import ResearchStore
from rocket.workflows.cava import CavaWorkflow
from rocket.workflows.disclosures import DisclosureWorkflow
from rocket.workflows.ism import IsmWorkflow
from rocket.workflows.macro import MacroWorkflow
from rocket.workflows.portfolio import PortfolioState, PortfolioWorkflow, PositionState
from rocket.workflows.shorts import ShortsWorkflow
from rocket.workflows.watch import WatchWorkflow
from tests.workflows.test_candidate_outputs import NOW, context, trade
from tests.workflows.test_cava import RSS, FixtureTranscript
from tests.workflows.test_exact_claims import data


def generate(root):
    outputs = {}
    def save(name, result):
        outputs[name] = replace(result, run_id=f"example-{name}", mode=Mode.REPLAY).to_dict()
    watch = WatchWorkflow(store=ResearchStore(root / 'watch'))
    rule = {'ticker': 'BE', 'condition': 'CROSS_ABOVE', 'threshold': 100,
            'thesis': 'Caller thesis: improving margins; consider entry after reclaiming 100.', 'source_reference': 'caller:BE-thesis'}
    watch.run([rule], prices={'BE': 99}, now=NOW)
    save('watch-trigger', watch.run([rule], prices={'BE': 101}, now=NOW))
    save('watch-silent', watch.run([rule], prices={'BE': 102}, now=NOW))
    def macro_fetch(symbol):
        value = {'EFFR': 3.5, 'WALCL': 6_000_000, 'WDTGAL': 500_000, 'RRPONTSYD': 10}[symbol]
        prior = value - 10_000 if symbol == 'WALCL' else value
        return {'records': [{'date': (NOW - timedelta(days=28)).date().isoformat(), 'value': prior},
                            {'date': NOW.date().isoformat(), 'value': value}], 'retrieved_at': NOW.isoformat()}, 'fixture'
    save('macro-change', MacroWorkflow(store=ResearchStore(root / 'macro'), fetcher=macro_fetch).run(now=NOW))
    portfolio = PortfolioWorkflow(store=ResearchStore(root / 'portfolio'))
    book = PortfolioState(positions=(PositionState('BE', thesis=rule['thesis'], quantity=3),))
    portfolio.run(book, {'BE': context()}, now=NOW)
    save('portfolio-change', portfolio.run(book, {'BE': context(technical_condition='weak')}, now=NOW))
    transcript = Transcript('DXY is above 100. DXY is below 100. BTC will rise next month. Inflation commentary remains uncertain.', 'en', 'fixture', NOW)
    save('cava-review', CavaWorkflow(store=ResearchStore(root / 'cava')).run(rss_xml=RSS,
        transcript_provider=FixtureTranscript(transcript), now=NOW,
        corroborate=lambda v, c, t: verify_claims(c, t, fetcher=lambda m: {**data(m), 'retrieved_at': NOW.isoformat()})))
    reports = {'manufacturing': ISMReport('manufacturing', 'August 2026', 52,
               [ISMIndustryRanking('machinery', 'expanding', 1)], [ISMIndustryRanking('wood products', 'contracting', 1)], 'https://fixture.test/ism')}
    exposures = {'machinery': [{'ticker': 'CAT', 'exposure': 'Equipment manufacturing', 'source': 'https://fixture.test/company'}],
                 'wood products': [{'ticker': 'WY', 'exposure': 'Wood manufacturing', 'source': 'https://fixture.test/company'}]}
    save('ism-buy', IsmWorkflow(store=ResearchStore(root / 'ism'), exposures=exposures,
         context_fetcher=lambda ts: {t: context() for t in ts}).run(reports=reports, research_companies=True, now=NOW))
    save('ism-watch', IsmWorkflow(exposures=exposures, context_fetcher=lambda ts: {t: context(105) for t in ts}).run(reports=reports, research_companies=True, now=NOW))
    for name, person, family in [('pelosi', 'Nancy Pelosi', 'congress'), ('trump', 'Donald J. Trump', 'executive')]:
        save(name + '-opportunity', DisclosureWorkflow(store=ResearchStore(root / name)).run(subjects=[person],
             historical_records=[trade(person, source_family=family)], research_opportunities=True,
             context_fetcher=lambda ts: {t: context() for t in ts}, now=NOW))
    save('shorts-no-setup', ShortsWorkflow().scan_live(inputs=[], now=NOW))
    save('short-candidate', ShortsWorkflow().scan([{'ticker': 'XYZ', 'source': 'fixture',
         'event_time': NOW.isoformat(), 'available_at': NOW.isoformat(), 'technical_breakdown': True,
         'company_fundamentals': True, 'sector_weakness': True, 'valuation_support': False,
         'current_price': 90, 'technical_setup': 'Break below prior 20-session support',
         'eps_growth': -.2, 'eps_growth_basis': 'reported annual EPS', 'pe_ttm': 24,
         'entry': {'concept': 'Failed retest of broken support', 'level': 95}, 'invalidation': 102,
         'candidate_sources': [{'thesis': 'ISM contraction; independently evaluated company and technical weakness'}]}], now=NOW))
    return outputs


if __name__ == '__main__':
    with TemporaryDirectory() as directory:
        examples = generate(Path(directory))
    destination = Path('docs/examples/outputs.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(examples, indent=2) + '\n')
    print(f'{len(examples)} synthetic examples written to {destination}')
