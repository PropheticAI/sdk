"""Shared data models for the Prophet SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


# =============================================================================
# Time Filters (for query building)
# =============================================================================


class TimeFilter(ABC):
    """Base class for time filter specifications."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert to API request format."""
        ...


@dataclass(frozen=True)
class Now(TimeFilter):
    """Current time specification."""

    def to_dict(self) -> dict[str, Any]:
        return {"now": True}


@dataclass(frozen=True)
class MinutesAgo(TimeFilter):
    """Relative time: N minutes ago."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("value must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"relative": {"value": self.value, "unit": "minutes"}}


@dataclass(frozen=True)
class HoursAgo(TimeFilter):
    """Relative time: N hours ago."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("value must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"relative": {"value": self.value, "unit": "hours"}}


@dataclass(frozen=True)
class DaysAgo(TimeFilter):
    """Relative time: N days ago."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("value must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"relative": {"value": self.value, "unit": "days"}}


@dataclass(frozen=True)
class WeeksAgo(TimeFilter):
    """Relative time: N weeks ago."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("value must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"relative": {"value": self.value, "unit": "weeks"}}


@dataclass(frozen=True)
class At(TimeFilter):
    """Absolute time specification."""

    time: str | datetime

    def to_dict(self) -> dict[str, Any]:
        if isinstance(self.time, datetime):
            return {"absolute": {"date": self.time.isoformat()}}
        return {"absolute": {"date": self.time}}


# =============================================================================
# Sort
# =============================================================================


@dataclass(frozen=True)
class Sort:
    """Sort specification for query results."""

    field: str
    order: str = "desc"

    def __post_init__(self) -> None:
        if self.order not in ("asc", "desc"):
            raise ValueError("order must be 'asc' or 'desc'")

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "order": self.order}
