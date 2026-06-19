"""Data models for node profiles."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Profile(BaseModel):
    """
    A reusable capture-config template (the `node_profiles` document).

    Tolerates extra fields so server-side schema additions don't break the SDK.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    profile_id: str
    customer_id: str
    name: str
    description: str | None = None
    services: dict[str, Any] | None = None
    tags: list[str] | None = None
    update_channel: Literal["stable", "dev", "pinned"] | str | None = None
    auto_update: bool | None = None
    fleet_staging: bool | None = None

    def __repr__(self) -> str:
        return f"Profile({self.profile_id}, name={self.name!r})"
