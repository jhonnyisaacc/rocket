"""Research CI covers research changes while skipping the real provider-fix paths."""

import fnmatch
import json
import re
from pathlib import Path


def test_research_ci_skips_ordinary_pr63_and_pr64_changes():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / '.github/workflows/research-governance.yml').read_text()
    # Both event path lists are JSON flow sequences, also valid YAML.
    filters = [json.loads(value) for value in re.findall(r'paths: (\[[\s\S]*?\])', workflow)]
    assert len(filters) == 2, 'Both PR and push events must have scoped paths'
    ordinary_paths = [
        'rocket/providers/open_cabinet.py', 'tests/providers/test_open_cabinet.py',
        'docs/FUNDAMENTALS_PROVIDER_COVERAGE.md', 'rocket/candidates.py',
        'rocket/providers/edgar.py', 'rocket/providers/fmp.py',
        'rocket/providers/fundamentals.py', 'rocket/providers/massive.py',
        'rocket/workflows/ism.py', 'tests/providers/test_dispatch_outputs.py',
        'tests/providers/test_edgar.py', 'tests/providers/test_evidence_acquisition.py',
        'tests/providers/test_fmp.py', 'tests/providers/test_fundamentals_recovery.py',
        'tests/workflows/test_ism_support_entry.py',
    ]
    research_paths = [
        'research/governance/manifests/MOM-002.json', 'rocket/research/governance.py',
        'docs/research/RESEARCH_CHARTER.md', 'tests/research/test_governance.py',
        'pyproject.toml', 'rocket/cli.py', '.github/workflows/research-governance.yml',
    ]
    for patterns in filters:
        assert not any(fnmatch.fnmatchcase(path, pattern)
                       for path in ordinary_paths for pattern in patterns)
        assert all(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
                   for path in research_paths)
