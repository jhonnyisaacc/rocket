from tests.harness import WORKFLOWS, registered_names


def test_every_implemented_workflow_is_registered():
    assert "macro" in WORKFLOWS
    assert "cava" in WORKFLOWS
    assert "watch.check" in WORKFLOWS
    assert "portfolio.review" in WORKFLOWS
    assert "crypto.scan" in WORKFLOWS
    assert "ism" in WORKFLOWS
    assert "disclosures" in WORKFLOWS
    assert "shorts" in WORKFLOWS
    assert "options.scan" in WORKFLOWS
    assert "memecoin.scan" in WORKFLOWS
    assert registered_names() == tuple(sorted(WORKFLOWS))
