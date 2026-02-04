"""Deployments API for managing sub-deployments under parent MSPs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..exceptions import APIError, AuthenticationError, ValidationError
from .models import (
    Deployment,
    DeploymentCreateResponse,
    DeploymentDeleteResponse,
    DeploymentListResponse,
)

if TYPE_CHECKING:
    from ..client import Prophet


class DeploymentsAPI:
    """
    API for managing deployments (sub-tenants) under parent MSPs.

    Accessed via `prophet.deployments`.

    Example:
        # List all sub-deployments
        response = prophet.deployments.list(parent_id="parent-123")
        for deployment in response.deployments:
            print(deployment.name)

        # Create a new sub-deployment
        result = prophet.deployments.create(
            name="Sub Tenant",
            handle="sub_tenant",
            parent_id="parent-123",
        )
        print(result.deployment.customer.customer_id)

        # Delete a sub-deployment
        prophet.deployments.delete(
            customer_id="sub-123",
            parent_id="parent-123",
        )
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def list(self, parent_id: str | None = None) -> DeploymentListResponse:
        """
        List all sub-deployments for a parent MSP.

        Args:
            parent_id: The customer_id of the parent MSP (optional, defaults to
                       the authenticated user's customer_id)

        Returns:
            DeploymentListResponse containing parent info and list of deployments

        Raises:
            AuthenticationError: If not authenticated
            APIError: If the request fails

        Example:
            # List your own sub-deployments (if you're a parent MSP)
            response = prophet.deployments.list()

            # Or specify a different parent (requires god_mode)
            response = prophet.deployments.list(parent_id="parent-123")

            for d in response.deployments:
                print(f"  - {d.name} ({d.customer_id})")
        """
        payload = {}
        if parent_id:
            payload["parent_id"] = parent_id

        response = self._client._request("GET", "/deployments/1.0", json=payload)

        self._handle_errors(response)

        data = response.json()
        return DeploymentListResponse.from_response(data)

    def create(
        self,
        name: str,
        handle: str,
        parent_id: str,
        subdomain: str | None = None,
    ) -> DeploymentCreateResponse:
        """
        Create a new sub-deployment under a parent MSP.

        Args:
            name: Display name for the sub-deployment
            handle: URL-safe identifier (will be slugified)
            parent_id: The customer_id of the parent MSP
            subdomain: Optional custom subdomain for the deployment

        Returns:
            DeploymentCreateResponse with the created deployment info

        Raises:
            ValidationError: If required fields are missing
            AuthenticationError: If not authenticated
            APIError: If the request fails

        Example:
            result = prophet.deployments.create(
                name="ACME Corp",
                handle="acme_corp",
                parent_id="parent-123",
                subdomain="acme",
            )
            print(f"Created: {result.deployment.customer.customer_id}")
        """
        if not name:
            raise ValidationError("name is required")
        if not handle:
            raise ValidationError("handle is required")
        if not parent_id:
            raise ValidationError("parent_id is required")

        payload = {
            "name": name,
            "handle": handle,
            "parent_id": parent_id,
        }

        if subdomain:
            payload["subdomain"] = subdomain

        response = self._client._request("POST", "/deployments/1.0", json=payload)

        self._handle_errors(response)

        data = response.json()
        return DeploymentCreateResponse.from_response(data)

    def delete(
        self,
        customer_id: str,
        parent_id: str,
    ) -> DeploymentDeleteResponse:
        """
        Delete a sub-deployment from a parent MSP.

        Args:
            customer_id: The customer_id of the sub-deployment to delete
            parent_id: The customer_id of the parent MSP

        Returns:
            DeploymentDeleteResponse with info about the deleted deployment

        Raises:
            ValidationError: If required fields are missing
            AuthenticationError: If not authenticated
            APIError: If the request fails (e.g., deployment not found)

        Example:
            result = prophet.deployments.delete(
                customer_id="sub-123",
                parent_id="parent-123",
            )
            print(f"Deleted: {result.deleted.name}")
        """
        if not customer_id:
            raise ValidationError("customer_id is required")
        if not parent_id:
            raise ValidationError("parent_id is required")

        payload = {
            "customer_id": customer_id,
            "parent_id": parent_id,
        }

        response = self._client._request("DELETE", "/deployments/1.0", json=payload)

        self._handle_errors(response)

        data = response.json()
        return DeploymentDeleteResponse.from_response(data)

    def get(self, customer_id: str, parent_id: str | None = None) -> Deployment | None:
        """
        Get a specific sub-deployment by customer_id.

        This is a convenience method that lists all deployments and finds
        the matching one.

        Args:
            customer_id: The customer_id of the sub-deployment
            parent_id: The customer_id of the parent MSP (optional, defaults to
                       the authenticated user's customer_id)

        Returns:
            Deployment if found, None otherwise

        Example:
            deployment = prophet.deployments.get("sub-123")
            if deployment:
                print(deployment.name)
        """
        response = self.list(parent_id)
        for deployment in response.deployments:
            if deployment.customer_id == customer_id:
                return deployment
        return None

    def _handle_errors(self, response) -> None:
        """Handle common API error responses."""
        if response.status_code == 401:
            data = response.json()
            raise AuthenticationError(
                message=data.get("error", "Authentication failed"),
                code=data.get("code"),
            )

        if response.status_code == 400:
            data = response.json()
            raise ValidationError(
                message=data.get("error", "Validation failed"),
            )

        if response.status_code == 403:
            data = response.json()
            raise APIError(
                message=data.get("error", "Unauthorized"),
                status_code=403,
                error_type="authorization_error",
            )

        if response.status_code == 404:
            data = response.json()
            raise APIError(
                message=data.get("error", "Not found"),
                status_code=404,
                error_type="not_found",
            )

        if response.status_code not in (200, 201):
            raise APIError(
                message=f"Request failed with status {response.status_code}",
                status_code=response.status_code,
            )
