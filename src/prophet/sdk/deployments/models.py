"""Data models for deployments."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Deployment(BaseModel):
    """
    A deployment (tenant). For a sub-deployment, `parent` is the parent MSP's
    customer_id. Tolerates extra fields (e.g. org_code) for forward-compat.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    customer_id: str
    name: str | None = None
    handle: str | None = None
    type: str | None = None
    parent: str | None = None
    subdomain: str | None = None
    org_code: str | None = None
    deployment: dict[str, Any] | None = None  # e.g. {'status': 'deployed'}
    created_at: str | None = None

    def __repr__(self) -> str:
        return f"Deployment({self.customer_id}, name={self.name!r}, parent={self.parent})"
