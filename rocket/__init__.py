"""Rocket: read-only, bot-runtime-agnostic research engine."""

from rocket.models import (
    Evidence,
    EvidenceKind,
    Mode,
    OperationalReport,
    OperationalStatus,
    ProviderHealth,
    ResearchResult,
    ResearchStatus,
    SafetyBoundary,
)
from rocket.pit import Availability, PointInTime

__all__ = [
    "Availability",
    "Evidence",
    "EvidenceKind",
    "Mode",
    "OperationalReport",
    "OperationalStatus",
    "PointInTime",
    "ProviderHealth",
    "ResearchResult",
    "ResearchStatus",
    "SafetyBoundary",
]

SAFETY_BOUNDARY = SafetyBoundary.READ_ONLY_RESEARCH_ONLY_HUMAN_GATED
