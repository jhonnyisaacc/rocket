"""Research workflows. Each returns a ResearchResult."""

from rocket.workflows.cava import CavaWorkflow
from rocket.workflows.fixture import FixtureWorkflow
from rocket.workflows.macro import MacroWorkflow
from rocket.workflows.portfolio import PortfolioWorkflow
from rocket.workflows.watch import WatchWorkflow

__all__ = [
    "CavaWorkflow",
    "FixtureWorkflow",
    "MacroWorkflow",
    "PortfolioWorkflow",
    "WatchWorkflow",
]
