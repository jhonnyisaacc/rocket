"""The only point-in-time implementation. Workflows must not invent PIT semantics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Availability(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    LATE = "LATE"
    UNKNOWN = "UNKNOWN"


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid ISO timestamp: {value!r}") from exc
    else:
        raise ValueError(f"timestamp must be an ISO string, got {type(value).__name__}")
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a timezone: {value!r}")
    return parsed.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


@dataclass(frozen=True)
class PointInTime:
    """event_time / available_at / decision_time. Missing availability is UNKNOWN, never guessed."""

    event_time: datetime | None = None
    available_at: datetime | None = None
    decision_time: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()

    @property
    def availability(self) -> Availability:
        if (
            self.decision_time is not None
            and self.event_time is not None
            and self.event_time > self.decision_time
        ):
            return Availability.LATE
        if (
            self.available_at is not None
            and self.decision_time is not None
            and self.available_at > self.decision_time
        ):
            return Availability.LATE
        if self.event_time is None or self.available_at is None or self.decision_time is None:
            return Availability.UNKNOWN
        return (
            Availability.ELIGIBLE
            if self.available_at <= self.decision_time
            else Availability.LATE
        )

    def validate(self) -> None:
        values = (self.event_time, self.available_at, self.decision_time)
        aware = [value.tzinfo is not None for value in values if value is not None]
        if aware and not all(aware):
            raise ValueError("all supplied timestamps must either be timezone-aware or absent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_time": iso(self.event_time),
            "available_at": iso(self.available_at),
            "decision_time": iso(self.decision_time),
            "availability": self.availability.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> PointInTime:
        value = value or {}
        return cls(
            event_time=parse_datetime(value.get("event_time")),
            available_at=parse_datetime(value.get("available_at")),
            decision_time=parse_datetime(value.get("decision_time")),
        )
