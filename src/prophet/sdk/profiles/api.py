"""Profiles API: manage reusable capture-config templates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from ..exceptions import ValidationError, raise_for_response
from .models import Profile

if TYPE_CHECKING:
    from ..client import Prophet


def lightweight_packet_services(interface_patterns: list[str] | None = None) -> dict[str, Any]:
    """
    Build a low-footprint packet-capture services block for constrained edge
    units (e.g. ~490MB ARMv7). Enables capture in lightweight mode, pins the
    interface(s), and collapses worker count. Pass to `profiles.create(services=...)`.
    """
    return {
        "packet": {
            "enabled": True,
            "lightweight": True,
            "interface_patterns": interface_patterns or [],
            "num_workers": 1,
            "process_ids": False,
        },
    }


class ProfilesAPI:
    """
    API for node capture-config profiles. Accessed via `prophet.profiles`.

    A parent MSP creates a profile once and references it by profile_id when
    provisioning units. Profile lookup at node-register time is by profile_id, so
    a parent-owned profile applies to nodes in its child deployments.

    Example:
        from prophet.sdk.profiles import lightweight_packet_services

        profile = prophet.profiles.create(
            name="TerraLynk fleet",
            services=lightweight_packet_services(interface_patterns=["eth*"]),
        )
        # ... use profile.profile_id when provisioning units ...
        prophet.profiles.delete(profile.profile_id)
    """

    def __init__(self, client: Prophet) -> None:
        self._client = client

    def create(
        self,
        name: str,
        *,
        description: str | None = None,
        services: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        update_channel: Literal["stable", "dev", "pinned"] = "stable",
        fleet_staging: bool = False,
    ) -> Profile:
        """
        Create a profile owned by the authenticated customer.

        Args:
            name: display name.
            description: optional notes.
            services: partial services config (merged with server defaults).
                      See lightweight_packet_services() for edge units.
            tags: optional tags applied to nodes using this profile.
            update_channel: "stable" | "dev" | "pinned".
            fleet_staging: if True, provision-token nodes start "staged" (requires
                           assignment). Leave False for the access_key factory flow.
        """
        if not name:
            raise ValidationError("name is required")

        payload: dict[str, Any] = {
            "name": name,
            "update_channel": update_channel,
            "fleet_staging": fleet_staging,
        }
        if description is not None:
            payload["description"] = description
        if services is not None:
            payload["services"] = services
        if tags is not None:
            payload["tags"] = tags

        response = self._client._request("POST", "/rest/profiles/1.0", json=payload)
        raise_for_response(response)

        return Profile.model_validate(response.json()["profile"])

    def list(self) -> list[Profile]:
        """List profiles owned by the authenticated customer (and its children)."""
        response = self._client._request("GET", "/rest/profiles/1.0")
        raise_for_response(response)
        return [Profile.model_validate(p) for p in response.json().get("profiles", [])]

    def delete(self, profile_id: str) -> None:
        """Delete a profile the caller owns."""
        if not profile_id:
            raise ValidationError("profile_id is required")
        response = self._client._request("DELETE", f"/rest/profiles/1.0/{profile_id}")
        raise_for_response(response)
