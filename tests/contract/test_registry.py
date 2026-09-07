from tests.harness import WORKFLOWS, registered_names


def test_every_implemented_workflow_is_registered():
    assert "macro" in WORKFLOWS
    assert "cava" in WORKFLOWS
    assert "watch.check" in WORKFLOWS
    assert "portfolio.review" in WORKFLOWS
    assert registered_names() == tuple(sorted(WORKFLOWS))
