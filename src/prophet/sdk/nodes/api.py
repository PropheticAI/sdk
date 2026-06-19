"""Nodes API: per-unit provisioning + node visibility (the factory-line seam)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ..exceptions import APIError, AuthenticationError, ValidationError
from .models import Node, ProvisionedUnit

if TYPE_CHECKING:
    from ..client import Prophet


def derive_machine_id(cpu_id: str) -> str:
    """
    Deterministically derive a node machine_id from a hardware CPU ID.

    Same CPU ID always yields the same machine_id, so re-flashing a board
    re-attaches to its existing node record instead of creating a duplicate.
    """
    if not cpu_id:
        raise ValidationError("cpu_id is required to derive a machine_id")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"prophet-node:{cpu_id}"))


class NodesAPI:
    """
    API for provisioning units and inspecting nodes. Accessed via `prophet.nodes`.

    Example:
        # Provision a unit on the factory line (under a child deployment)
        unit = prophet.nodes.provision(
            deployment="meshcomm-x1234y567",
            cpu_id="0x1122334455667788",
            description="TerraLynk SN-0042",
            profile_id="<profile-uuid>",
        )
        device_yaml = unit.collector_yaml(env="prod", spool_dir="/data/apps/prophet/spool")

        # Later, gate the build on enrollment
        node = prophet.nodes.find_by_machine_id(unit.machine_id)
        if node and node.is_enrolled:
            print("unit enrolled and collecting")
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def provision(
        self,
        deployment: str,
        cpu_id: str | None = None,
        *,
        machine_id: str | None = None,
        description: str | None = None,
        profile_id: str | None = None,
    ) -> ProvisionedUnit:
        """
        Mint a per-unit, child-scoped collector credential.

        Args:
            deployment: customer_id of the target child deployment (or the
                        caller's own customer_id to provision under itself).
            cpu_id: hardware CPU ID; the SDK derives a deterministic machine_id
                    from it. Provide this OR machine_id.
            machine_id: explicit machine_id (overrides cpu_id derivation).
            description: human label (e.g. serial number) stored on the credential.
            profile_id: capture-config profile to inherit at first boot. The
                        server rejects an unknown profile_id, so a typo fails here.

        Returns:
            ProvisionedUnit with the one-time access_key, machine_id, and a
            collector_yaml() helper for the device.
        """
        if not deployment:
            raise ValidationError("deployment (target customer_id) is required")
        if not machine_id and not cpu_id:
            raise ValidationError("either cpu_id or machine_id is required")

        resolved_machine_id = machine_id or derive_machine_id(cpu_id)  # type: ignore[arg-type]

        payload: dict[str, str] = {
            "customer_id": deployment,
            "machine_id": resolved_machine_id,
        }
        if description:
            payload["description"] = description
        if profile_id:
            payload["profile_id"] = profile_id

        response = self._client._request("POST", "/rest/nodes/provision/1.0", json=payload)
        self._handle_errors(response)

        data = response.json()
        return ProvisionedUnit.from_response(data, machine_id=resolved_machine_id)

    def list(self, *, services: bool = False, hardware: bool = False) -> list[Node]:
        """
        List nodes for the authenticated customer (and its children, if a parent).

        Args:
            services: include each node's merged service config.
            hardware: include each node's reported hardware block.
        """
        params: dict[str, str] = {}
        if services:
            params["services"] = "true"
        if hardware:
            params["hardware"] = "true"

        response = self._client._request("GET", "/rest/nodes/1.0", params=params)
        self._handle_errors(response)

        data = response.json()
        return [Node.model_validate(n) for n in data.get("nodes", [])]

    def get(self, node_id: str, *, services: bool = False, hardware: bool = False) -> Node | None:
        """Get a single node by node_id, or None if it doesn't exist / isn't yours."""
        if not node_id:
            raise ValidationError("node_id is required")

        params: dict[str, str] = {}
        if services:
            params["services"] = "true"
        if hardware:
            params["hardware"] = "true"

        response = self._client._request("GET", f"/rest/nodes/1.0/{node_id}", params=params)
        if response.status_code == 404:
            return None
        self._handle_errors(response)

        return Node.model_validate(response.json())

    def find_by_machine_id(self, machine_id: str) -> Node | None:
        """
        Find the node for a given machine_id by scanning the node list.

        The node_id is controller-assigned and unknown until first boot, so the
        factory gate keys on machine_id (which the SDK derived deterministically).
        """
        if not machine_id:
            raise ValidationError("machine_id is required")
        for node in self.list():
            if getattr(node, "machine_id", None) == machine_id:
                return node
        return None

    def _handle_errors(self, response) -> None:
        if response.status_code in (200, 201):
            return
        try:
            data = response.json()
        except Exception:
            data = {}
        message = data.get("error") or data.get("message") or f"Request failed with status {response.status_code}"

        if response.status_code == 401:
            raise AuthenticationError(message=message, code=data.get("code"))
        if response.status_code == 400:
            raise ValidationError(message=message)
        if response.status_code == 403:
            raise APIError(message=message, status_code=403, error_type="authorization_error")
        if response.status_code == 404:
            raise APIError(message=message, status_code=404, error_type="not_found")
        raise APIError(message=message, status_code=response.status_code)
