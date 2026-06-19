"""Deployments API for managing sub-deployments under parent MSPs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import APIError, ValidationError, raise_for_response
from .models import Deployment

if TYPE_CHECKING:
    from ..client import Prophet


class DeploymentsAPI:
    """
    Manage deployments (sub-tenants) under a parent MSP. Accessed via
    `prophet.deployments`. `parent_id` defaults to the authenticated tenant
    (`prophet.customer_id`), so a parent MSP rarely needs to pass it.

    Example:
        children = prophet.deployments.list()
        for d in children:
            print(d.name, d.customer_id)

        child = prophet.deployments.create(name="ACME Corp", handle="acme")
        prophet.deployments.delete(child.customer_id)
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def list(self, parent_id: str | None = None) -> list[Deployment]:
        """
        List sub-deployments for a parent MSP.

        Args:
            parent_id: parent MSP customer_id (defaults to the authenticated tenant).

        Returns:
            list[Deployment] (empty if there are none).
        """
        params = {"parent_id": parent_id} if parent_id else {}
        response = self._client._request("GET", "/rest/deployments/1.0", params=params)
        raise_for_response(response)

        data = self._json(response)
        return [Deployment.model_validate(d) for d in data.get("deployments", [])]

    def create(self, name: str, handle: str, parent_id: str | None = None) -> Deployment:
        """
        Create a sub-deployment under a parent MSP.

        Args:
            name: display name.
            handle: url-safe identifier (slugified server-side).
            parent_id: parent MSP customer_id (defaults to the authenticated tenant).

        Returns:
            The created Deployment.
        """
        if not name:
            raise ValidationError("name is required")
        if not handle:
            raise ValidationError("handle is required")

        parent = parent_id or self._client.customer_id
        payload = {"name": name, "handle": handle, "parent_id": parent}
        response = self._client._request("POST", "/rest/deployments/1.0", json=payload)
        raise_for_response(response)

        # Response shape: {deployment: {customer: {...}, org: {...}}}
        customer = self._json(response).get("deployment", {}).get("customer", {})
        return Deployment.model_validate(customer)

    def delete(self, customer_id: str, parent_id: str | None = None) -> None:
        """Delete a sub-deployment (cascades deletion of its nodes and credentials)."""
        if not customer_id:
            raise ValidationError("customer_id is required")

        parent = parent_id or self._client.customer_id
        payload = {"customer_id": customer_id, "parent_id": parent}
        response = self._client._request("DELETE", "/rest/deployments/1.0", json=payload)
        raise_for_response(response)

    def get(self, customer_id: str, parent_id: str | None = None) -> Deployment | None:
        """Get a sub-deployment by customer_id, or None if not found."""
        for deployment in self.list(parent_id):
            if deployment.customer_id == customer_id:
                return deployment
        return None

    @staticmethod
    def _json(response: Any) -> dict[str, Any]:
        if not response.text:
            raise APIError(
                f"Empty response from API (status={response.status_code})",
                status_code=response.status_code,
            )
        try:
            data: dict[str, Any] = response.json()
        except Exception:
            raise APIError(
                f"Invalid JSON response: {response.text[:500]}",
                status_code=response.status_code,
            ) from None
        return data
