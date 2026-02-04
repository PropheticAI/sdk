"""Data models for deployments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict


class DeploymentModel(BaseModel):
    """Base model for deployment-related models."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


class ParentInfo(DeploymentModel):
    """Parent MSP information."""

    customer_id: str
    name: str
    handle: str


class Deployment(DeploymentModel):
    """A sub-deployment (child tenant) under a parent MSP."""

    customer_id: str
    name: str
    handle: str
    type: str | None = None
    parent: str | None = None
    subdomain: str | None = None
    deployment: dict[str, Any] | None = None  # e.g. {'status': 'deployed'}
    created_at: str | None = None

    def __repr__(self) -> str:
        return f"Deployment({self.customer_id}, name={self.name!r}, parent={self.parent})"


class DeploymentOrg(DeploymentModel):
    """Kinde organization info for a deployment."""

    code: str
    name: str
    handle: str


class CreatedDeploymentCustomer(DeploymentModel):
    """Customer info returned when creating a deployment."""

    customer_id: str
    name: str
    handle: str
    type: str | None = None
    parent: str | None = None
    subdomain: str | None = None
    org_code: str | None = None
    deployment: dict[str, Any] | None = None  # e.g. {'status': 'deployed'}
    created_at: str | None = None


class CreatedDeployment(DeploymentModel):
    """Response from creating a new sub-deployment."""

    customer: CreatedDeploymentCustomer
    org: DeploymentOrg


class DeletedDeployment(DeploymentModel):
    """Info about a deleted deployment."""

    customer_id: str
    name: str
    handle: str


@dataclass
class DeploymentListResponse:
    """Response from listing sub-deployments."""

    parent: ParentInfo
    deployments: list[Deployment]
    count: int

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> DeploymentListResponse:
        """Create from API response."""
        parent_data = data.get("parent", {})
        parent = ParentInfo.model_validate(parent_data)

        deployments_data = data.get("deployments", [])
        deployments = [Deployment.model_validate(d) for d in deployments_data]

        return cls(
            parent=parent,
            deployments=deployments,
            count=data.get("count", len(deployments)),
        )


@dataclass
class DeploymentCreateResponse:
    """Response from creating a sub-deployment."""

    deployment: CreatedDeployment

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> DeploymentCreateResponse:
        """Create from API response."""
        deployment_data = data.get("deployment", {})
        deployment = CreatedDeployment.model_validate(deployment_data)
        return cls(deployment=deployment)


@dataclass
class DeploymentDeleteResponse:
    """Response from deleting a sub-deployment."""

    message: str
    deleted: DeletedDeployment

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> DeploymentDeleteResponse:
        """Create from API response."""
        deleted_data = data.get("deleted", {})
        deleted = DeletedDeployment.model_validate(deleted_data)
        return cls(
            message=data.get("message", ""),
            deleted=deleted,
        )
